"""vault 밖 .md 임시 열기 (ext://) 테스트 (v0.7).

인메모리 등록제: /api/open이 등록한 절대경로만 /api/file에서 읽힌다.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import fs
from app.fs import FileNotFoundInVault, register_external, resolve_external
from app.main import app, set_config
from app.schema import AppConfig, RootConfig


@pytest.fixture
def ext_vault(tmp_path: Path) -> AppConfig:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "inside.md").write_text("# inside", encoding="utf-8")
    cfg = AppConfig(roots=[RootConfig(name="vault", path=root)])
    set_config(cfg)
    return cfg


@pytest.fixture
def outside_md(tmp_path: Path) -> Path:
    p = tmp_path / "elsewhere" / "draft.md"
    p.parent.mkdir()
    p.write_text("# 외부 문서\n\n본문", encoding="utf-8")
    return p


@pytest.fixture(autouse=True)
def _clean_registry():
    fs._EXTERNAL_FILES.clear()
    yield
    fs._EXTERNAL_FILES.clear()


class TestRegistry:
    def test_register_returns_ext_virtual(self, outside_md: Path):
        virtual = register_external(outside_md)
        assert virtual == f"ext://{outside_md.resolve()}"

    def test_resolve_registered(self, outside_md: Path):
        virtual = register_external(outside_md)
        assert resolve_external(virtual) == outside_md.resolve()

    def test_resolve_unregistered_raises(self, outside_md: Path):
        with pytest.raises(FileNotFoundInVault, match="not registered"):
            resolve_external(f"ext://{outside_md.resolve()}")

    def test_register_rejects_non_markdown(self, tmp_path: Path):
        txt = tmp_path / "x.txt"
        txt.write_text("x", encoding="utf-8")
        with pytest.raises(FileNotFoundInVault, match="not a markdown"):
            register_external(txt)

    def test_register_rejects_missing(self, tmp_path: Path):
        with pytest.raises(FileNotFoundInVault, match="not found"):
            register_external(tmp_path / "ghost.md")


class TestApi:
    def test_open_outside_roots_registers_and_pends(self, ext_vault, outside_md: Path):
        client = TestClient(app)
        res = client.post("/api/open", json={"abs_path": str(outside_md)})
        assert res.status_code == 200
        virtual = res.json()["path"]
        assert virtual.startswith("ext://")
        # pending으로 전달된다
        assert client.get("/api/open/pending").json()["path"] == virtual
        # 등록된 경로는 /api/file로 읽힌다
        res = client.get("/api/file", params={"path": virtual})
        assert res.status_code == 200
        assert res.json()["title"] == "외부 문서"

    def test_open_inside_roots_unchanged(self, ext_vault, tmp_path: Path):
        client = TestClient(app)
        inside = tmp_path / "vault" / "inside.md"
        res = client.post("/api/open", json={"abs_path": str(inside)})
        assert res.json()["path"] == "vault://inside.md"

    def test_file_unregistered_ext_404(self, ext_vault, outside_md: Path):
        client = TestClient(app)
        res = client.get("/api/file", params={"path": f"ext://{outside_md.resolve()}"})
        assert res.status_code == 404

    def test_open_missing_file_404(self, ext_vault, tmp_path: Path):
        client = TestClient(app)
        res = client.post("/api/open", json={"abs_path": str(tmp_path / "nope.md")})
        assert res.status_code == 404

    def test_registered_then_deleted_file_404(self, ext_vault, outside_md: Path):
        client = TestClient(app)
        virtual = client.post("/api/open", json={"abs_path": str(outside_md)}).json()["path"]
        outside_md.unlink()
        res = client.get("/api/file", params={"path": virtual})
        assert res.status_code == 404
