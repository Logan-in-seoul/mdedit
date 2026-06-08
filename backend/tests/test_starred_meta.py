"""고정 섹션 메타데이터 회귀 테스트.

Regression: ISSUE-001 — 고정 섹션이 최근 수정 목록(files_flat limit)과의
교집합만 그려서, limit 밖으로 밀려난 별표 파일이 UI에서 사라졌다.
Found by /qa on 2026-06-08.
Report: .gstack/qa-reports/qa-report-mdedit-2026-06-08.md

/api/starred가 files 메타데이터를 동봉해 프론트가 최근 목록과 무관하게
고정 섹션을 그릴 수 있는지 검증한다.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import index as fts_index
from app.main import app, set_config
from app.schema import AppConfig, RootConfig


@pytest.fixture
def meta_vault(tmp_path: Path) -> AppConfig:
    root = tmp_path / "common"
    root.mkdir()
    (root / "alpha.md").write_text("# Alpha\n\n본문\n", encoding="utf-8")
    (root / "beta.md").write_text("# 베타 제목\n\n본문\n", encoding="utf-8")
    fts_index.init_db(tmp_path / "state")
    cfg = AppConfig(roots=[RootConfig(name="common", path=root)])
    fts_index.refresh(cfg)
    set_config(cfg)
    return cfg


@pytest.fixture
def client(meta_vault: AppConfig) -> TestClient:
    return TestClient(app)


def test_starred_response_includes_files_metadata(client: TestClient) -> None:
    """GET /api/starred는 paths와 함께 files 메타데이터를 반환한다."""
    res = client.put("/api/starred", params={"path": "common://alpha.md"})
    assert res.status_code == 200

    res = client.get("/api/starred")
    assert res.status_code == 200
    data = res.json()
    assert data["paths"] == ["common://alpha.md"]
    assert len(data["files"]) == 1
    entry = data["files"][0]
    assert entry["path"] == "common://alpha.md"
    assert entry["name"] == "alpha.md"
    assert entry["mtime"] > 0
    assert entry["size"] > 0


def test_starred_files_keep_starred_order_and_title(client: TestClient) -> None:
    """files는 starred_at 역순(최근 별표 우선)이고 frontmatter title을 포함한다."""
    client.put("/api/starred", params={"path": "common://alpha.md"})
    client.put("/api/starred", params={"path": "common://beta.md"})
    # 같은 초에 별표가 찍히면 starred_at tie로 path 정렬이 되므로 시각을 분리한다
    db = fts_index.get_db()
    db.execute(
        "UPDATE starred SET starred_at = starred_at + 10 WHERE path = ?",
        ("common://beta.md",),
    )
    db.commit()

    data = client.get("/api/starred").json()
    assert [f["path"] for f in data["files"]] == [
        "common://beta.md",
        "common://alpha.md",
    ]
    assert data["files"][0]["title"] == "베타 제목"


def test_unstarred_file_dropped_from_files(client: TestClient) -> None:
    """별표 해제 시 files에서도 제거된다."""
    client.put("/api/starred", params={"path": "common://alpha.md"})
    client.delete("/api/starred", params={"path": "common://alpha.md"})

    data = client.get("/api/starred").json()
    assert data["paths"] == []
    assert data["files"] == []
