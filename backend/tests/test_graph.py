from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import app.index as fts_index
from app.main import app, set_config
from app.schema import AppConfig, RootConfig


@pytest.fixture
def linked_vault(tmp_path: Path):
    """a.md → b.md → c.md 단방향 체인 볼트."""
    root = tmp_path / "vault"
    root.mkdir()
    (root / "a.md").write_text("# a\n\n[[b]]\n", encoding="utf-8")
    (root / "b.md").write_text("# b\n\n[[c]]\n", encoding="utf-8")
    (root / "c.md").write_text("# c\n\n내용\n", encoding="utf-8")

    state_dir = tmp_path / ".mdedit"
    fts_index.init_db(state_dir)
    config = AppConfig(roots=[RootConfig(name="vault", path=root)])
    set_config(config)
    fts_index.refresh(config)
    return TestClient(app), root


def test_links_table_populated_after_refresh(linked_vault):
    client, root = linked_vault
    resp = client.get("/api/graph", params={"path": "vault://a.md", "depth": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert any(n["id"] == "vault://a.md" for n in data["nodes"])
    assert any(e["source"] == "vault://a.md" for e in data["edges"])


def test_graph_depth_2_includes_transitive(linked_vault):
    client, root = linked_vault
    resp = client.get("/api/graph", params={"path": "vault://a.md", "depth": 2})
    assert resp.status_code == 200
    data = resp.json()
    node_ids = {n["id"] for n in data["nodes"]}
    assert "vault://c.md" in node_ids


def test_graph_depth_1_excludes_transitive(linked_vault):
    client, root = linked_vault
    resp = client.get("/api/graph", params={"path": "vault://a.md", "depth": 1})
    assert resp.status_code == 200
    data = resp.json()
    node_ids = {n["id"] for n in data["nodes"]}
    assert "vault://c.md" not in node_ids


def test_graph_unknown_path_returns_empty(linked_vault):
    client, _ = linked_vault
    resp = client.get("/api/graph", params={"path": "vault://nonexistent.md", "depth": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert data["nodes"] == []
    assert data["edges"] == []
