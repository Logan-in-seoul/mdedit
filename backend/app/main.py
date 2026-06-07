import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from app.fs import (
    FileNotFoundInVault, build_tree, collect_flat, find_backlinks, read_file,
    register_external, to_virtual_path,
)
from app.schema import (
    AppConfig, BlockResponse, EmbedResponse, FileContent, FileEntry, FileNode,
    GraphResponse, OpenRequest, SearchResponse, TagEntry,
)
import app.index as fts_index
from app.wikilinks import resolve_title
from app.graph import build_graph
from app.blocks import extract_blocks

app = FastAPI(title="mdedit", version="0.6.0")
app.add_middleware(GZipMiddleware, minimum_size=1024)

_config: AppConfig | None = None


def set_config(config: AppConfig) -> None:
    global _config
    _config = config


def get_config() -> AppConfig:
    if _config is None:
        raise HTTPException(status_code=503, detail="config not loaded")
    return _config


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/tree", response_model=list[FileNode])
def tree() -> list[FileNode]:
    return build_tree(get_config())


@app.get("/api/file", response_model=FileContent)
def file(path: str = Query(...)) -> FileContent:
    try:
        return read_file(path, get_config())
    except FileNotFoundInVault as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/files/flat", response_model=list[FileEntry])
def files_flat(limit: int = 500) -> list[FileEntry]:
    return collect_flat(get_config(), limit=limit)


@app.get("/api/backlinks", response_model=list[FileEntry])
def backlinks(path: str = Query(...), limit: int = 200) -> list[FileEntry]:
    return find_backlinks(path, get_config(), limit=limit)


@app.get("/api/search", response_model=SearchResponse)
def search(
    q: str = Query(""),
    tag: str | None = Query(None),
    path: str | None = Query(None),
    type: str | None = Query(None),
    limit: int = Query(200),
) -> SearchResponse:
    try:
        return fts_index.search(
            get_config(),
            query=q,
            max_hits=limit,
            tag=tag or None,
            path_filter=path or None,
            type_filter=type or None,
        )
    except RuntimeError:
        raise HTTPException(status_code=503, detail="index not ready")


@app.get("/api/tags", response_model=list[TagEntry])
def tags(limit: int = Query(500)) -> list[TagEntry]:
    try:
        return fts_index.get_tags(limit=limit)
    except RuntimeError:
        raise HTTPException(status_code=503, detail="index not ready")


@app.get("/api/starred")
def starred_list() -> dict:
    """별표 경로 목록 (최근 별표 순)."""
    try:
        return {"paths": fts_index.list_starred()}
    except RuntimeError:
        raise HTTPException(status_code=503, detail="index not ready")


@app.put("/api/starred")
def starred_add(path: str = Query(...)) -> dict:
    try:
        ok = fts_index.star(path)
    except RuntimeError:
        raise HTTPException(status_code=503, detail="index not ready")
    if not ok:
        raise HTTPException(status_code=404, detail=f"file not indexed: {path}")
    return {"ok": True, "path": path}


@app.delete("/api/starred")
def starred_remove(path: str = Query(...)) -> dict:
    try:
        fts_index.unstar(path)
    except RuntimeError:
        raise HTTPException(status_code=503, detail="index not ready")
    return {"ok": True, "path": path}


@app.get("/api/index/refresh")
def index_refresh() -> dict:
    try:
        stats = fts_index.refresh(get_config())
        return {"ok": True, **stats}
    except RuntimeError:
        raise HTTPException(status_code=503, detail="index not ready")


@app.get("/api/resolve")
def resolve(title: str = Query(...)) -> dict:
    """[[파일명]] 링크를 가상 경로로 변환한다.

    Returns:
        {"path": "root://rel/path.md"}  — 찾은 경우
        {"path": null}                  — 찾지 못한 경우
    """
    try:
        path = resolve_title(title)
    except RuntimeError:
        raise HTTPException(status_code=503, detail="index not ready")
    return {"path": path}


@app.get("/api/config")
def config() -> dict:
    cfg = get_config()
    return {
        "roots": [{"name": r.name} for r in cfg.roots],
        "server": {"host": cfg.server.host, "port": cfg.server.port},
    }


# 데스크톱 앱(Finder .md 더블클릭)에서 전달된 "열기 대기" 경로.
# POST /api/open이 채우고, GET /api/open/pending이 반환하며 비운다.
_pending_open: str | None = None
_pending_open_lock = threading.Lock()


@app.post("/api/open")
def open_file(req: OpenRequest) -> dict:
    """절대 경로를 가상 경로로 변환해 pending open으로 저장한다.

    roots 밖 .md는 ext:// 임시 열람으로 등록한다 (v0.7).
    """
    try:
        virtual = to_virtual_path(req.abs_path, get_config())
    except FileNotFoundInVault:
        try:
            virtual = register_external(req.abs_path)
        except FileNotFoundInVault as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    global _pending_open
    with _pending_open_lock:
        _pending_open = virtual
    return {"path": virtual}


@app.get("/api/open/pending")
def open_pending() -> dict:
    """pending open 경로를 반환하고 비운다 (프론트엔드 폴링용)."""
    global _pending_open
    with _pending_open_lock:
        virtual, _pending_open = _pending_open, None
    return {"path": virtual}


def _read_file_content(path: str) -> FileContent | None:
    """가상 경로를 FileContent로 읽어 반환한다. 없으면 None."""
    try:
        return read_file(path, get_config())
    except (FileNotFoundInVault, HTTPException):
        return None


@app.get("/api/graph", response_model=GraphResponse)
def get_graph(path: str, depth: int = 1):
    conn = fts_index.get_conn()
    return build_graph(conn, path, depth)


@app.get("/api/embed", response_model=EmbedResponse)
def get_embed(path: str):
    content = _read_file_content(path)
    if content is None:
        raise HTTPException(status_code=404, detail="not found")
    return EmbedResponse(path=path, title=content.title, body=content.body)


@app.get("/api/block", response_model=BlockResponse)
def get_block(path: str, block_id: str):
    content = _read_file_content(path)
    if content is None:
        raise HTTPException(status_code=404, detail="not found")
    blocks = extract_blocks(content.body)
    if block_id not in blocks:
        raise HTTPException(status_code=404, detail="block not found")
    return BlockResponse(path=path, block_id=block_id, content=blocks[block_id])


_STATIC_DIR = Path(__file__).parent / "static"

if _STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=_STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        index = _STATIC_DIR / "index.html"
        if not index.is_file():
            raise HTTPException(status_code=404)
        return FileResponse(index)
