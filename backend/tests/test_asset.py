"""문서 안 그림 서빙 (/api/asset, v0.11).

실제 문서처럼 중첩 폴더 아래 workflows/<주제>/fig.png 를 상대 경로로 거는 형태를 픽스처로 쓴다.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import fs
from app.fs import register_external
from app.main import app, set_config
from app.schema import AppConfig, RootConfig

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "home"
    fig_dir = root / "workspace" / "cms" / "docs" / "workflows" / "best-price"
    fig_dir.mkdir(parents=True)
    (fig_dir / "fig1-flow.png").write_bytes(PNG)
    (fig_dir / "chart.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
    (root / "workspace" / "cms" / "docs" / "prd.md").write_text("# prd", encoding="utf-8")
    (root / "secret.env").write_text("TOKEN=x", encoding="utf-8")
    set_config(AppConfig(roots=[RootConfig(name="home", path=root)]))
    return root


@pytest.fixture(autouse=True)
def _clean_registry():
    fs._EXTERNAL_FILES.clear()
    yield
    fs._EXTERNAL_FILES.clear()


client = TestClient(app)


def test_serves_png_inside_root(vault: Path) -> None:
    r = client.get("/api/asset", params={"path": "home://workspace/cms/docs/workflows/best-price/fig1-flow.png"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content == PNG
    assert r.headers["cache-control"] == "no-cache"


def test_svg_gets_script_blocking_csp(vault: Path) -> None:
    r = client.get("/api/asset", params={"path": "home://workspace/cms/docs/workflows/best-price/chart.svg"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert "sandbox" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"


def test_rejects_non_media_file(vault: Path) -> None:
    r = client.get("/api/asset", params={"path": "home://secret.env"})
    assert r.status_code == 404


def test_rejects_escape_from_root(vault: Path) -> None:
    r = client.get("/api/asset", params={"path": "home://../outside.png"})
    assert r.status_code == 404


def test_abs_path_inside_root(vault: Path) -> None:
    p = vault / "workspace" / "cms" / "docs" / "workflows" / "best-price" / "fig1-flow.png"
    r = client.get("/api/asset", params={"abs": str(p)})
    assert r.status_code == 200


def test_abs_path_outside_root_rejected(vault: Path, tmp_path: Path) -> None:
    other = tmp_path / "other" / "x.png"
    other.parent.mkdir()
    other.write_bytes(PNG)
    r = client.get("/api/asset", params={"abs": str(other)})
    assert r.status_code == 404


def test_external_doc_folder_assets(vault: Path, tmp_path: Path) -> None:
    doc = tmp_path / "elsewhere" / "draft.md"
    (doc.parent / "img").mkdir(parents=True)
    doc.write_text("# draft", encoding="utf-8")
    (doc.parent / "img" / "a.png").write_bytes(PNG)
    unregistered = client.get("/api/asset", params={"path": f"ext://{doc.parent / 'img' / 'a.png'}"})
    assert unregistered.status_code == 404
    register_external(doc)
    r = client.get("/api/asset", params={"path": f"ext://{doc.parent / 'img' / 'a.png'}"})
    assert r.status_code == 200


def test_missing_file_404(vault: Path) -> None:
    r = client.get("/api/asset", params={"path": "home://workspace/none.png"})
    assert r.status_code == 404
