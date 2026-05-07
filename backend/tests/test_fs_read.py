from pathlib import Path

import pytest

from app.fs import FileNotFoundInVault, read_file, resolve_virtual_path
from app.schema import AppConfig, RootConfig


def _make_config(tmp_path: Path) -> AppConfig:
    root = tmp_path / "common"
    root.mkdir()
    return AppConfig(roots=[RootConfig(name="common", path=root)])


def test_resolve_virtual_path_returns_absolute_path(tmp_path: Path):
    config = _make_config(tmp_path)
    (tmp_path / "common" / "a.md").write_text("hi")
    resolved = resolve_virtual_path("common://a.md", config)
    assert resolved == tmp_path / "common" / "a.md"


def test_resolve_virtual_path_rejects_traversal(tmp_path: Path):
    config = _make_config(tmp_path)
    with pytest.raises(FileNotFoundInVault):
        resolve_virtual_path("common://../etc/passwd", config)


def test_resolve_virtual_path_rejects_unknown_root(tmp_path: Path):
    config = _make_config(tmp_path)
    with pytest.raises(FileNotFoundInVault, match="unknown root"):
        resolve_virtual_path("ghost://a.md", config)


def test_read_file_parses_frontmatter_and_body(tmp_path: Path):
    config = _make_config(tmp_path)
    target = tmp_path / "common" / "note.md"
    target.write_text(
        "---\ntype: feedback\ntags: [a, b]\n---\n\n# 제목\n\n본문",
        encoding="utf-8",
    )
    content = read_file("common://note.md", config)
    assert content.path == "common://note.md"
    assert content.title == "제목"
    assert content.frontmatter == {"type": "feedback", "tags": ["a", "b"]}
    assert content.body.startswith("# 제목")
    assert content.size > 0


def test_read_file_handles_missing_frontmatter(tmp_path: Path):
    config = _make_config(tmp_path)
    target = tmp_path / "common" / "plain.md"
    target.write_text("# 제목만\n\n본문", encoding="utf-8")
    content = read_file("common://plain.md", config)
    assert content.frontmatter is None
    assert content.title == "제목만"
