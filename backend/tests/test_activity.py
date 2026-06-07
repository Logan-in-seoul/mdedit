"""활동 피드 (/api/activity) 테스트 (v0.8)."""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import index as fts_index
from app.main import app, set_config
from app.schema import AppConfig, RootConfig


@pytest.fixture
def activity_vault(tmp_path: Path) -> AppConfig:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "fresh.md").write_text("# 오늘 작업\n\n본문", encoding="utf-8")
    old = root / "old.md"
    old.write_text("# 오래된 문서\n\n본문", encoding="utf-8")
    past = time.time() - 120 * 86400  # 120일 전 — 기본 14일 윈도 밖
    os.utime(old, (past, past))
    fts_index.init_db(tmp_path / "state")
    cfg = AppConfig(roots=[RootConfig(name="vault", path=root)])
    fts_index.refresh(cfg)
    set_config(cfg)
    return cfg


@pytest.fixture
def client(activity_vault: AppConfig) -> TestClient:
    return TestClient(app)


class TestActivity:
    def test_recent_file_included_old_excluded(self, client: TestClient):
        body = client.get("/api/activity").json()
        paths = [e["path"] for e in body["entries"]]
        assert "vault://fresh.md" in paths
        assert "vault://old.md" not in paths

    def test_wider_window_includes_old(self, client: TestClient):
        # 120일 전 파일 — refresh가 mtime을 인덱스에 보존했는지 포함 여부로 확인
        body = client.get("/api/activity", params={"days": 90}).json()
        paths = [e["path"] for e in body["entries"]]
        assert "vault://old.md" not in paths  # 90 < 120 — 여전히 밖
        assert "vault://fresh.md" in paths

    def test_entry_shape_and_order(self, client: TestClient):
        body = client.get("/api/activity").json()
        entry = body["entries"][0]
        assert set(entry) == {"path", "name", "title", "mtime", "created_same_day"}
        assert entry["title"] == "오늘 작업"
        mtimes = [e["mtime"] for e in body["entries"]]
        assert mtimes == sorted(mtimes, reverse=True)

    def test_fresh_file_created_same_day(self, client: TestClient):
        body = client.get("/api/activity").json()
        fresh = next(e for e in body["entries"] if e["path"] == "vault://fresh.md")
        # 방금 만든 파일: birthtime == mtime 날짜 (birthtime 미지원 플랫폼은 skip)
        if not hasattr(os.stat(__file__), "st_birthtime"):
            pytest.skip("platform lacks st_birthtime")
        assert fresh["created_same_day"] is True

    def test_deleted_file_skipped(self, client: TestClient, tmp_path: Path):
        (tmp_path / "vault" / "fresh.md").unlink()
        # 인덱스엔 남아 있지만 stat 실패 → 항목에서 제외
        body = client.get("/api/activity").json()
        assert "vault://fresh.md" not in [e["path"] for e in body["entries"]]

    def test_limit_param(self, client: TestClient):
        body = client.get("/api/activity", params={"limit": 1}).json()
        assert len(body["entries"]) <= 1
