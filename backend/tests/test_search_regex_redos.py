"""정규식 검색 ReDoS 방어 테스트.

`compile_safe_regex`를 통과하는 다항식/지수 백트래킹 패턴이 실제 서버에서
시간 예산 안에 끊기는지, 그동안 다른 엔드포인트가 막히지 않는지를 실서버(uvicorn
스레드)로 검증한다. 수정 전에는 아래 패턴 하나가 라인 하나에서 4초~무한대로
GIL을 쥐어 서버 전체가 멈췄다.
"""
from __future__ import annotations

import json
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest
import uvicorn

from app import index as fts_index
from app import regex_worker
from app.main import app, set_config
from app.schema import AppConfig, RootConfig

BUDGET = 0.5
# 응답 상한: 예산 + 강제 종료 여유 + CI 지터
RESPONSE_LIMIT = BUDGET + regex_worker.KILL_GRACE + 1.0

REDOS_PATTERNS = [
    r"(.*)(.*)(.*)\d",
    r"(?:.{1,99}){1,99}\x00",
    r"a*a*a*b",
]


@pytest.fixture
def base_url(tmp_path: Path, monkeypatch):
    root = tmp_path / "common"
    root.mkdir()
    # 숫자·b·NUL이 없는 긴 라인 — 위 패턴들이 매치에 실패하며 끝까지 백트래킹한다
    (root / "evil.md").write_text("\n".join(["a" * 400] * 20) + "\n", encoding="utf-8")
    (root / "ok.md").write_text("# 정상\n\nINV-2024-001 발행\n", encoding="utf-8")
    fts_index.init_db(tmp_path / "state")
    cfg = AppConfig(roots=[RootConfig(name="common", path=root)])
    fts_index.refresh(cfg)
    set_config(cfg)
    monkeypatch.setattr(fts_index, "REGEX_TIME_BUDGET", BUDGET)

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 10
    while not server.started:
        assert time.monotonic() < deadline, "server did not start"
        time.sleep(0.01)
    # 워커 기동(최초 1회)은 예산 밖이므로 미리 데워 타이밍 측정에서 뺀다
    _get(url, "/api/search", q="INV", regex="true")
    yield url
    server.should_exit = True
    thread.join(5)
    sock.close()
    regex_worker.shutdown()


def _get(base: str, path: str, **params) -> tuple[int, dict, float]:
    url = base + path + ("?" + urllib.parse.urlencode(params) if params else "")
    start = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=30) as res:
            status, body = res.status, json.load(res)
    except urllib.error.HTTPError as exc:
        status, body = exc.code, json.load(exc)
    return status, body, time.monotonic() - start


@pytest.mark.parametrize("pattern", REDOS_PATTERNS)
def test_redos_pattern_is_cut_off_and_server_stays_responsive(base_url, pattern):
    result: dict = {}

    def run_search() -> None:
        result["res"] = _get(base_url, "/api/search", q=pattern, regex="true")

    t = threading.Thread(target=run_search)
    t.start()
    time.sleep(0.1)  # 워커가 백트래킹에 들어간 뒤
    health_times = []
    while t.is_alive():
        status, body, took = _get(base_url, "/api/health")
        assert status == 200 and body == {"status": "ok"}
        health_times.append(took)
        time.sleep(0.05)
    t.join()

    status, body, took = result["res"]
    assert took < RESPONSE_LIMIT, f"{pattern!r} took {took:.2f}s"
    # 1차 방어가 거부(400)하든 워커가 끊든(200+truncated) 둘 다 허용 — 멈추지만 않으면 된다
    assert status in (200, 400)
    if status == 200:
        assert body["truncated"] is True
        assert body["truncated_reason"] == "timeout"
    assert health_times, "health was never probed during the search"
    assert max(health_times) < 0.5, f"health blocked for {max(health_times):.2f}s"


def test_search_works_again_after_worker_was_killed(base_url):
    status, body, _ = _get(base_url, "/api/search", q=r"(?:.{1,99}){1,99}\x00", regex="true")
    assert status == 200 and body["truncated_reason"] == "timeout"
    status, body, _ = _get(base_url, "/api/search", q=r"INV-\d{4}", regex="true")
    assert status == 200
    assert body["total"] == 1 and body["truncated"] is False
    assert body["truncated_reason"] is None


def test_concurrent_regex_searches_are_all_bounded(base_url):
    results: list = []

    def run() -> None:
        results.append(_get(base_url, "/api/search", q=r"a*a*a*b", regex="true"))

    threads = [threading.Thread(target=run) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(results) == 8
    for status, body, took in results:
        assert status == 200
        assert body["truncated_reason"] in ("timeout", "busy")
        assert took < RESPONSE_LIMIT, f"took {took:.2f}s"


def test_variable_width_lookbehind_is_400_not_500(base_url):
    status, _, _ = _get(base_url, "/api/search", q=r"(?<=a+)b", regex="true")
    assert status == 400


def test_limit_has_upper_bound(base_url):
    assert _get(base_url, "/api/search", q="INV", limit="1000")[0] == 200
    assert _get(base_url, "/api/search", q="INV", limit="1001")[0] == 422
    assert _get(base_url, "/api/search", q="INV", limit="0")[0] == 422
