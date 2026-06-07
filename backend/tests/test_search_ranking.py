"""검색 랭킹 점수 모델 테스트 (v0.5.0).

bm25 단독 정렬이 짧은 스쳐가는 언급을 본문 문서보다 위에 두는 문제를
백엔드 점수 모델(제목/파일명/경로 매치 + 최근성 부스트)이 해결하는지 검증한다.
실제 SQLite + FTS5 라운드트립.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from app import index as fts_index
from app.schema import AppConfig, RootConfig


@pytest.fixture
def ranking_vault(tmp_path: Path) -> AppConfig:
    root = tmp_path / "common"
    root.mkdir()
    # 제목에 검색어가 있는 본문 문서
    (root / "guide.md").write_text(
        "# Airwallex 가이드\n\n"
        "Airwallex 결제 연동 절차를 정리한다.\n"
        "계정 생성 후 Airwallex 대시보드에서 API 키를 발급한다.\n",
        encoding="utf-8",
    )
    # 스쳐가는 한 줄 언급 (라인 단위 bm25는 이런 짧은 줄을 높게 친다)
    (root / "weekly.md").write_text(
        "# 주간 회고\n\n할 일: Airwallex\n다른 내용이 길게 이어진다.\n",
        encoding="utf-8",
    )
    # 파일명에 검색어가 있는 문서 (제목/본문 첫 줄엔 없음)
    (root / "stripe-notes.md").write_text(
        "# 결제 메모\n\nstripe 연동 관련 메모.\n",
        encoding="utf-8",
    )
    (root / "etc.md").write_text(
        "# 기타\n\nstripe 잠깐 언급.\n",
        encoding="utf-8",
    )
    fts_index.init_db(tmp_path / "state")
    cfg = AppConfig(roots=[RootConfig(name="common", path=root)])
    fts_index.refresh(cfg)
    return cfg


class TestTitleColumn:
    def test_title_stored_on_index(self, ranking_vault: AppConfig):
        db = fts_index.get_db()
        row = db.execute(
            "SELECT title FROM files WHERE path = ?", ("common://guide.md",)
        ).fetchone()
        assert row[0] == "Airwallex 가이드"

    def test_title_none_when_no_h1(self, tmp_path: Path):
        root = tmp_path / "common"
        root.mkdir()
        (root / "plain.md").write_text("그냥 본문만 있는 파일\n", encoding="utf-8")
        fts_index.init_db(tmp_path / "state")
        cfg = AppConfig(roots=[RootConfig(name="common", path=root)])
        fts_index.refresh(cfg)
        row = fts_index.get_db().execute(
            "SELECT title FROM files WHERE path = ?", ("common://plain.md",)
        ).fetchone()
        assert row[0] is None


class TestRanking:
    def test_title_match_beats_passing_mention(self, ranking_vault: AppConfig):
        res = fts_index.search(ranking_vault, "Airwallex")
        assert res.hits, "검색 결과가 있어야 한다"
        assert res.hits[0].path == "common://guide.md", (
            "제목 매치 문서가 한 줄 언급 문서보다 위여야 한다"
        )

    def test_filename_match_boost(self, ranking_vault: AppConfig):
        res = fts_index.search(ranking_vault, "stripe")
        assert res.hits
        assert res.hits[0].path == "common://stripe-notes.md", (
            "파일명 매치 문서가 본문 언급 문서보다 위여야 한다"
        )

    def test_hits_within_file_are_line_ordered(self, ranking_vault: AppConfig):
        res = fts_index.search(ranking_vault, "Airwallex")
        guide_lines = [h.line for h in res.hits if h.path == "common://guide.md"]
        assert guide_lines == sorted(guide_lines)

    def test_file_hits_are_contiguous(self, ranking_vault: AppConfig):
        """파일 그룹 정렬: 같은 파일의 hit은 연속으로 나온다."""
        res = fts_index.search(ranking_vault, "Airwallex")
        seen: list[str] = []
        for h in res.hits:
            if not seen or seen[-1] != h.path:
                seen.append(h.path)
        assert len(seen) == len(set(seen)), "파일이 결과에서 흩어지면 안 된다"

    def test_recency_boost(self, tmp_path: Path):
        root = tmp_path / "common"
        root.mkdir()
        old = root / "old.md"
        new = root / "new.md"
        # 동일한 내용 — bm25 동률, 최근성만 차이
        old.write_text("# 메모\n\nkubernetes 설정 정리.\n", encoding="utf-8")
        new.write_text("# 메모\n\nkubernetes 설정 정리.\n", encoding="utf-8")
        past = time.time() - 60 * 86400
        os.utime(old, (past, past))
        fts_index.init_db(tmp_path / "state")
        cfg = AppConfig(roots=[RootConfig(name="common", path=root)])
        fts_index.refresh(cfg)
        res = fts_index.search(cfg, "kubernetes")
        assert res.hits[0].path == "common://new.md", (
            "최근 수정 문서가 위여야 한다"
        )


class TestMigration:
    def test_old_schema_gets_title_column(self, tmp_path: Path):
        """title 컬럼 없는 구버전 DB가 init_db에서 마이그레이션된다."""
        import sqlite3

        state = tmp_path / "state"
        state.mkdir(parents=True)
        db = sqlite3.connect(str(state / "index.db"))
        db.execute(
            "CREATE TABLE files (path TEXT PRIMARY KEY, name TEXT NOT NULL,"
            " mtime INTEGER NOT NULL, size INTEGER NOT NULL)"
        )
        db.execute(
            "INSERT INTO files VALUES ('common://a.md', 'a.md', 12345, 10)"
        )
        db.commit()
        db.close()

        fts_index.init_db(state)
        rows = fts_index.get_db().execute(
            "SELECT title, mtime FROM files"
        ).fetchall()
        assert rows == [(None, 0)], "title 컬럼 추가 + mtime 무효화(재인덱싱 유도)"
