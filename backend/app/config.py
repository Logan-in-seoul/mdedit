from pathlib import Path

import yaml

from app.schema import AppConfig


class ConfigError(ValueError):
    pass


def load_config(path: Path) -> AppConfig:
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    try:
        config = AppConfig.model_validate(raw)
    except Exception as exc:
        raise ConfigError(f"invalid config: {exc}") from exc

    names = [r.name for r in config.roots]
    if len(names) != len(set(names)):
        raise ConfigError(f"duplicate root names: {names}")

    for root in config.roots:
        if not root.path.is_dir():
            raise ConfigError(f"root '{root.name}' path is not a directory: {root.path}")

    return config
