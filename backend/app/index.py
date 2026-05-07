"""SQLite + FTS5 라인 인덱서.

전체 .md 파일을 라인 단위로 인덱싱해 풀텍스트 검색을 ms 단위로 처리한다.
mtime 비교로 변경된 파일만 재인덱싱하므로 시작 시 첫 빌드 후엔 빠르다.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from app.fs import _is_excluded
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
            size INTEGER NOT NULL
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS lines_fts USING fts5(
            path UNINDEXED,
            line_num UNINDEXED,
            text,
            tokenize='unicode61'
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
        """
    )
    db.commit()


def init_db(state_dir: Path) -> None:
    global _DB, _DB_PATH
    state_dir.mkdir(parents=True, exist_ok=True)
    _DB_PATH = state_dir / "index.db"
    _DB = _connect(_DB_PATH)
    _init_schema(_DB)
    _migrate_tags(_DB)


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
    # Parse wikilinks
    import re as _re
    wikilink_re = _re.compile(r'\[\[([^\]|#^]+)')
    link_targets = []
    for m in wikilink_re.finditer(text):
        target_stem = m.group(1).strip()
        dst_id = f"{root.name}://{target_stem}.md"
        link_targets.append(dst_id)

    with _DB_LOCK:
        db.execute("DELETE FROM lines_fts WHERE path = ?", (virtual,))
        db.execute("DELETE FROM file_tags WHERE path = ?", (virtual,))
        db.execute("DELETE FROM links WHERE src = ?", (virtual,))
        db.execute(
            "INSERT OR REPLACE INTO files (path, name, mtime, size) VALUES (?, ?, ?, ?)",
            (virtual, path.name, int(stat.st_mtime), stat.st_size),
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
    with _DB_LOCK:
        for (path,) in cur:
            if path not in seen:
                db.execute("DELETE FROM files WHERE path = ?", (path,))
                db.execute("DELETE FROM lines_fts WHERE path = ?", (path,))
                db.execute("DELETE FROM file_tags WHERE path = ?", (path,))
                db.execute("DELETE FROM links WHERE src = ?", (path,))
                deleted += 1
        db.commit()

    return {"indexed": indexed, "skipped": skipped, "deleted": deleted, "total": len(seen)}


def _escape_fts(query: str) -> str:
    """FTS5 phrase query: 토큰별로 분리 후 큰따옴표로 감싸 안전화."""
    tokens = [t for t in query.split() if t]
    if not tokens:
        return '""'
    safe = []
    for t in tokens:
        cleaned = t.replace('"', "")
        if cleaned:
            safe.append(f'"{cleaned}"')
    return " ".join(safe) if safe else '""'


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


def search(
    config: AppConfig,
    query: str,
    max_hits: int = 200,
    max_per_file: int = 5,
    tag: str | None = None,
    path_filter: str | None = None,
    type_filter: str | None = None,
) -> SearchResponse:
    needle = query.strip()
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
    fts_query = _escape_fts(needle)
    rows = db.execute(
        """
        SELECT path, line_num, text,
               highlight(lines_fts, 2, '<<MARK>>', '<<ENDMARK>>') AS hl
        FROM lines_fts
        WHERE lines_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (fts_query, max_hits * 4),
    ).fetchall()
    if tag_paths is not None:
        rows = [r for r in rows if r[0] in tag_paths]

    hits: list[SearchHit] = []
    per_file: dict[str, int] = {}
    total = 0
    truncated = False
    pad = 60

    for path, line_num, text, hl in rows:
        if hl is None or "<<MARK>>" not in hl:
            continue
        total += 1
        cnt = per_file.get(path, 0)
        if cnt >= max_per_file:
            continue
        if len(hits) >= max_hits:
            truncated = True
            continue
        # Build snippet from hl: locate first match
        idx = hl.find("<<MARK>>")
        end = hl.find("<<ENDMARK>>", idx)
        if idx < 0 or end < 0:
            continue
        match_text = hl[idx + len("<<MARK>>") : end]
        before = hl[:idx].replace("<<MARK>>", "").replace("<<ENDMARK>>", "")
        after = hl[end + len("<<ENDMARK>>") :].replace("<<MARK>>", "").replace("<<ENDMARK>>", "")
        # Trim padding
        before_trim = before[-pad:] if len(before) > pad else before
        after_trim = after[:pad] if len(after) > pad else after
        prefix = "…" if len(before) > pad else ""
        suffix = "…" if len(after) > pad else ""
        snippet = f"{prefix}{before_trim}{match_text}{after_trim}{suffix}"
        match_start = len(prefix) + len(before_trim)
        match_end = match_start + len(match_text)

        # Get name from files table
        name_row = db.execute("SELECT name FROM files WHERE path = ?", (path,)).fetchone()
        name = name_row[0] if name_row else path.rsplit("/", 1)[-1]

        hits.append(
            SearchHit(
                path=path,
                name=name,
                line=line_num,
                snippet=snippet,
                match_start=match_start,
                match_end=match_end,
            )
        )
        per_file[path] = cnt + 1

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
