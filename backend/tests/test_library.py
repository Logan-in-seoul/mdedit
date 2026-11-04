"""자료함 보기: frontmatter type 으로 표시한 파일만 고른다."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import index as fts_index
from app.main import app, set_config
from app.schema import AppConfig, RootConfig


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    root = tmp_path / "home"
    root.mkdir()
    (root / "script.md").write_text("---\ntype: 대본\n---\n# 대본\n", encoding="utf-8")
    (root / "research.md").write_text("---\ntype: 조사\n---\n# 조사\n", encoding="utf-8")
    (root / "draft.md").write_text("# 중간 작업\n", encoding="utf-8")
    (root / "study.md").write_text("---\ntype: 학습\n---\n# 학습노트\n", encoding="utf-8")
    fts_index.init_db(tmp_path / "state")
    cfg = AppConfig(roots=[RootConfig(name="home", path=root)])
    fts_index.refresh(cfg)
    set_config(cfg)
    c = TestClient(app)
    c.root = root  # type: ignore[attr-defined]
    return c


def test_library_returns_only_typed(client: TestClient) -> None:
    r = client.get("/api/files/library")
    assert r.status_code == 200
    got = {f["name"]: f["type"] for f in r.json()}
    assert got == {"script.md": "대본", "research.md": "조사", "study.md": "학습"}


def test_library_types_param(client: TestClient) -> None:
    r = client.get("/api/files/library", params={"types": "대본"})
    assert [f["name"] for f in r.json()] == ["script.md"]


def test_star_reindexes_so_new_type_shows(client: TestClient) -> None:
    root: Path = client.root  # type: ignore[attr-defined]
    (root / "draft.md").write_text("---\ntype: 대본\n---\n# 이제 대본\n", encoding="utf-8")
    assert client.put("/api/starred", params={"path": "home://draft.md"}).status_code == 200
    names = {f["name"] for f in client.get("/api/files/library").json()}
    assert "draft.md" in names


def test_index_file_endpoint_and_deleted_file_dropped(client: TestClient) -> None:
    root: Path = client.root  # type: ignore[attr-defined]
    (root / "new.md").write_text("---\ntype: 조사\n---\n# 새 조사\n", encoding="utf-8")
    assert client.put("/api/index/file", params={"path": "home://new.md"}).status_code == 200
    (root / "script.md").unlink()
    names = {f["name"] for f in client.get("/api/files/library").json()}
    assert "new.md" in names and "script.md" not in names
