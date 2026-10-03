from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import mount_static


def _client(tmp_path: Path) -> TestClient:
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "fonts" / "pretendard").mkdir(parents=True)
    (static / "index.html").write_text("<html>spa</html>", encoding="utf-8")
    (static / "fonts" / "pretendard" / "pretendard.css").write_text("/* css */", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
    app = FastAPI()
    mount_static(app, static)
    return TestClient(app)


def test_serves_nested_public_file(tmp_path: Path):
    r = _client(tmp_path).get("/fonts/pretendard/pretendard.css")
    assert r.status_code == 200
    assert r.text == "/* css */"


def test_unknown_path_falls_back_to_index(tmp_path: Path):
    r = _client(tmp_path).get("/some/note/route")
    assert r.status_code == 200
    assert "spa" in r.text


def test_path_traversal_is_not_served(tmp_path: Path):
    r = _client(tmp_path).get("/..%2Fsecret.txt")
    assert "secret" not in r.text


def test_api_prefix_stays_404(tmp_path: Path):
    assert _client(tmp_path).get("/api/nope").status_code == 404
