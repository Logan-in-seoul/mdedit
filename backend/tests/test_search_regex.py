"""정규식 검색 모드(regex=true) 테스트: 매치, 필터, 안전장치, 한도, 랭킹, API."""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import index as fts_index
from app.main import app, set_config
from app.schema import AppConfig, RootConfig


@pytest.fixture
def vault(tmp_path: Path) -> AppConfig:
    root = tmp_path / "common"
    root.mkdir()
    (root / "invoice.md").write_text(
        "# 인보이스\n\nINV-2024-001 발행\nINV-2025-017 취소\n", encoding="utf-8"
    )
    (root / "notes.md").write_text(
        "# 메모\n\n회의 2024-03-05 진행\n담당자 kim@example.com\n", encoding="utf-8"
    )
    old = root / "old.md"
    old.write_text("# 옛 문서\n\nINV-1999-001 기록\n", encoding="utf-8")
    os.utime(old, (time.time() - 90 * 86400,) * 2)
    fts_index.init_db(tmp_path / "state")
    cfg = AppConfig(roots=[RootConfig(name="common", path=root)])
    fts_index.refresh(cfg)
    return cfg


def paths(res) -> list[str]:
    return [h.path for h in res.hits]


def test_regex_matches_pattern(vault):
    res = fts_index.search(vault, r"INV-\d{4}-\d{3}", regex=True)
    assert res.total == 3
    snippets = [h.snippet[h.match_start:h.match_end] for h in res.hits]
    assert sorted(snippets) == ["INV-1999-001", "INV-2024-001", "INV-2025-017"]


def test_regex_case_insensitive_and_korean(vault):
    assert fts_index.search(vault, r"inv-2024", regex=True).total == 1
    assert fts_index.search(vault, r"회의\s+\d{4}", regex=True).total == 1


def test_regex_does_not_parse_operators(vault):
    # 정규식 모드에서 `tag:` 같은 접두어는 패턴의 일부다
    assert fts_index.search(vault, r"path:x", regex=True).total == 0


def test_regex_explicit_path_filter(vault):
    res = fts_index.search(vault, r"\d{4}", regex=True, path_filter="notes")
    assert set(paths(res)) == {"common://notes.md"}


def test_regex_empty_and_empty_match(vault):
    assert fts_index.search(vault, "  ", regex=True).total == 0
    assert fts_index.search(vault, r"x*", regex=True).total == 0  # 빈 매치는 무시


def test_regex_ranking_recent_first(vault):
    res = fts_index.search(vault, r"INV-\d+-\d+", regex=True)
    assert res.hits[0].path == "common://invoice.md"
    assert res.hits[-1].path == "common://old.md"


def test_regex_title_boost(vault):
    res = fts_index.search(vault, r"인보이스|2024", regex=True)
    assert res.hits[0].path == "common://invoice.md"


def test_regex_max_hits_truncates(vault):
    res = fts_index.search(vault, r"\d{4}", regex=True, max_hits=2)
    assert len(res.hits) == 2
    assert res.truncated is True
    assert res.total >= 4


def test_regex_per_file_cap(tmp_path: Path):
    root = tmp_path / "common"
    root.mkdir()
    (root / "a.md").write_text("\n".join(f"line{i} foo" for i in range(20)), encoding="utf-8")
    fts_index.init_db(tmp_path / "state")
    cfg = AppConfig(roots=[RootConfig(name="common", path=root)])
    fts_index.refresh(cfg)
    res = fts_index.search(cfg, r"foo", regex=True, max_per_file=3)
    assert len(res.hits) == 3


@pytest.mark.parametrize(
    "pattern",
    [r"(a+)+$", r"(a*)*b", r"(a|aa)+", r"(\w+)\1", r"a" * 201, r"(unclosed", r"a*b*c*d*"],
)
def test_unsafe_or_invalid_patterns_rejected(vault, pattern):
    with pytest.raises(fts_index.RegexSearchError):
        fts_index.search(vault, pattern, regex=True)


def test_safe_patterns_accepted():
    for p in [r"\d{1,3}", r"foo.*bar", r"(?:foo|bar)\d", r"^#+\s", r"a{2,50}"]:
        fts_index.compile_safe_regex(p)


def test_time_budget_returns_truncated(vault, monkeypatch):
    monkeypatch.setattr(fts_index, "REGEX_TIME_BUDGET", -1.0)
    res = fts_index.search(vault, r"INV", regex=True)
    assert res.truncated is True


def test_long_lines_are_capped(tmp_path: Path):
    root = tmp_path / "common"
    root.mkdir()
    (root / "a.md").write_text("x" * 1000 + "NEEDLE\n", encoding="utf-8")
    fts_index.init_db(tmp_path / "state")
    cfg = AppConfig(roots=[RootConfig(name="common", path=root)])
    fts_index.refresh(cfg)
    assert fts_index.search(cfg, "NEEDLE", regex=True).total == 0


def test_non_regex_default_unchanged(vault):
    # regex 미지정 시 `.`은 리터럴 취급 (기존 trigram 경로)
    assert fts_index.search(vault, "INV.2024").total == 0


class TestApi:
    @pytest.fixture
    def client(self, vault) -> TestClient:
        set_config(vault)
        return TestClient(app)

    def test_api_regex_ok(self, client):
        r = client.get("/api/search", params={"q": r"INV-\d{4}", "regex": "true"})
        assert r.status_code == 200
        assert r.json()["total"] == 3

    def test_api_regex_rejects_catastrophic(self, client):
        r = client.get("/api/search", params={"q": "(a+)+$", "regex": "true"})
        assert r.status_code == 400

    def test_api_regex_default_off(self, client):
        r = client.get("/api/search", params={"q": r"INV-\d{4}"})
        assert r.status_code == 200
        assert r.json()["total"] == 0
