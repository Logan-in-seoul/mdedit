from app.blocks import extract_blocks
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import app.index as fts_index
from app.main import app, set_config
from app.schema import AppConfig, RootConfig


def test_extract_blocks_basic():
    text = "첫 번째 단락 ^intro\n두 번째 ^summary\n일반 줄"
    blocks = extract_blocks(text)
    assert blocks["intro"] == "첫 번째 단락"
    assert blocks["summary"] == "두 번째"


def test_extract_blocks_no_blocks():
    text = "그냥 일반 텍스트\n블록 없음"
    blocks = extract_blocks(text)
    assert blocks == {}


@pytest.fixture
def block_vault(tmp_path: Path):
    root = tmp_path / "vault"
    root.mkdir()
    (root / "note.md").write_text("첫째 ^first\n둘째 ^second\n", encoding="utf-8")

    state_dir = tmp_path / ".mdedit"
    fts_index.init_db(state_dir)
    config = AppConfig(roots=[RootConfig(name="vault", path=root)])
    set_config(config)
    fts_index.refresh(config)
    return TestClient(app), root


def test_block_api_returns_content(block_vault):
    client, _ = block_vault
    resp = client.get("/api/block", params={"path": "vault://note.md", "block_id": "first"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["block_id"] == "first"
    assert data["content"] == "첫째"


def test_block_api_unknown_block_returns_404(block_vault):
    client, _ = block_vault
    resp = client.get("/api/block", params={"path": "vault://note.md", "block_id": "ghost"})
    assert resp.status_code == 404
