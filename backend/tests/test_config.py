from pathlib import Path

import pytest

from app.config import ConfigError, load_config


def test_load_config_parses_valid_yaml(config_file: Path):
    config = load_config(config_file)
    assert len(config.roots) == 4
    assert [r.name for r in config.roots] == ["common", "skills", "memory", "tour"]
    assert all(r.path.is_dir() for r in config.roots)
    assert config.server.port == 8787


def test_load_config_raises_when_root_missing(tmp_path: Path, config_file: Path):
    import yaml
    cfg = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    cfg["roots"].append({"name": "bogus", "path": "/definitely/not/there"})
    config_file.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    with pytest.raises(ConfigError, match="not a directory"):
        load_config(config_file)


def test_load_config_raises_on_duplicate_root_names(tmp_path: Path, config_file: Path):
    import yaml
    cfg = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    cfg["roots"][1]["name"] = "common"  # duplicate
    config_file.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    with pytest.raises(ConfigError, match="duplicate"):
        load_config(config_file)
