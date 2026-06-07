import argparse
import logging
import os
import threading
from pathlib import Path

import uvicorn

from app.config import load_config
from app.main import app, set_config
import app.index as fts_index

logger = logging.getLogger("mdedit")


def _default_config_path() -> Path:
    env = os.environ.get("MDEDIT_CONFIG")
    if env:
        return Path(env)
    return Path.home() / ".config" / "mdedit" / "config.yaml"


def _background_index(config) -> None:
    try:
        stats = fts_index.refresh(config)
        logger.info("FTS5 index ready: %s", stats)
    except Exception as exc:
        logger.warning("FTS5 index refresh failed: %s", exc)


def main() -> None:
    parser = argparse.ArgumentParser(prog="mdedit")
    parser.add_argument("--config", type=Path, default=_default_config_path())
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    set_config(config)

    # SQLite index 초기화 후 background에서 refresh (서버 시작 지연 없음)
    state_env = os.environ.get("MDEDIT_STATE_DIR")
    state_dir = (
        Path(state_env) if state_env else Path.home() / ".local" / "share" / "mdedit"
    )
    fts_index.init_db(state_dir)
    t = threading.Thread(target=_background_index, args=(config,), daemon=True)
    t.start()

    host = args.host or config.server.host
    port = args.port or config.server.port
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
