"""정규식 스캔 전용 워커 프로세스.

`re`는 매칭 한 번(`rx.search`)이 도는 동안 GIL을 놓지 않고 중간에 끊을 방법도 없다.
그래서 사용자 정규식은 서버 프로세스에서 한 번도 실행하지 않고, spawn으로 띄운 별도
프로세스 하나에서만 돌린다. 서버는 파이프를 벽시계 기한까지만 기다리고, 기한이 지나면
워커를 SIGKILL한 뒤 그때까지 받은 결과를 `truncated`로 돌려준다.

- 워커는 SQLite 인덱스를 읽기 전용으로 직접 열어 스캔하고 매치를 묶음으로 흘려보낸다.
- 워커 스스로도 행 사이마다 예산을 확인해, 느리기만 한 정상 패턴은 죽이지 않고 끝낸다.
- 부모가 죽어 kill을 못 받는 경우에 대비해 워커는 작업마다 SIGALRM 자폭 타이머를 건다.
- 이 모듈은 표준 라이브러리만 import한다 (워커 기동 비용 최소화).
"""
from __future__ import annotations

import logging
import multiprocessing
import re
import signal
import sqlite3
import threading
import time
from pathlib import Path
from urllib.parse import quote

logger = logging.getLogger("mdedit.regex")

KILL_GRACE = 0.3  # 워커의 자체 예산 종료를 기다려 주는 여유. 지나면 강제 종료
STARTUP_TIMEOUT = 10.0  # 워커 기동(ready 신호) 대기 한도 — 스캔 예산과 별개
MAX_WAITERS = 4  # 워커를 기다리며 서버 스레드를 점유할 수 있는 요청 수
SELF_DESTRUCT_EXTRA = 5.0
BATCH_SIZE = 200
BATCH_INTERVAL = 0.1

_SCAN_SQL = """
    SELECT lines_fts.path, line_num, text, f.name, f.title, f.mtime
    FROM lines_fts JOIN files AS f ON f.path = lines_fts.path
    ORDER BY f.mtime DESC, lines_fts.path, line_num
"""


class RegexWorkerError(RuntimeError):
    """워커를 띄우지 못했거나 워커가 비정상 종료했다."""


# ---------------------------------------------------------------- 워커 쪽 (자식 프로세스)


def _scan(conn, job: dict) -> None:
    deadline = time.monotonic() + job["budget"]
    rx = re.compile(job["pattern"], re.IGNORECASE)
    allowed = set(job["allowed"]) if job["allowed"] is not None else None
    line_cap: int = job["line_cap"]
    max_per_file: int = job["max_per_file"]
    wall_now = time.time()

    db = sqlite3.connect(f"file:{quote(job['db_path'])}?mode=ro", uri=True)
    try:
        per_file: dict[str, list] = {}  # path -> [보낸 hit 수, 점수]
        batch: list[tuple] = []
        total = 0
        timed_out = False
        last_flush = time.monotonic()
        for path, line_num, text, name, title, mtime in db.execute(_SCAN_SQL):
            now = time.monotonic()
            if now > deadline:
                timed_out = True
                break
            if allowed is not None and path not in allowed:
                continue
            text = text[:line_cap]
            m = rx.search(text)
            if m is None or m.end() == m.start():
                continue
            total += 1
            state = per_file.get(path)
            if state is None:
                # 점수: 제목/파일명에 패턴이 걸리면 부스트, 최근성 부스트 (낮을수록 상위).
                # 파일 단위 값이라 파일당 한 번만 계산한다.
                score = 0.0
                if title and rx.search(title[:line_cap]):
                    score -= 5.0
                if rx.search((name or "")[:line_cap]):
                    score -= 3.0
                age_days = (wall_now - mtime) / 86400 if mtime else 9999
                if age_days <= 7:
                    score -= 1.0
                elif age_days <= 30:
                    score -= 0.5
                state = per_file[path] = [0, score]
            if state[0] >= max_per_file:
                continue
            state[0] += 1
            batch.append((path, line_num, text, name, state[1], m.start(), m.end()))
            if len(batch) >= BATCH_SIZE or now - last_flush > BATCH_INTERVAL:
                conn.send(("hits", batch, total))
                batch = []
                last_flush = now
        conn.send(("done", batch, total, timed_out))
    finally:
        db.close()


def _worker_main(conn) -> None:
    """워커 루프. 부모 쪽 파이프가 닫히면(부모 종료) 스스로 끝난다."""
    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)  # 터미널 Ctrl-C는 부모가 처리
    except (ValueError, OSError):
        pass
    has_timer = hasattr(signal, "setitimer")
    conn.send(("ready",))
    while True:
        try:
            job = conn.recv()
        except (EOFError, OSError):
            return
        if job is None:
            return
        if has_timer:
            # SIGALRM 기본 동작은 프로세스 종료 — 매칭이 GIL을 쥔 채여도 OS가 끊는다
            signal.setitimer(
                signal.ITIMER_REAL, max(job["budget"], 0.0) + KILL_GRACE + SELF_DESTRUCT_EXTRA
            )
        try:
            _scan(conn, job)
        except (EOFError, BrokenPipeError):
            return
        except Exception as exc:  # noqa: BLE001 — 워커는 죽지 않고 오류를 보고한다
            try:
                conn.send(("error", f"{type(exc).__name__}: {exc}"))
            except (OSError, ValueError):
                return
        finally:
            if has_timer:
                signal.setitimer(signal.ITIMER_REAL, 0)


# ---------------------------------------------------------------- 서버 쪽 (부모 프로세스)

_CTX = multiprocessing.get_context("spawn")
_LOCK = threading.Lock()  # 워커는 하나 — 한 번에 한 작업
_WAITERS = threading.BoundedSemaphore(MAX_WAITERS)
_proc = None
_conn = None
_ready = False


def _spawn() -> None:
    global _proc, _conn, _ready
    parent_conn, child_conn = _CTX.Pipe(duplex=True)
    proc = _CTX.Process(
        target=_worker_main, args=(child_conn,), name="mdedit-regex-worker", daemon=True
    )
    proc.start()
    child_conn.close()  # 부모 쪽 사본을 닫아야 워커 종료 시 EOF가 온다
    _proc, _conn, _ready = proc, parent_conn, False


def _kill() -> None:
    global _proc, _conn, _ready
    proc, conn = _proc, _conn
    _proc, _conn, _ready = None, None, False
    if conn is not None:
        try:
            conn.close()
        except OSError:
            pass
    if proc is not None:
        try:
            proc.kill()
            proc.join(1.0)
        except (OSError, ValueError, AttributeError):
            pass


def _ensure_worker():
    """살아 있고 ready를 보낸 워커의 파이프를 돌려준다. `_LOCK`을 쥔 채 호출한다."""
    global _ready
    if _proc is None or not _proc.is_alive():
        _kill()
        try:
            _spawn()
        except Exception as exc:
            _kill()
            raise RegexWorkerError(f"regex worker spawn failed: {exc}") from exc
    if not _ready:
        try:
            ok = _conn.poll(STARTUP_TIMEOUT) and _conn.recv() == ("ready",)
        except (EOFError, OSError):
            ok = False
        if not ok:
            _kill()
            raise RegexWorkerError("regex worker did not start")
        _ready = True
    return _conn


def scan(
    db_path: Path | str,
    pattern: str,
    allowed: set[str] | None,
    max_per_file: int,
    line_cap: int,
    budget: float,
) -> tuple[list[tuple], int, str | None]:
    """워커에서 정규식 스캔을 돌린다. (rows, total, reason)을 돌려준다.

    rows는 (path, line_num, text, name, score, m_start, m_end) 튜플 목록.
    reason은 정상 완료면 None, 아니면 "timeout"(예산 초과 — 필요하면 워커 강제 종료)
    또는 "busy"(다른 정규식 검색이 워커를 쓰는 중). 호출자가 `budget + KILL_GRACE`
    남짓 안에 반드시 돌아온다 (워커 최초 기동 대기만 예외).
    """
    start = time.monotonic()
    if not _WAITERS.acquire(blocking=False):
        return [], 0, "busy"
    try:
        if not _LOCK.acquire(timeout=max(budget, 0.0)):
            return [], 0, "busy"
        locked_at = time.monotonic()
        try:
            return _scan_locked(
                db_path, pattern, allowed, max_per_file, line_cap, budget - (locked_at - start)
            )
        finally:
            _LOCK.release()
    finally:
        _WAITERS.release()


def _scan_locked(db_path, pattern, allowed, max_per_file, line_cap, remaining):
    conn = _ensure_worker()  # 기동 대기는 예산에서 빼지 않는다 (락 대기는 이미 뺐다)
    hard_deadline = time.monotonic() + max(remaining, 0.0) + KILL_GRACE
    rows: list[tuple] = []
    total = 0
    try:
        conn.send(
            {
                "db_path": str(db_path),
                "pattern": pattern,
                "allowed": sorted(allowed) if allowed is not None else None,
                "max_per_file": max_per_file,
                "line_cap": line_cap,
                "budget": remaining,
            }
        )
        while True:
            left = hard_deadline - time.monotonic()
            if left <= 0 or not conn.poll(left):
                _kill()
                _respawn_quietly()
                return rows, total, "timeout"
            msg = conn.recv()
            kind = msg[0]
            if kind == "hits":
                rows.extend(msg[1])
                total = msg[2]
            elif kind == "done":
                rows.extend(msg[1])
                return rows, msg[2], "timeout" if msg[3] else None
            else:
                raise RegexWorkerError(f"regex worker failed: {msg[1:]}")
    except (EOFError, OSError) as exc:
        # 워커가 도중에 죽었다(자폭 타이머, 외부 kill 등)
        _kill()
        raise RegexWorkerError(f"regex worker died: {exc}") from exc


def _respawn_quietly() -> None:
    """강제 종료 직후 다음 요청을 위해 워커를 미리 띄워 둔다 (ready 대기는 다음 요청에서)."""
    try:
        _spawn()
    except Exception:
        logger.warning("regex worker respawn failed", exc_info=True)
        _kill()


def shutdown() -> None:
    """워커를 정리한다 (테스트·종료용). 다음 scan()이 다시 띄운다."""
    with _LOCK:
        _kill()
