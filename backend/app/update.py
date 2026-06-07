"""업데이트 체크 — GitHub 최신 릴리스와 현재 버전 비교 (v0.7).

네트워크 실패는 조용히 삼킨다 (update_available=False).
결과는 1시간 캐시해 GitHub API rate limit을 피한다.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.request

RELEASES_API = "https://api.github.com/repos/Logan-in-seoul/mdedit/releases/latest"
RELEASES_URL = "https://github.com/Logan-in-seoul/mdedit/releases/latest"
CACHE_TTL = 3600.0

_cache: dict | None = None
_cache_at: float = 0.0
_lock = threading.Lock()


def parse_version(v: str) -> tuple[int, ...]:
    """'v0.10.1' / '0.10.1' → (0, 10, 1). 파싱 불가 토큰은 0."""
    parts = v.strip().lstrip("vV").split(".")
    out = []
    for p in parts:
        digits = "".join(ch for ch in p if ch.isdigit())
        out.append(int(digits) if digits else 0)
    return tuple(out) if out else (0,)


def is_newer(latest: str, current: str) -> bool:
    return parse_version(latest) > parse_version(current)


def _fetch_latest_tag(timeout: float = 3.0) -> str | None:
    try:
        req = urllib.request.Request(
            RELEASES_API, headers={"Accept": "application/vnd.github+json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return json.load(res).get("tag_name")
    except Exception:
        return None


def check(current: str) -> dict:
    """현재 버전과 최신 릴리스를 비교한다. 1시간 캐시."""
    global _cache, _cache_at
    with _lock:
        if _cache is not None and time.monotonic() - _cache_at < CACHE_TTL:
            return _cache

    latest = _fetch_latest_tag()
    result = {
        "current": current,
        "latest": latest,
        "update_available": bool(latest and is_newer(latest, current)),
        "url": RELEASES_URL,
    }
    with _lock:
        _cache, _cache_at = result, time.monotonic()
    return result


def reset_cache() -> None:
    """테스트용 캐시 초기화."""
    global _cache, _cache_at
    with _lock:
        _cache, _cache_at = None, 0.0
