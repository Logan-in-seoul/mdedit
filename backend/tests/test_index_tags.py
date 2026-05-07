"""FTS5 tag indexing 통합 테스트 (P3 step 2).

실제 SQLite + FTS5를 사용해 tag 컬럼이 인덱싱·검색되는지 검증한다.
mock 없이 tmp_path에 실 DB를 띄워 라운드트립을 본다.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app import index as fts_index
from app.schema import AppConfig, RootConfig


@pytest.fixture
def tagged_vault(tmp_path: Path) -> AppConfig:
    """태그가 포함된 .md 파일 3개를 만든 vault."""
    root = tmp_path / "common"
    root.mkdir()
    (root / "alpha.md").write_text(
        "# Alpha\n\n작업 #project/guidedtour 진행중. #회고 적기.\n",
        encoding="utf-8",
    )
    (root / "beta.md").write_text(
        "# Beta\n\n#project/atom 빌드. #release 후보.\n",
        encoding="utf-8",
    )
    (root / "gamma.md").write_text(
        "# Gamma\n\n태그 없는 일반 본문.\n",
        encoding="utf-8",
    )
    fts_index.init_db(tmp_path / "state")
    cfg = AppConfig(roots=[RootConfig(name="common", path=root)])
    fts_index.refresh(cfg)
    return cfg


class TestTagSchema:
    def test_tag_column_table_exists(self, tagged_vault: AppConfig):
        db = fts_index.get_db()
        rows = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='file_tags'"
        ).fetchall()
        assert rows, "file_tags FTS5 table must exist after init"

    def test_tags_stored_for_indexed_file(self, tagged_vault: AppConfig):
        db = fts_index.get_db()
        row = db.execute(
            "SELECT tags FROM file_tags WHERE path = ?",
            ("common://alpha.md",),
        ).fetchone()
        assert row is not None
        tags = row[0].split()
        assert "project/guidedtour" in tags
        assert "회고" in tags

    def test_files_without_tags_have_empty_row(self, tagged_vault: AppConfig):
        db = fts_index.get_db()
        row = db.execute(
            "SELECT tags FROM file_tags WHERE path = ?",
            ("common://gamma.md",),
        ).fetchone()
        assert row is not None
        assert row[0] == ""


class TestTagSearch:
    def test_filter_by_tag_returns_only_matching_file(self, tagged_vault: AppConfig):
        result = fts_index.search(tagged_vault, query="", tag="회고")
        paths = [h.path for h in result.hits]
        assert "common://alpha.md" in paths
        assert "common://beta.md" not in paths

    def test_tag_prefix_in_query_filters(self, tagged_vault: AppConfig):
        # query "tag:release foo" should narrow to files with tag release
        result = fts_index.search(tagged_vault, query="tag:release")
        paths = [h.path for h in result.hits]
        assert "common://beta.md" in paths
        assert "common://alpha.md" not in paths

    def test_hierarchical_tag_match(self, tagged_vault: AppConfig):
        result = fts_index.search(tagged_vault, query="", tag="project/guidedtour")
        paths = [h.path for h in result.hits]
        assert "common://alpha.md" in paths
        assert "common://beta.md" not in paths

    def test_tag_filter_combined_with_text_search(self, tagged_vault: AppConfig):
        # text "Alpha" + tag "회고" → alpha matches
        result = fts_index.search(tagged_vault, query="Alpha", tag="회고")
        paths = [h.path for h in result.hits]
        assert "common://alpha.md" in paths

    def test_unknown_tag_yields_empty(self, tagged_vault: AppConfig):
        result = fts_index.search(tagged_vault, query="", tag="nonexistent")
        assert result.hits == []
        assert result.total == 0


class TestMigrationIdempotent:
    def test_init_db_repeated_safe(self, tmp_path: Path):
        state = tmp_path / "state"
        fts_index.init_db(state)
        fts_index.init_db(state)  # second call must not crash
        db = fts_index.get_db()
        rows = db.execute(
            "SELECT name FROM sqlite_master WHERE name IN ('file_tags','lines_fts','files')"
        ).fetchall()
        names = {r[0] for r in rows}
        assert {"file_tags", "lines_fts", "files"}.issubset(names)


class TestRefreshKeepsTagsInSync:
    """파일이 수정되어 mtime 변경 후 refresh 호출 시 tags가 갱신되는지."""

    def test_tags_updated_after_file_rewrite(self, tmp_path: Path):
        root = tmp_path / "common"
        root.mkdir()
        target = root / "shifty.md"
        target.write_text("# Shifty\n#alpha note\n", encoding="utf-8")
        fts_index.init_db(tmp_path / "state")
        cfg = AppConfig(roots=[RootConfig(name="common", path=root)])
        fts_index.refresh(cfg)

        # rewrite with different tags + force later mtime
        import os
        target.write_text("# Shifty\n#beta updated\n", encoding="utf-8")
        future = target.stat().st_mtime + 5
        os.utime(target, (future, future))
        fts_index.refresh(cfg)

        db = fts_index.get_db()
        row = db.execute(
            "SELECT tags FROM file_tags WHERE path = ?",
            ("common://shifty.md",),
        ).fetchone()
        assert row is not None
        assert "beta" in row[0]
        assert "alpha" not in row[0]


# ---------------------------------------------------------------------------
# D-5: path: / type: 검색 연산자 테스트
# ---------------------------------------------------------------------------


@pytest.fixture
def operator_vault(tmp_path: Path) -> AppConfig:
    """path: / type: 연산자 테스트용 vault.

    디렉터리 구조:
      memory/user_logan.md   — frontmatter: type: user
      memory/feedback_x.md   — frontmatter: type: feedback, 본문에 #feedback
      skills/deploy.md       — frontmatter: type: skill
    """
    root = tmp_path / "vault"
    root.mkdir()
    mem = root / "memory"
    mem.mkdir()
    (mem / "user_logan.md").write_text(
        "---\ntype: user\n---\n# Logan 프로필\n사용자 프로필 문서.\n",
        encoding="utf-8",
    )
    (mem / "feedback_x.md").write_text(
        "---\ntype: feedback\n---\n# Feedback X\n#feedback 항목.\n",
        encoding="utf-8",
    )
    skills = root / "skills"
    skills.mkdir()
    (skills / "deploy.md").write_text(
        "---\ntype: skill\n---\n# Deploy Skill\n배포 자동화 스킬.\n",
        encoding="utf-8",
    )
    fts_index.init_db(tmp_path / "state")
    cfg = AppConfig(roots=[RootConfig(name="vault", path=root)])
    fts_index.refresh(cfg)
    return cfg


class TestPathFilterOperator:
    def test_path_filter_narrows_to_directory(self, operator_vault: AppConfig):
        result = fts_index.search(operator_vault, query="path:memory")
        paths = [h.path for h in result.hits]
        assert any("memory" in p for p in paths)
        assert not any("skills" in p for p in paths)

    def test_path_filter_returns_empty_for_nonexistent_dir(self, operator_vault: AppConfig):
        result = fts_index.search(operator_vault, query="path:nonexistent")
        assert result.total == 0
        assert result.hits == []

    def test_path_filter_combined_with_text(self, operator_vault: AppConfig):
        result = fts_index.search(operator_vault, query="Logan path:memory")
        paths = [h.path for h in result.hits]
        assert any("user_logan" in p for p in paths)
        assert not any("skills" in p for p in paths)

    def test_path_filter_via_query_string_prefix(self, operator_vault: AppConfig):
        # 쿼리 문자열에 path: 연산자 포함
        result = fts_index.search(operator_vault, query="path:skills")
        paths = [h.path for h in result.hits]
        assert any("skills" in p for p in paths)
        assert not any("memory" in p for p in paths)


class TestTypeFilterOperator:
    def test_type_filter_returns_only_matching_type(self, operator_vault: AppConfig):
        result = fts_index.search(operator_vault, query="", type_filter="user")
        paths = [h.path for h in result.hits]
        assert any("user_logan" in p for p in paths)
        assert not any("feedback" in p for p in paths)
        assert not any("deploy" in p for p in paths)

    def test_type_filter_feedback(self, operator_vault: AppConfig):
        result = fts_index.search(operator_vault, query="", type_filter="feedback")
        paths = [h.path for h in result.hits]
        assert any("feedback_x" in p for p in paths)
        assert not any("user_logan" in p for p in paths)

    def test_type_filter_unknown_returns_empty(self, operator_vault: AppConfig):
        result = fts_index.search(operator_vault, query="", type_filter="nonexistent")
        assert result.hits == []

    def test_type_via_query_prefix(self, operator_vault: AppConfig):
        result = fts_index.search(operator_vault, query="type:skill")
        paths = [h.path for h in result.hits]
        assert any("deploy" in p for p in paths)
        assert not any("user_logan" in p for p in paths)

    def test_type_indexed_in_tags_blob(self, operator_vault: AppConfig):
        db = fts_index.get_db()
        row = db.execute(
            "SELECT tags FROM file_tags WHERE path = ?",
            ("vault://memory/user_logan.md",),
        ).fetchone()
        assert row is not None
        assert "type:user" in row[0].split()


class TestCombinedOperators:
    def test_path_and_type_intersection(self, operator_vault: AppConfig):
        # memory 디렉터리 + type:feedback → feedback_x.md만
        result = fts_index.search(
            operator_vault, query="", path_filter="memory", type_filter="feedback"
        )
        paths = [h.path for h in result.hits]
        assert any("feedback_x" in p for p in paths)
        assert not any("user_logan" in p for p in paths)

    def test_path_and_type_no_intersection_returns_empty(self, operator_vault: AppConfig):
        # skills 디렉터리에는 type:user 없음
        result = fts_index.search(
            operator_vault, query="", path_filter="skills", type_filter="user"
        )
        assert result.hits == []

    def test_operator_prefix_extraction_leaves_text_intact(self, operator_vault: AppConfig):
        # "프로필 path:memory" → 텍스트 "프로필"로 memory 내 검색
        result = fts_index.search(operator_vault, query="프로필 path:memory")
        paths = [h.path for h in result.hits]
        assert any("user_logan" in p for p in paths)


# ---------------------------------------------------------------------------
# D-4: 검색 결과 line 번호 포함 검증 (백엔드)
# ---------------------------------------------------------------------------


class TestSearchLineNumbers:
    def test_search_hit_contains_line_number(self, operator_vault: AppConfig):
        result = fts_index.search(operator_vault, query="Logan")
        assert result.total > 0
        hit = result.hits[0]
        assert hit.line >= 1, "검색 히트에 line 번호(≥1)가 있어야 한다"

    def test_line_number_points_to_correct_content(self, operator_vault: AppConfig):
        result = fts_index.search(operator_vault, query="배포")
        assert result.total > 0
        hit = result.hits[0]
        # deploy.md의 "배포 자동화 스킬." 라인은 frontmatter 이후
        assert hit.line >= 3

    def test_snippet_and_match_coords_are_consistent(self, operator_vault: AppConfig):
        result = fts_index.search(operator_vault, query="프로필")
        assert result.total > 0
        for hit in result.hits:
            assert 0 <= hit.match_start <= hit.match_end <= len(hit.snippet)
