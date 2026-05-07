from pathlib import Path

from app.fs import build_tree
from app.schema import AppConfig, RootConfig


def _make_config(tmp_path: Path) -> AppConfig:
    roots = []
    for name in ["common", "memory"]:
        p = tmp_path / name
        p.mkdir(exist_ok=True)
        roots.append(RootConfig(name=name, path=p))
    return AppConfig(roots=roots, exclude=["node_modules", ".git"])


def test_build_tree_returns_root_sections(tmp_path: Path):
    config = _make_config(tmp_path)
    (tmp_path / "common" / "a.md").write_text("hi")
    (tmp_path / "memory" / "sub").mkdir()
    (tmp_path / "memory" / "sub" / "b.md").write_text("hi")

    tree = build_tree(config)

    assert len(tree) == 2
    common, memory = tree
    assert common.name == "common"
    assert common.path == "common://"
    assert common.kind == "dir"
    assert len(common.children) == 1
    assert common.children[0].name == "a.md"
    assert common.children[0].path == "common://a.md"
    assert common.children[0].kind == "file"

    assert memory.children[0].kind == "dir"
    assert memory.children[0].children[0].path == "memory://sub/b.md"


def test_build_tree_skips_excluded_dirs(tmp_path: Path):
    config = _make_config(tmp_path)
    (tmp_path / "common" / "node_modules").mkdir()
    (tmp_path / "common" / "node_modules" / "ignored.md").write_text("hi")
    (tmp_path / "common" / "keep.md").write_text("hi")

    tree = build_tree(config)
    common = tree[0]
    names = [c.name for c in common.children]
    assert "keep.md" in names
    assert "node_modules" not in names


def test_build_tree_only_includes_markdown_files(tmp_path: Path):
    config = _make_config(tmp_path)
    (tmp_path / "common" / "note.md").write_text("hi")
    (tmp_path / "common" / "script.py").write_text("pass")

    tree = build_tree(config)
    names = [c.name for c in tree[0].children]
    assert names == ["note.md"]
