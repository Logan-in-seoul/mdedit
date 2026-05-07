"""Tag extraction unit tests (TDD red phase first)."""
from __future__ import annotations

import pytest

from app.tags import extract_tags


class TestBasicExtraction:
    def test_single_tag_in_paragraph(self):
        assert extract_tags("hello #foo world") == ["foo"]

    def test_multiple_tags_dedupe_preserve_order(self):
        assert extract_tags("#a #b #a #c") == ["a", "b", "c"]

    def test_no_tags_returns_empty(self):
        assert extract_tags("plain text without anything") == []

    def test_tag_at_line_start(self):
        assert extract_tags("#start of line") == ["start"]

    def test_empty_string(self):
        assert extract_tags("") == []


class TestHierarchical:
    def test_nested_tag_with_slash(self):
        assert extract_tags("see #project/guidedtour") == ["project/guidedtour"]

    def test_deep_nested_tag(self):
        assert extract_tags("#a/b/c") == ["a/b/c"]


class TestKorean:
    def test_korean_tag_allowed(self):
        assert extract_tags("작업 #회고 끝") == ["회고"]

    def test_mixed_korean_alnum(self):
        assert extract_tags("#가이드투어-MVP") == ["가이드투어-MVP"]


class TestExclusion:
    def test_hash_only_no_letters_excluded(self):
        # ## H2 헤딩은 태그 아님
        assert extract_tags("## section title") == []

    def test_url_fragment_not_a_tag(self):
        assert extract_tags("see https://example.com/page#section") == []

    def test_inline_code_excluded(self):
        assert extract_tags("use `#tagged` literal") == []

    def test_fenced_code_block_excluded(self):
        src = "before #real\n```\n#fake\n```\nafter #also"
        assert extract_tags(src) == ["real", "also"]

    def test_yaml_frontmatter_excluded(self):
        src = "---\ntitle: foo\nbody: '#nope'\n---\n\n#real"
        assert extract_tags(src) == ["real"]

    def test_email_with_hash_not_tag(self):
        assert extract_tags("test@example.com#anchor") == []

    def test_numeric_only_after_hash_excluded(self):
        # #123 은 이슈번호처럼 읽힘 - 태그로 보지 않음
        assert extract_tags("issue #123 done") == []


class TestEdgeCases:
    def test_punctuation_terminates_tag(self):
        assert extract_tags("#foo, #bar.") == ["foo", "bar"]

    def test_double_hash_not_tag(self):
        assert extract_tags("##heading") == []

    def test_underscore_in_tag(self):
        assert extract_tags("#snake_case") == ["snake_case"]

    def test_dash_in_tag(self):
        assert extract_tags("#kebab-case") == ["kebab-case"]
