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

    # DNS 리바인딩 방어: 로컬 파일 서버라 인증이 없으므로, 악성 웹페이지가
    # 자기 도메인을 127.0.0.1로 리바인딩해 로컬 API로 파일을 빼가는 경로를 Host 검증으로 차단.
    # localhost·명시 바인딩 host는 허용하되 임의 Host 헤더는 거부. (2026-07-02 보안감사)
    import socket
    from starlette.middleware.trustedhost import TrustedHostMiddleware

    allowed = {"localhost", "127.0.0.1", "::1", "testserver"}
    if host in ("0.0.0.0", "::", ""):
        allowed.add(socket.gethostname())  # 광범위 바인딩: LAN 접근 호스트명만 추가 허용
    else:
        allowed.add(host)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=sorted(allowed))

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
