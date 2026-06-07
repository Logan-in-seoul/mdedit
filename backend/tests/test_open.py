from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.fs import FileNotFoundInVault, to_virtual_path
from app.main import app, set_config
from app.schema import AppConfig, RootConfig


# ---------------------------------------------------------------------------
# to_virtual_path — 절대 경로 → 가상 경로 변환 로직
# ---------------------------------------------------------------------------


@pytest.fixture
def vault_config(tmp_path: Path) -> AppConfig:
    common = tmp_path / "common"
    common.mkdir()
    (common / "note.md").write_text("# note", encoding="utf-8")
    sub = common / "sub"
    sub.mkdir()
    (sub / "deep.md").write_text("# deep", encoding="utf-8")
    return AppConfig(roots=[RootConfig(name="common", path=common)])


def test_to_virtual_path_converts_file_inside_root(vault_config: AppConfig, tmp_path: Path):
    abs_path = tmp_path / "common" / "note.md"
    assert to_virtual_path(abs_path, vault_config) == "common://note.md"


def test_to_virtual_path_handles_nested_file(vault_config: AppConfig, tmp_path: Path):
    abs_path = tmp_path / "common" / "sub" / "deep.md"
    assert to_virtual_path(abs_path, vault_config) == "common://sub/deep.md"


def test_to_virtual_path_rejects_file_outside_roots(vault_config: AppConfig, tmp_path: Path):
    outsider = tmp_path / "elsewhere.md"
    outsider.write_text("# out", encoding="utf-8")
    with pytest.raises(FileNotFoundInVault, match="outside all configured roots"):
        to_virtual_path(outsider, vault_config)


def test_to_virtual_path_rejects_non_markdown(vault_config: AppConfig, tmp_path: Path):
    txt = tmp_path / "common" / "plain.txt"
    txt.write_text("text", encoding="utf-8")
    with pytest.raises(FileNotFoundInVault, match="not a markdown file"):
        to_virtual_path(txt, vault_config)


def test_to_virtual_path_rejects_missing_file(vault_config: AppConfig, tmp_path: Path):
    with pytest.raises(FileNotFoundInVault, match="file not found"):
        to_virtual_path(tmp_path / "common" / "ghost.md", vault_config)


def test_to_virtual_path_rejects_relative_path(vault_config: AppConfig):
    with pytest.raises(FileNotFoundInVault, match="not an absolute path"):
        to_virtual_path("common/note.md", vault_config)


def test_to_virtual_path_prefers_deepest_root(tmp_path: Path):
    """루트가 중첩되면 최장 prefix(더 깊은 루트)가 이긴다."""
    outer = tmp_path / "outer"
    inner = outer / "inner"
    inner.mkdir(parents=True)
    (inner / "doc.md").write_text("# doc", encoding="utf-8")
    config = AppConfig(
        roots=[
            RootConfig(name="outer", path=outer),
            RootConfig(name="inner", path=inner),
        ]
    )
    assert to_virtual_path(inner / "doc.md", config) == "inner://doc.md"


def test_to_virtual_path_resolves_dotdot_segments(vault_config: AppConfig, tmp_path: Path):
    abs_path = tmp_path / "common" / "sub" / ".." / "note.md"
    assert to_virtual_path(abs_path, vault_config) == "common://note.md"


# ---------------------------------------------------------------------------
# POST /api/open + GET /api/open/pending 엔드포인트
# ---------------------------------------------------------------------------


@pytest.fixture
def open_client(vault_config: AppConfig) -> TestClient:
    set_config(vault_config)
    client = TestClient(app)
    # 다른 테스트가 남긴 pending을 비운다
    client.get("/api/open/pending")
    return client


def test_open_endpoint_converts_and_stores_pending(open_client: TestClient, tmp_path: Path):
    abs_path = str(tmp_path / "common" / "note.md")
    response = open_client.post("/api/open", json={"abs_path": abs_path})
    assert response.status_code == 200
    assert response.json() == {"path": "common://note.md"}

    pending = open_client.get("/api/open/pending")
    assert pending.status_code == 200
    assert pending.json() == {"path": "common://note.md"}


def test_open_pending_clears_after_read(open_client: TestClient, tmp_path: Path):
    abs_path = str(tmp_path / "common" / "note.md")
    open_client.post("/api/open", json={"abs_path": abs_path})
    assert open_client.get("/api/open/pending").json()["path"] == "common://note.md"
    # 두 번째 조회는 비어 있어야 한다
    assert open_client.get("/api/open/pending").json() == {"path": None}


def test_open_pending_empty_by_default(open_client: TestClient):
    assert open_client.get("/api/open/pending").json() == {"path": None}


def test_open_endpoint_404_for_path_outside_roots(open_client: TestClient, tmp_path: Path):
    outsider = tmp_path / "outside.md"
    outsider.write_text("# out", encoding="utf-8")
    response = open_client.post("/api/open", json={"abs_path": str(outsider)})
    assert response.status_code == 404
    assert "outside all configured roots" in response.json()["detail"]
    # 실패한 open은 pending을 만들지 않는다
    assert open_client.get("/api/open/pending").json() == {"path": None}


def test_open_endpoint_404_for_missing_file(open_client: TestClient, tmp_path: Path):
    response = open_client.post(
        "/api/open", json={"abs_path": str(tmp_path / "common" / "ghost.md")}
    )
    assert response.status_code == 404


def test_open_endpoint_overwrites_previous_pending(open_client: TestClient, tmp_path: Path):
    open_client.post("/api/open", json={"abs_path": str(tmp_path / "common" / "note.md")})
    open_client.post(
        "/api/open", json={"abs_path": str(tmp_path / "common" / "sub" / "deep.md")}
    )
    assert open_client.get("/api/open/pending").json()["path"] == "common://sub/deep.md"
