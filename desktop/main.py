"""mdedit 데스크톱 진입점 (pywebview).

uvicorn(기존 FastAPI 앱)을 데몬 스레드로 띄우고 네이티브 WKWebView 창을 연다.

- 포트가 이미 mdedit을 서빙 중이면(/api/health) 서버를 새로 띄우지 않고 재사용한다.
- .md 파일 인자와 함께 실행됐는데 인스턴스가 이미 떠 있으면, 실행 중 인스턴스의
  POST /api/open에 절대 경로를 넘기고 종료한다 (단일 인스턴스 파일 열기).
- macOS에서 앱 실행 중 Finder가 보내는 odoc Apple Event(application:openFile:)는
  pywebview의 Cocoa AppDelegate에 핸들러를 주입해 받는다.
- 창을 닫으면 webview.start()가 반환되고, 서버 스레드는 데몬이라 프로세스가 종료된다.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

HOST = "127.0.0.1"
DEFAULT_PORT = 8787

logger = logging.getLogger("mdedit.desktop")


def _setup_logging() -> None:
    log_dir = Path.home() / ".local" / "state" / "mdedit"
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_dir / "desktop.log", encoding="utf-8"))
    except OSError:
        pass
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=handlers,
    )


def _base_url(port: int) -> str:
    return f"http://{HOST}:{port}"


def _is_mdedit_serving(port: int, timeout: float = 0.5) -> bool:
    """포트에서 mdedit /api/health가 응답하는지 확인한다."""
    try:
        with urllib.request.urlopen(f"{_base_url(port)}/api/health", timeout=timeout) as res:
            return json.load(res).get("status") == "ok"
    except Exception:
        return False


def _wait_healthy(port: int, timeout: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _is_mdedit_serving(port, timeout=1.0):
            return True
        time.sleep(0.2)
    return False


def _post_open(port: int, abs_path: str) -> tuple[bool, str]:
    """실행 중 인스턴스에 파일 열기 요청을 보낸다. (성공 여부, detail)"""
    data = json.dumps({"abs_path": abs_path}).encode("utf-8")
    req = urllib.request.Request(
        f"{_base_url(port)}/api/open",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=3.0) as res:
            body = json.load(res)
        logger.info("open accepted: %s -> %s", abs_path, body.get("path"))
        return True, body.get("path") or ""
    except urllib.error.HTTPError as exc:
        try:
            detail = json.load(exc).get("detail", "")
        except Exception:
            detail = str(exc)
        logger.warning("open rejected (%s): %s — %s", exc.code, abs_path, detail)
        return False, detail
    except Exception as exc:
        logger.warning("open request failed: %s — %s", abs_path, exc)
        return False, str(exc)


def _file_from_argv(argv: list[str]) -> str | None:
    """argv에서 첫 .md 파일 경로를 찾는다 (PyInstaller argv_emulation 포함)."""
    for arg in argv:
        if arg.startswith("-"):
            continue  # -psn_... 같은 Finder/디버그 플래그 무시
        if arg.lower().endswith(".md"):
            return os.path.abspath(os.path.expanduser(arg))
    return None


def _load_config():
    from app.config import load_config

    env = os.environ.get("MDEDIT_CONFIG")
    path = Path(env) if env else Path.home() / ".config" / "mdedit" / "config.yaml"
    return load_config(path)


def _run_server(config, port: int) -> None:
    """백엔드 __main__과 동일한 부트 순서로 uvicorn을 띄운다 (데몬 스레드에서 호출)."""
    import uvicorn

    import app.index as fts_index
    from app.main import app as fastapi_app, set_config

    set_config(config)
    state_dir = Path.home() / ".local" / "share" / "mdedit"
    fts_index.init_db(state_dir)

    def _background_index() -> None:
        try:
            stats = fts_index.refresh(config)
            logger.info("FTS5 index ready: %s", stats)
        except Exception as exc:
            logger.warning("FTS5 index refresh failed: %s", exc)

    threading.Thread(target=_background_index, daemon=True).start()
    uvicorn.run(fastapi_app, host=HOST, port=port, log_level="info")


def _install_macos_open_handler(port: int) -> None:
    """앱 실행 중 Finder .md 더블클릭(odoc Apple Event)을 받는 Cocoa 핸들러 주입.

    pywebview의 Cocoa 백엔드는 BrowserView.AppDelegate(NSObject)를 NSApp delegate로
    설정한다. webview.start() 전에 objc.classAddMethods로 application:openFile:
    셀렉터를 추가하면 macOS가 실행 중 앱에 보내는 파일 열기 이벤트를 받을 수 있다.
    """
    if sys.platform != "darwin":
        return
    try:
        import objc
        from webview.platforms.cocoa import BrowserView

        def application_openFile_(self, _app, filename):  # noqa: N802 (objc selector)
            path = os.path.abspath(str(filename))
            logger.info("Apple Event open: %s", path)
            ok, _ = _post_open(port, path)
            return ok

        selector = objc.selector(
            application_openFile_,
            selector=b"application:openFile:",
            signature=objc._C_NSBOOL + b"@:@@",
        )
        objc.classAddMethods(BrowserView.AppDelegate, [selector])
        logger.info("macOS open-file handler installed")
    except Exception:
        logger.warning("failed to install macOS open-file handler", exc_info=True)


def _open_window(port: int) -> None:
    import webview

    _install_macos_open_handler(port)
    webview.create_window(
        "mdedit",
        f"{_base_url(port)}/?desktop=1",
        width=1280,
        height=850,
        min_size=(700, 480),
    )
    webview.start()


def _open_error_window(message: str) -> None:
    import webview

    html = f"""<!doctype html>
    <meta charset="utf-8">
    <body style="font-family: -apple-system, sans-serif; padding: 2rem; line-height: 1.6">
      <h2>mdedit을 시작할 수 없습니다</h2>
      <p style="white-space: pre-wrap; color: #c0392b">{message}</p>
      <p><code>~/.config/mdedit/config.yaml</code>을 확인하세요.
         예제는 저장소의 <code>config.example.yaml</code>에 있습니다.</p>
    </body>"""
    webview.create_window("mdedit", html=html, width=640, height=360)
    webview.start()


def main() -> None:
    _setup_logging()
    file_arg = _file_from_argv(sys.argv[1:])

    config = None
    config_error: str | None = None
    port = DEFAULT_PORT
    try:
        config = _load_config()
        port = config.server.port or DEFAULT_PORT
    except Exception as exc:
        config_error = str(exc)

    if _is_mdedit_serving(port):
        if file_arg:
            # 단일 인스턴스: 실행 중 인스턴스에 열기 요청을 넘기고 종료한다.
            _post_open(port, file_arg)
            sys.exit(0)
        # 서버는 떠 있는데 파일 인자가 없으면(예: headless 서버 가동 중 Dock 실행)
        # 두 번째 서버 없이 기존 서버를 가리키는 창만 연다.
        logger.info("reusing running mdedit server on port %d", port)
        _open_window(port)
        return

    if config is None:
        logger.error("config load failed: %s", config_error)
        _open_error_window(config_error or "unknown config error")
        return

    threading.Thread(target=_run_server, args=(config, port), daemon=True).start()
    if not _wait_healthy(port):
        _open_error_window(f"백엔드가 {port} 포트에서 기동하지 못했습니다. "
                           f"로그: ~/.local/state/mdedit/desktop.log")
        return

    if file_arg:
        # 창이 뜨면 프론트엔드가 /api/open/pending 폴링으로 픽업한다.
        _post_open(port, file_arg)

    _open_window(port)
    logger.info("window closed — exiting")


if __name__ == "__main__":
    main()
