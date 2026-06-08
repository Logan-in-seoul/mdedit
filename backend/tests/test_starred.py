"""별표 고정 기능 테스트 (v0.5.0).

starred 테이블 영속성, API 라운드트립, 삭제 파일 정리를 검증한다.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import index as fts_index
from app.main import app, set_config
from app.schema import AppConfig, RootConfig


@pytest.fixture
def starred_vault(tmp_path: Path) -> AppConfig:
    root = tmp_path / "common"
    root.mkdir()
    (root / "alpha.md").write_text("# Alpha\n\n본문\n", encoding="utf-8")
    (root / "beta.md").write_text("# Beta\n\n본문\n", encoding="utf-8")
    fts_index.init_db(tmp_path / "state")
    cfg = AppConfig(roots=[RootConfig(name="common", path=root)])
    fts_index.refresh(cfg)
    set_config(cfg)
    return cfg


@pytest.fixture
def client(starred_vault: AppConfig) -> TestClient:
    return TestClient(app)


class TestStarredCore:
    def test_star_and_list(self, starred_vault: AppConfig):
        assert fts_index.star("common://alpha.md") is True
        assert fts_index.list_starred() == ["common://alpha.md"]

    def test_star_unknown_path_returns_false(self, starred_vault: AppConfig):
        assert fts_index.star("common://nope.md") is False
        assert fts_index.list_starred() == []

    def test_unstar_idempotent(self, starred_vault: AppConfig):
        fts_index.star("common://alpha.md")
        fts_index.unstar("common://alpha.md")
        fts_index.unstar("common://alpha.md")  # 두 번 해도 에러 없음
        assert fts_index.list_starred() == []

    def test_recent_star_first(self, starred_vault: AppConfig):
        db = fts_index.get_db()
        fts_index.star("common://alpha.md")
        fts_index.star("common://beta.md")
        # starred_at 동률 가능성 제거를 위해 직접 시간 조정
        db.execute(
            "UPDATE starred SET starred_at = starred_at + 10 WHERE path = ?",
            ("common://beta.md",),
        )
        db.commit()
        assert fts_index.list_starred() == ["common://beta.md", "common://alpha.md"]

    def test_deleted_file_removed_from_starred(self, starred_vault: AppConfig, tmp_path: Path):
        fts_index.star("common://alpha.md")
        (tmp_path / "common" / "alpha.md").unlink()
        fts_index.refresh(starred_vault)
        assert fts_index.list_starred() == []


class TestStarredApi:
    def test_put_get_delete_roundtrip(self, client: TestClient):
        res = client.put("/api/starred", params={"path": "common://alpha.md"})
        assert res.status_code == 200
        assert res.json()["ok"] is True

        res = client.get("/api/starred")
        # v0.8.1: files 메타데이터 동봉 (ISSUE-001) — paths contract는 유지
        assert res.json()["paths"] == ["common://alpha.md"]

        res = client.delete("/api/starred", params={"path": "common://alpha.md"})
        assert res.status_code == 200

        res = client.get("/api/starred")
        assert res.json()["paths"] == []

    def test_put_unknown_path_404(self, client: TestClient):
        res = client.put("/api/starred", params={"path": "common://nope.md"})
        assert res.status_code == 404
