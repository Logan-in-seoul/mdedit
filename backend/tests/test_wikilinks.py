"""Tests for wikilinks.py — parse_wikilinks and related utilities."""
from __future__ import annotations

import pytest

from app.wikilinks import WikiRef, _mask_code_blocks, parse_wikilinks


class TestMaskCodeBlocks:
    def test_inline_code_masked(self):
        masked = _mask_code_blocks("hello `[[note]]` world")
        assert "[[" not in masked

    def test_fenced_code_block_masked(self):
        text = "before\n```\n[[note]]\n```\nafter"
        masked = _mask_code_blocks(text)
        assert "[[" not in masked

    def test_text_outside_code_preserved(self):
        text = "[[note]] outside\n```\n[[inside]]\n```"
        masked = _mask_code_blocks(text)
        assert "[[note]]" in masked
        assert masked.index("[[note]]") == 0

    def test_tilde_fence_masked(self):
        text = "~~~python\n[[ref]]\n~~~"
        masked = _mask_code_blocks(text)
        assert "[[" not in masked

    def test_consecutive_fences_each_masked(self):
        text = "```\n[[a]]\n```\n```\n[[b]]\n```"
        masked = _mask_code_blocks(text)
        assert "[[" not in masked

    def test_length_preserved(self):
        text = "abc `[[x]]` def"
        assert len(_mask_code_blocks(text)) == len(text)


class TestParseWikilinks:
    def test_basic_link_extracted(self):
        refs = parse_wikilinks("see [[note-title]] for details")
        assert len(refs) == 1
        assert refs[0].title == "note-title"
        assert refs[0].display == "note-title"

    def test_display_text_extracted(self):
        refs = parse_wikilinks("see [[note|display text]] here")
        assert refs[0].title == "note"
        assert refs[0].display == "display text"

    def test_multiple_links(self):
        refs = parse_wikilinks("[[a]] and [[b]] and [[c]]")
        assert [r.title for r in refs] == ["a", "b", "c"]

    def test_no_links(self):
        assert parse_wikilinks("plain text") == []

    def test_offsets_correct(self):
        text = "abc [[note]] xyz"
        refs = parse_wikilinks(text)
        assert len(refs) == 1
        assert text[refs[0].start:refs[0].end] == "[[note]]"

    def test_link_in_fenced_code_ignored(self):
        text = "```\n[[inside]]\n```\n[[outside]]"
        refs = parse_wikilinks(text)
        assert len(refs) == 1
        assert refs[0].title == "outside"

    def test_link_in_inline_code_ignored(self):
        refs = parse_wikilinks("text `[[code]]` and [[real]]")
        assert len(refs) == 1
        assert refs[0].title == "real"

    # _INVALID_TITLE_RE filter tests
    def test_quoted_title_filtered(self):
        assert parse_wikilinks('[["cmd","arg1"]]') == []

    def test_dollar_var_filtered(self):
        assert parse_wikilinks("[[${var}]]") == []

    def test_char_class_filtered(self):
        assert parse_wikilinks("[[:word:]]") == []

    def test_coordinate_filtered(self):
        assert parse_wikilinks("[[1,2]]") == []

    def test_block_ref_filtered(self):
        # _INVALID_TITLE_RE filters titles that START with ^ (bare block-id refs)
        assert parse_wikilinks("[[^block-id]]") == []

    def test_single_quote_filtered(self):
        assert parse_wikilinks("[['quoted']]") == []

    def test_valid_korean_title_preserved(self):
        refs = parse_wikilinks("[[메모 제목]]")
        assert len(refs) == 1
        assert refs[0].title == "메모 제목"

    def test_valid_path_with_slash_preserved(self):
        refs = parse_wikilinks("[[folder/note]]")
        assert len(refs) == 1
        assert refs[0].title == "folder/note"

    def test_whitespace_stripped_from_title(self):
        refs = parse_wikilinks("[[  note  ]]")
        assert refs[0].title == "note"

    def test_table_row_code_artifact_filtered(self):
        # Real-world case: markdown table cell with code-like [["cmd","arg",...]] pattern
        text = '| example | [["run","arg1","arg2"]] |'
        assert parse_wikilinks(text) == []
