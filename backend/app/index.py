"""SQLite + FTS5 라인 인덱서.

전체 .md 파일을 라인 단위로 인덱싱해 풀텍스트 검색을 ms 단위로 처리한다.
mtime 비교로 변경된 파일만 재인덱싱하므로 시작 시 첫 빌드 후엔 빠르다.
"""
from __future__ import annotations

import logging
import re
import sqlite3
import threading
import time
from pathlib import Path

from app import regex_worker
from app.fs import _extract_title, _is_excluded
from app.schema import AppConfig, RootConfig, SearchHit, SearchResponse, TagEntry
from app.tags import extract_tags


_DB_LOCK = threading.Lock()
_DB: sqlite3.Connection | None = None
_DB_PATH: Path | None = None


def _connect(db_path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(str(db_path), check_same_thread=False)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    return db


def _init_schema(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS files (
            path TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            mtime INTEGER NOT NULL,
            size INTEGER NOT NULL,
            title TEXT
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS lines_fts USING fts5(
            path UNINDEXED,
            line_num UNINDEXED,
            text,
            tokenize='trigram'
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS file_tags USING fts5(
            path UNINDEXED,
            tags,
            tokenize="unicode61 tokenchars '/-_'"
        );
        CREATE TABLE IF NOT EXISTS links (
            src TEXT NOT NULL,
            dst TEXT NOT NULL,
            PRIMARY KEY (src, dst)
        );
        CREATE INDEX IF NOT EXISTS links_dst ON links(dst);
        CREATE TABLE IF NOT EXISTS starred (
            path TEXT PRIMARY KEY,
            starred_at INTEGER NOT NULL
        );
        """
    )
    db.commit()


def _migrate_title(db: sqlite3.Connection) -> None:
    """기존 DB에 title 컬럼이 없으면 추가하고, 다음 refresh()에서
    재인덱싱되도록 mtime을 무효화한다. idempotent."""
    cols = {row[1] for row in db.execute("PRAGMA table_info(files)").fetchall()}
    if "title" not in cols:
        with _DB_LOCK:
            db.execute("ALTER TABLE files ADD COLUMN title TEXT")
            db.execute("UPDATE files SET mtime = 0")
            db.commit()


def init_db(state_dir: Path) -> None:
    global _DB, _DB_PATH
    state_dir.mkdir(parents=True, exist_ok=True)
    _DB_PATH = state_dir / "index.db"
    _DB = _connect(_DB_PATH)
    _init_schema(_DB)
    _migrate_tags(_DB)
    _migrate_title(_DB)
    _migrate_trigram(_DB)


def _migrate_tags(db: sqlite3.Connection) -> None:
    """기존 DB에 file_tags가 비어 있고 files만 있는 경우, mtime을 0으로 만들어
    다음 refresh()에서 강제 재인덱싱되도록 한다. idempotent."""
    file_count = db.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    if file_count == 0:
        return
    tag_count = db.execute("SELECT COUNT(*) FROM file_tags").fetchone()[0]
    if tag_count == 0:
        # backfill marker: invalidate mtime so refresh will re-process
        with _DB_LOCK:
            db.execute("UPDATE files SET mtime = 0")
            db.commit()


def _migrate_trigram(db: sqlite3.Connection) -> None:
    """lines_fts가 구버전 unicode61 토크나이저면 trigram으로 재생성한다.

    unicode61은 한글 음절 런을 통째로 한 토큰으로 만들어 부분 검색('회의자료'를
    '회의'로 못 찾음)이 불가능했다. trigram은 부분/중간 매치를 지원한다.
    재생성 후 mtime을 무효화해 다음 refresh()에서 전량 재인덱싱되게 한다. idempotent."""
    row = db.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='lines_fts'"
    ).fetchone()
    if row and "trigram" not in (row[0] or "").lower():
        with _DB_LOCK:
            db.execute("DROP TABLE lines_fts")
            db.execute(
                "CREATE VIRTUAL TABLE lines_fts USING fts5("
                "path UNINDEXED, line_num UNINDEXED, text, tokenize='trigram')"
            )
            db.execute("UPDATE files SET mtime = 0")
            db.commit()


def get_db() -> sqlite3.Connection:
    if _DB is None:
        raise RuntimeError("index db not initialized")
    return _DB


# Alias used by graph routes
get_conn = get_db


def _iter_md_files(root: RootConfig, current: Path, exclude: list[str]):
    try:
        entries = current.iterdir()
    except (PermissionError, OSError):
        return
    for entry in entries:
        if _is_excluded(entry.name, exclude):
            continue
        try:
            if entry.is_symlink():
                continue
            if entry.is_dir():
                yield from _iter_md_files(root, entry, exclude)
            elif entry.is_file() and entry.suffix.lower() == ".md":
                yield entry
        except (PermissionError, OSError):
            continue


def _extract_frontmatter_type(text: str) -> str | None:
    """YAML frontmatter에서 `type:` 값을 추출한다. 없으면 None."""
    import re as _re
    m = _re.match(r"^---\s*\n(.*?\n)---\s*\n", text, _re.DOTALL)
    if not m:
        return None
    fm_block = m.group(1)
    for line in fm_block.splitlines():
        kv = line.split(":", 1)
        if len(kv) == 2 and kv[0].strip().lower() == "type":
            val = kv[1].strip().strip("'\"")
            return val.lower() if val else None
    return None


def _index_file(db: sqlite3.Connection, root: RootConfig, path: Path) -> None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except (PermissionError, OSError):
        return
    rel = path.relative_to(root.path).as_posix()
    virtual = f"{root.name}://{rel}"
    stat = path.stat()
    tags = extract_tags(text)
    # frontmatter type 값을 `type:<val>` 형태로 태그 블롭에 추가한다
    fm_type = _extract_frontmatter_type(text)
    if fm_type:
        type_token = f"type:{fm_type}"
        if type_token not in tags:
            tags = tags + [type_token]
    tags_blob = " ".join(tags)
    # Parse wikilinks using the shared parser (requires [[...]] closing, filters invalid titles)
    from app.wikilinks import parse_wikilinks
    link_targets = []
    for ref in parse_wikilinks(text):
        dst_id = f"{root.name}://{ref.title}.md"
        link_targets.append(dst_id)

    with _DB_LOCK:
        db.execute("DELETE FROM lines_fts WHERE path = ?", (virtual,))
        db.execute("DELETE FROM file_tags WHERE path = ?", (virtual,))
        db.execute("DELETE FROM links WHERE src = ?", (virtual,))
        db.execute(
            "INSERT OR REPLACE INTO files (path, name, mtime, size, title) VALUES (?, ?, ?, ?, ?)",
            (virtual, path.name, int(stat.st_mtime), stat.st_size, _extract_title(text)),
        )
        db.execute(
            "INSERT INTO file_tags (path, tags) VALUES (?, ?)",
            (virtual, tags_blob),
        )
        for dst_id in link_targets:
            db.execute(
                "INSERT OR REPLACE INTO links (src, dst) VALUES (?, ?)",
                (virtual, dst_id)
            )
        for i, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            db.execute(
                "INSERT INTO lines_fts (path, line_num, text) VALUES (?, ?, ?)",
                (virtual, i, line),
            )
        db.commit()


def refresh(config: AppConfig) -> dict[str, int]:
    """Walk all .md files and re-index changed ones based on mtime."""
    db = get_db()
    seen: set[str] = set()
    indexed = 0
    skipped = 0
    for root in config.roots:
        for path in _iter_md_files(root, root.path, config.exclude):
            rel = path.relative_to(root.path).as_posix()
            virtual = f"{root.name}://{rel}"
            seen.add(virtual)
            try:
                mtime = int(path.stat().st_mtime)
            except OSError:
                continue
            cur = db.execute(
                "SELECT mtime FROM files WHERE path = ?", (virtual,)
            ).fetchone()
            if cur is None or cur[0] != mtime:
                _index_file(db, root, path)
                indexed += 1
            else:
                skipped += 1

    # delete records for files no longer present
    cur = db.execute("SELECT path FROM files").fetchall()
    deleted = 0
    # 대량 삭제 가드 (ISSUE-005): walk 결과가 기존 인덱스의 절반 미만이면
    # 설정 오류·부분 walk·동시 writer를 의심하고 cleanup을 건너뛴다.
    # 정상 vault에서 한 번에 절반 이상이 사라지는 일은 없다 — starred까지
    # 연쇄 삭제되므로 잘못 지우면 복구 불가.
    if len(cur) > 100 and len(seen) < len(cur) * 0.5:
        logging.getLogger("mdedit.index").warning(
            "refresh cleanup skipped: walked %d files but index has %d "
            "(suspiciously small walk — config/race?)",
            len(seen),
            len(cur),
        )
        return {
            "indexed": indexed,
            "skipped": skipped,
            "deleted": 0,
            "total": len(seen),
        }
    with _DB_LOCK:
        for (path,) in cur:
            if path not in seen:
                db.execute("DELETE FROM files WHERE path = ?", (path,))
                db.execute("DELETE FROM lines_fts WHERE path = ?", (path,))
                db.execute("DELETE FROM file_tags WHERE path = ?", (path,))
                db.execute("DELETE FROM links WHERE src = ?", (path,))
                db.execute("DELETE FROM starred WHERE path = ?", (path,))
                deleted += 1
        db.commit()

    return {"indexed": indexed, "skipped": skipped, "deleted": deleted, "total": len(seen)}


def list_starred() -> list[str]:
    """별표 경로를 starred_at 역순(최근 별표가 위)으로 반환한다."""
    db = get_db()
    rows = db.execute(
        "SELECT path FROM starred ORDER BY starred_at DESC, path"
    ).fetchall()
    return [p for (p,) in rows]


def list_starred_files() -> list[dict]:
    """별표 파일을 files 메타데이터와 JOIN해 starred_at 역순으로 반환한다.

    최근 수정 목록(files_flat limit)에 없는 오래된 별표 파일도
    고정 섹션에 그릴 수 있도록 전체 메타데이터를 제공한다.
    """
    db = get_db()
    rows = db.execute(
        """
        SELECT f.path, f.name, f.mtime, f.size, f.title
        FROM starred s JOIN files f ON f.path = s.path
        ORDER BY s.starred_at DESC, s.path
        """
    ).fetchall()
    return [
        {"path": p, "name": n, "mtime": m, "size": sz, "title": t}
        for (p, n, m, sz, t) in rows
    ]


def index_single(virtual: str, config: "AppConfig") -> bool:
    """가상 경로 하나를 즉석 인덱싱한다. 디스크에 실존하는 .md면 True.

    인덱스 refresh(startup·수동) 이후 생성된 파일은 files에 없어서
    star가 404로 조용히 실패했다(ISSUE-004). 디스크 실측 후 단건 인덱싱.
    """
    if "://" not in virtual:
        return False
    root_name, rel = virtual.split("://", 1)
    root = next((r for r in config.roots if r.name == root_name), None)
    if root is None:
        return False
    disk_path = (Path(root.path) / rel).resolve()
    # 루트 밖 경로 차단
    if not str(disk_path).startswith(str(Path(root.path).resolve())):
        return False
    if not (disk_path.is_file() and disk_path.suffix == ".md"):
        return False
    # _index_file이 내부에서 _DB_LOCK을 잡고 commit까지 한다 (여기서 잡으면 데드락)
    _index_file(get_db(), root, disk_path)
    return True


def star(path: str) -> bool:
    """파일에 별표를 단다. files에 없는 경로면 False."""
    db = get_db()
    exists = db.execute("SELECT 1 FROM files WHERE path = ?", (path,)).fetchone()
    if not exists:
        return False
    with _DB_LOCK:
        db.execute(
            "INSERT OR REPLACE INTO starred (path, starred_at) VALUES (?, ?)",
            (path, int(time.time())),
        )
        db.commit()
    return True


def unstar(path: str) -> None:
    """별표를 해제한다. 없어도 조용히 성공(idempotent)."""
    db = get_db()
    with _DB_LOCK:
        db.execute("DELETE FROM starred WHERE path = ?", (path,))
        db.commit()


TRIGRAM_MIN = 3  # trigram 토크나이저는 3글자 미만 토큰을 매치할 수 없다


def _tokenize_query(query: str) -> list[str]:
    """공백으로 분리하고 큰따옴표를 제거한다. 빈 토큰은 버린다."""
    out: list[str] = []
    for t in query.split():
        cleaned = t.replace('"', "").strip()
        if cleaned:
            out.append(cleaned)
    return out


def _trigram_match_query(tokens: list[str]) -> str:
    """trigram FTS5용 substring-AND 쿼리: 각 토큰을 따옴표 구절로 감싼다."""
    return " ".join(f'"{t}"' for t in tokens)


def _like_term(token: str) -> str:
    """LIKE 폴백용 패턴. %·_·\\ 를 이스케이프해 와일드카드 오작동을 막는다."""
    esc = token.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{esc}%"


def _locate_match(text: str, tokens: list[str]) -> tuple[int, int] | None:
    """라인에서 토큰 중 가장 먼저 등장하는 구간을 찾는다 (대소문자 무시).

    trigram이 과대 매치하거나 LIKE 와일드카드가 섞여도, 실제 토큰이 부분
    문자열로 존재하는 라인만 통과시켜 거짓 양성을 걸러낸다."""
    low = text.lower()
    best: tuple[int, int] | None = None
    for t in tokens:
        idx = low.find(t.lower())
        if idx >= 0 and (best is None or idx < best[0]):
            best = (idx, idx + len(t))
    return best


def _extract_tag_prefix(query: str) -> tuple[str, str | None]:
    """`tag:foo` 또는 `tag:foo bar` 형태를 파싱해 (잔여 쿼리, tag) 반환."""
    tokens = query.split()
    rest: list[str] = []
    tag: str | None = None
    for tok in tokens:
        if tok.startswith("tag:") and len(tok) > 4 and tag is None:
            tag = tok[4:]
        else:
            rest.append(tok)
    return " ".join(rest), tag


def _extract_operator_prefixes(query: str) -> tuple[str, str | None, str | None, str | None]:
    """쿼리에서 `tag:`, `path:`, `type:` 연산자를 파싱한다.

    반환: (잔여 텍스트, tag, path_filter, type_filter)
    각 연산자는 첫 번째 등장만 인식하고 나머지 토큰은 텍스트 쿼리로 돌려준다.
    """
    tokens = query.split()
    rest: list[str] = []
    tag: str | None = None
    path_filter: str | None = None
    type_filter: str | None = None
    for tok in tokens:
        low = tok.lower()
        if tok.startswith("tag:") and len(tok) > 4 and tag is None:
            tag = tok[4:]
        elif low.startswith("path:") and len(tok) > 5 and path_filter is None:
            path_filter = tok[5:]
        elif low.startswith("type:") and len(tok) > 5 and type_filter is None:
            type_filter = tok[5:]
        else:
            rest.append(tok)
    return " ".join(rest), tag, path_filter, type_filter


def _paths_with_path_filter(db: sqlite3.Connection, path_fragment: str) -> set[str]:
    """파일 경로에 path_fragment가 포함된 가상 경로를 반환한다."""
    fragment = path_fragment.lower()
    rows = db.execute("SELECT path FROM files").fetchall()
    return {p for (p,) in rows if fragment in p.lower()}


def _paths_with_type(db: sqlite3.Connection, type_value: str) -> set[str]:
    """file_tags에 `type:<value>` 형태로 저장된 파일을 반환한다.

    타입은 frontmatter의 `type` 필드 값으로, 태그 인덱스에 `type:<val>` 형식으로 저장한다.
    이미 인덱싱된 tags blob에서 `type:` prefix를 검색한다.
    """
    target = f"type:{type_value.lower()}"
    rows = db.execute("SELECT path, tags FROM file_tags").fetchall()
    result: set[str] = set()
    for path, tags_blob in rows:
        if not tags_blob:
            continue
        for t in tags_blob.split():
            if t.lower() == target:
                result.add(path)
                break
    return result


def _paths_with_tag(db: sqlite3.Connection, tag: str) -> set[str]:
    cleaned = tag.replace('"', "").strip()
    if not cleaned:
        return set()
    fts_query = f'"{cleaned}"'
    try:
        rows = db.execute(
            "SELECT path FROM file_tags WHERE file_tags MATCH ?",
            (fts_query,),
        ).fetchall()
    except sqlite3.OperationalError:
        return set()
    return {p for (p,) in rows}


REGEX_MAX_PATTERN_LEN = 200
REGEX_MAX_UNBOUNDED = 3
REGEX_LINE_CAP = 400
REGEX_TIME_BUDGET = 2.0


class RegexSearchError(ValueError):
    """잘못되었거나 위험한 정규식."""


try:  # Python 3.11+
    from re import _constants as _sre_const
    from re import _parser as _sre_parse
except ImportError:  # pragma: no cover
    import sre_constants as _sre_const  # type: ignore
    import sre_parse as _sre_parse  # type: ignore


def compile_safe_regex(pattern: str) -> re.Pattern[str]:
    """사용자 정규식을 컴파일하되 재앙적 백트래킹 위험 패턴은 거부한다.

    거부: 길이 초과, 역참조, 무한 반복의 중첩, 무한 반복 안의 선택(|),
    무한 반복 3개 초과. 대소문자는 구분하지 않는다."""
    if len(pattern) > REGEX_MAX_PATTERN_LEN:
        raise RegexSearchError("정규식이 너무 깁니다")
    try:
        parsed = _sre_parse.parse(pattern, re.IGNORECASE)
    except re.error as e:
        raise RegexSearchError(f"잘못된 정규식: {e}") from e
    unbounded = 0

    def walk(items, in_unbounded: bool) -> None:
        nonlocal unbounded
        for op, av in items:
            if op in (_sre_const.GROUPREF, _sre_const.GROUPREF_EXISTS):
                raise RegexSearchError("역참조는 지원하지 않습니다")
            if op in (_sre_const.MAX_REPEAT, _sre_const.MIN_REPEAT,
                      getattr(_sre_const, "POSSESSIVE_REPEAT", None)):
                _lo, hi, sub = av
                is_unb = hi >= 100 or hi == _sre_const.MAXREPEAT
                if is_unb:
                    if in_unbounded:
                        raise RegexSearchError("중첩된 반복은 지원하지 않습니다")
                    unbounded += 1
                walk(sub, in_unbounded or is_unb)
            elif op == _sre_const.BRANCH:
                if in_unbounded:
                    raise RegexSearchError("반복 안의 선택(|)은 지원하지 않습니다")
                for alt in av[1]:
                    walk(alt, in_unbounded)
            elif op == _sre_const.SUBPATTERN:
                walk(av[3], in_unbounded)
            elif op in (_sre_const.ASSERT, _sre_const.ASSERT_NOT):
                walk(av[1], in_unbounded)

    walk(parsed, False)
    if unbounded > REGEX_MAX_UNBOUNDED:
        raise RegexSearchError("무한 반복(*, +)이 너무 많습니다")
    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error as e:  # 파싱은 통과하고 컴파일에서 걸리는 경우 (가변 길이 look-behind 등)
        raise RegexSearchError(f"잘못된 정규식: {e}") from e


def _search_regex(
    db: sqlite3.Connection,
    query: str,
    max_hits: int,
    max_per_file: int,
    tag: str | None,
    path_filter: str | None,
    type_filter: str | None,
) -> SearchResponse:
    """정규식 모드: trigram 인덱스를 쓰지 않고 라인을 시간 제한 안에서 스캔한다.

    쿼리 전체가 패턴이므로 `tag:` 등 연산자 접두어는 해석하지 않고, 필터는
    명시적 파라미터로만 받는다. 시간 예산을 넘기면 지금까지의 결과를 truncated로 돌려준다.
    `compile_safe_regex`는 1차 방어일 뿐이라(통과하는 다항식 백트래킹 패턴이 있다),
    이 프로세스에서는 패턴을 컴파일·검사만 하고 매칭은 하지 않는다."""
    pattern = query.strip()
    empty = SearchResponse(query=query, total=0, truncated=False, hits=[])
    if not pattern:
        return empty
    compile_safe_regex(pattern)

    allowed: set[str] | None = None
    for paths in (
        _paths_with_tag(db, tag) if tag else None,
        _paths_with_path_filter(db, path_filter) if path_filter else None,
        _paths_with_type(db, type_filter) if type_filter else None,
    ):
        if paths is None:
            continue
        allowed = paths if allowed is None else allowed & paths
        if not allowed:
            return empty

    if _DB_PATH is None:
        raise RuntimeError("index db not initialized")
    # 매칭은 워커 프로세스에서만 돈다 — 예산을 넘기면 워커째 강제 종료된다 (regex_worker 참고)
    rows, total, reason = regex_worker.scan(
        _DB_PATH, pattern, allowed, max_per_file, REGEX_LINE_CAP, REGEX_TIME_BUDGET
    )
    pad = 60
    groups: dict[str, dict] = {}
    for path, line_num, text, name, score, m_start, m_end in rows:
        group = groups.setdefault(path, {"score": score, "hits": []})
        before, after = text[:m_start], text[m_end:]
        before_trim = before[-pad:]
        prefix = "…" if len(before) > pad else ""
        suffix = "…" if len(after) > pad else ""
        snippet = f"{prefix}{before_trim}{text[m_start:m_end]}{after[:pad]}{suffix}"
        ms = len(prefix) + len(before_trim)
        group["hits"].append(
            (
                line_num,
                SearchHit(
                    path=path,
                    name=name or path.rsplit("/", 1)[-1],
                    line=line_num,
                    snippet=snippet,
                    match_start=ms,
                    match_end=ms + (m_end - m_start),
                ),
            )
        )

    hits: list[SearchHit] = []
    over_limit = False
    for group in sorted(groups.values(), key=lambda g: g["score"]):
        for _, hit in sorted(group["hits"], key=lambda h: h[0]):
            if len(hits) >= max_hits:
                over_limit = True
                break
            hits.append(hit)
        if over_limit:
            break
    return SearchResponse(
        query=query,
        total=total,
        truncated=over_limit or reason is not None,
        hits=hits,
        truncated_reason=reason,
    )


def search(
    config: AppConfig,
    query: str,
    max_hits: int = 200,
    max_per_file: int = 5,
    tag: str | None = None,
    path_filter: str | None = None,
    type_filter: str | None = None,
    regex: bool = False,
) -> SearchResponse:
    needle = query.strip()
    if regex:
        return _search_regex(
            get_db(), query, max_hits, max_per_file, tag, path_filter, type_filter
        )
    # 쿼리에서 모든 연산자를 파싱한다
    text_q, prefix_tag, prefix_path, prefix_type = _extract_operator_prefixes(needle)
    if tag is None:
        tag = prefix_tag
    if path_filter is None:
        path_filter = prefix_path
    if type_filter is None:
        type_filter = prefix_type
    needle = text_q.strip()
    db = get_db()

    # 각 필터가 허용하는 경로 집합을 교집합으로 좁혀간다
    allowed_paths: set[str] | None = None

    if tag:
        tag_paths = _paths_with_tag(db, tag)
        if not tag_paths:
            return SearchResponse(query=query, total=0, truncated=False, hits=[])
        allowed_paths = tag_paths

    if path_filter:
        pf_paths = _paths_with_path_filter(db, path_filter)
        if not pf_paths:
            return SearchResponse(query=query, total=0, truncated=False, hits=[])
        allowed_paths = pf_paths if allowed_paths is None else allowed_paths & pf_paths
        if not allowed_paths:
            return SearchResponse(query=query, total=0, truncated=False, hits=[])

    if type_filter:
        tf_paths = _paths_with_type(db, type_filter)
        if not tf_paths:
            return SearchResponse(query=query, total=0, truncated=False, hits=[])
        allowed_paths = tf_paths if allowed_paths is None else allowed_paths & tf_paths
        if not allowed_paths:
            return SearchResponse(query=query, total=0, truncated=False, hits=[])

    # 하위 호환: 기존 tag_paths 변수명 유지
    tag_paths: set[str] | None = allowed_paths

    # Filter-only mode: no text query, just return one synthetic hit per matched file
    if not needle and tag_paths is not None:
        # 스니펫: 활성 필터를 보여준다
        filter_parts = []
        if tag:
            filter_parts.append(f"#{tag}")
        if path_filter:
            filter_parts.append(f"path:{path_filter}")
        if type_filter:
            filter_parts.append(f"type:{type_filter}")
        filter_label = " ".join(filter_parts) if filter_parts else query

        hits: list[SearchHit] = []
        for vpath in sorted(tag_paths):
            name_row = db.execute(
                "SELECT name FROM files WHERE path = ?", (vpath,)
            ).fetchone()
            name = name_row[0] if name_row else vpath.rsplit("/", 1)[-1]
            hits.append(
                SearchHit(
                    path=vpath, name=name, line=1,
                    snippet=filter_label, match_start=0, match_end=len(filter_label),
                )
            )
        return SearchResponse(
            query=query, total=len(hits), truncated=False, hits=hits[:max_hits]
        )

    if not needle:
        return SearchResponse(query=query, total=0, truncated=False, hits=[])
    tokens = _tokenize_query(needle)
    if not tokens:
        return SearchResponse(query=query, total=0, truncated=False, hits=[])

    if all(len(t) >= TRIGRAM_MIN for t in tokens):
        # 3글자 이상 토큰만 — trigram FTS로 bm25 랭킹과 함께 빠르게 조회한다
        rows = db.execute(
            """
            SELECT lines_fts.path, line_num, text, rank, f.name, f.title, f.mtime
            FROM lines_fts
            JOIN files AS f ON f.path = lines_fts.path
            WHERE lines_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (_trigram_match_query(tokens), max_hits * 4),
        ).fetchall()
    else:
        # 2글자 이하 토큰 포함(예: 한글 '회의') — trigram이 못 잡으므로 LIKE 부분 스캔으로 폴백.
        # bm25 랭크가 없어 rank=0; 최근 수정 순으로 후보를 모으고 점수 모델로 정렬한다.
        like_clause = " AND ".join(["lines_fts.text LIKE ? ESCAPE '\\'"] * len(tokens))
        params: list = [_like_term(t) for t in tokens]
        params.append(max_hits * 4)
        rows = db.execute(
            f"""
            SELECT lines_fts.path, line_num, text, 0.0 AS rank, f.name, f.title, f.mtime
            FROM lines_fts
            JOIN files AS f ON f.path = lines_fts.path
            WHERE {like_clause}
            ORDER BY f.mtime DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    if tag_paths is not None:
        rows = [r for r in rows if r[0] in tag_paths]

    # 파일 단위 그룹핑 + 점수 모델.
    # bm25 rank(작을수록 좋음)에 제목/파일명/경로 매치와 최근성 부스트를 더해
    # 파일 대표 점수(최소값)로 파일을 정렬하고, 파일 내 hit은 라인 순으로 보여준다.
    # 짧은 스쳐가는 언급이 본문 문서보다 위에 뜨는 문제를 백엔드에서 해결한다.
    needle_low = needle.lower()
    now = time.time()
    total = 0
    pad = 60
    groups: dict[str, dict] = {}  # path → {score, hits:[(line, SearchHit)]}

    for path, line_num, text, rank, name, title, mtime in rows:
        span = _locate_match(text, tokens)
        if span is None:
            continue
        total += 1

        boost = 0.0
        if title and needle_low in title.lower():
            boost -= 5.0  # 제목 매치: 강한 부스트
        if needle_low in (name or "").lower():
            boost -= 3.0  # 파일명 매치
        elif needle_low in path.lower():
            boost -= 1.5  # 경로 매치
        age_days = (now - mtime) / 86400 if mtime else 9999
        if age_days <= 7:
            boost -= 1.0  # 최근 수정 부스트
        elif age_days <= 30:
            boost -= 0.5
        score = rank + boost

        group = groups.setdefault(path, {"score": score, "hits": []})
        group["score"] = min(group["score"], score)
        if len(group["hits"]) >= max_per_file:
            continue

        # 스니펫: Python에서 매치 위치를 계산한다 (trigram·LIKE 양쪽 공통)
        m_start, m_end = span
        match_text = text[m_start:m_end]
        before = text[:m_start]
        after = text[m_end:]
        before_trim = before[-pad:] if len(before) > pad else before
        after_trim = after[:pad] if len(after) > pad else after
        prefix = "…" if len(before) > pad else ""
        suffix = "…" if len(after) > pad else ""
        snippet = f"{prefix}{before_trim}{match_text}{after_trim}{suffix}"
        match_start = len(prefix) + len(before_trim)
        match_end = match_start + len(match_text)

        group["hits"].append(
            (
                line_num,
                SearchHit(
                    path=path,
                    name=name or path.rsplit("/", 1)[-1],
                    line=line_num,
                    snippet=snippet,
                    match_start=match_start,
                    match_end=match_end,
                ),
            )
        )

    hits: list[SearchHit] = []
    truncated = False
    for group in sorted(groups.values(), key=lambda g: g["score"]):
        for _, hit in sorted(group["hits"], key=lambda h: h[0]):
            if len(hits) >= max_hits:
                truncated = True
                break
            hits.append(hit)
        if truncated:
            break

    return SearchResponse(query=query, total=total, truncated=truncated, hits=hits)


def get_tags(limit: int = 500) -> list[TagEntry]:
    """전체 파일의 태그를 집계해 등장 파일 수 기준으로 정렬해 반환한다."""
    db = get_db()
    rows = db.execute("SELECT tags FROM file_tags").fetchall()
    counter: dict[str, int] = {}
    for (tags_blob,) in rows:
        if not tags_blob:
            continue
        for tag in tags_blob.split():
            tag = tag.strip()
            if tag:
                counter[tag] = counter.get(tag, 0) + 1
    sorted_tags = sorted(counter.items(), key=lambda x: (-x[1], x[0]))
    return [TagEntry(tag=t, count=c) for t, c in sorted_tags[:limit]]
