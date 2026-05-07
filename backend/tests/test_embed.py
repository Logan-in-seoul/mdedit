from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import app.index as fts_index
from app.main import app, set_config
from app.schema import AppConfig, RootConfig


@pytest.fixture
def embed_vault(tmp_path: Path):
    root = tmp_path / "vault"
    root.mkdir()
    (root / "note.md").write_text("# 제목\n\n본문 내용입니다.\n", encoding="utf-8")

    state_dir = tmp_path / ".mdedit"
    fts_index.init_db(state_dir)
    config = AppConfig(roots=[RootConfig(name="vault", path=root)])
    set_config(config)
    fts_index.refresh(config)
    return TestClient(app), root


def test_embed_returns_body(embed_vault):
    client, _ = embed_vault
    resp = client.get("/api/embed", params={"path": "vault://note.md"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["path"] == "vault://note.md"
    assert "본문" in data["body"]


def test_embed_unknown_returns_404(embed_vault):
    client, _ = embed_vault
    resp = client.get("/api/embed", params={"path": "vault://ghost.md"})
    assert resp.status_code == 404
