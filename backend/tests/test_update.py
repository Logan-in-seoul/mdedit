"""업데이트 체크 테스트 (v0.7). 네트워크는 monkeypatch로 차단."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import update
from app.main import app


@pytest.fixture(autouse=True)
def _clean_cache():
    update.reset_cache()
    yield
    update.reset_cache()


class TestSemver:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("v0.7.0", (0, 7, 0)),
            ("0.7.0", (0, 7, 0)),
            ("v0.10.1", (0, 10, 1)),
            ("1.0", (1, 0)),
            ("garbage", (0,)),
        ],
    )
    def test_parse_version(self, raw, expected):
        assert update.parse_version(raw) == expected

    def test_is_newer_basic(self):
        assert update.is_newer("v0.8.0", "0.7.0") is True
        assert update.is_newer("v0.7.0", "0.7.0") is False
        assert update.is_newer("v0.6.0", "0.7.0") is False

    def test_is_newer_double_digit(self):
        # 문자열 비교였다면 0.10.0 < 0.9.0으로 틀렸을 케이스
        assert update.is_newer("v0.10.0", "0.9.0") is True


class TestCheck:
    def test_update_available(self, monkeypatch):
        monkeypatch.setattr(update, "_fetch_latest_tag", lambda timeout=3.0: "v9.9.9")
        res = update.check("0.7.0")
        assert res["update_available"] is True
        assert res["latest"] == "v9.9.9"

    def test_up_to_date(self, monkeypatch):
        monkeypatch.setattr(update, "_fetch_latest_tag", lambda timeout=3.0: "v0.7.0")
        res = update.check("0.7.0")
        assert res["update_available"] is False

    def test_offline_silent(self, monkeypatch):
        monkeypatch.setattr(update, "_fetch_latest_tag", lambda timeout=3.0: None)
        res = update.check("0.7.0")
        assert res["update_available"] is False
        assert res["latest"] is None

    def test_result_cached(self, monkeypatch):
        calls = {"n": 0}

        def fake(timeout=3.0):
            calls["n"] += 1
            return "v9.9.9"

        monkeypatch.setattr(update, "_fetch_latest_tag", fake)
        update.check("0.7.0")
        update.check("0.7.0")
        assert calls["n"] == 1, "1시간 내 재호출은 캐시를 써야 한다"


class TestEndpoint:
    def test_update_check_endpoint(self, monkeypatch):
        monkeypatch.setattr(update, "_fetch_latest_tag", lambda timeout=3.0: "v9.9.9")
        client = TestClient(app)
        res = client.get("/api/update-check")
        assert res.status_code == 200
        body = res.json()
        assert body["update_available"] is True
        assert body["current"] == app.version
        assert body["url"].startswith("https://github.com/")
