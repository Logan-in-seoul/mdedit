from __future__ import annotations

import fnmatch
import re
import threading
from pathlib import Path

import frontmatter

from app.schema import AppConfig, FileContent, FileNode, RootConfig


class FileNotFoundInVault(FileNotFoundError):
    pass


_VIRTUAL_RE = re.compile(r"^(?P<root>[a-zA-Z0-9_-]+)://(?P<rel>.*)$")


def resolve_virtual_path(virtual: str, config: AppConfig) -> Path:
    m = _VIRTUAL_RE.match(virtual)
    if not m:
        raise FileNotFoundInVault(f"invalid virtual path: {virtual}")
    root_name = m.group("root")
    rel = m.group("rel")
    root = next((r for r in config.roots if r.name == root_name), None)
    if root is None:
        raise FileNotFoundInVault(f"unknown root: {root_name}")
    candidate = (root.path / rel).resolve()
    try:
        candidate.relative_to(root.path.resolve())
    except ValueError as exc:
        raise FileNotFoundInVault(f"path escapes root: {virtual}") from exc
    return candidate


def to_virtual_path(abs_path: str | Path, config: AppConfig) -> str:
    """절대 파일시스템 경로를 가상 경로(root://rel/path.md)로 변환한다.

    config roots와 대조해 가장 깊게 매치되는 루트(최장 prefix)를 고른다.
    roots 밖이거나, .md가 아니거나, 존재하지 않으면 FileNotFoundInVault.
    """
    p = Path(abs_path).expanduser()
    if not p.is_absolute():
        raise FileNotFoundInVault(f"not an absolute path: {abs_path}")
    p = p.resolve()
    if p.suffix.lower() != ".md":
        raise FileNotFoundInVault(f"not a markdown file: {abs_path}")
    if not p.is_file():
        raise FileNotFoundInVault(f"file not found: {abs_path}")

    best: tuple[int, RootConfig, str] | None = None
    for root in config.roots:
        root_path = root.path.resolve()
        try:
            rel = p.relative_to(root_path)
        except ValueError:
            continue
        depth = len(root_path.parts)
        if best is None or depth > best[0]:
            best = (depth, root, rel.as_posix())
    if best is None:
        raise FileNotFoundInVault(f"path is outside all configured roots: {p}")
    return f"{best[1].name}://{best[2]}"


# ============ vault 밖 임시 열기 (ext://) ============
# /api/open이 등록한 절대경로만 읽기를 허용한다 (임의 파일 노출 방지).
# 인메모리·휘발성 — 인덱스/검색/백링크 대상이 아니며 재시작 시 사라진다.
_EXTERNAL_FILES: set[str] = set()
_EXTERNAL_LOCK = threading.Lock()

EXTERNAL_SCHEME = "ext://"


def register_external(abs_path: str | Path) -> str:
    """roots 밖 .md를 임시 열람 대상으로 등록하고 ext:// 가상 경로를 반환한다."""
    p = Path(abs_path).expanduser()
    if not p.is_absolute():
        raise FileNotFoundInVault(f"not an absolute path: {abs_path}")
    p = p.resolve()
    if p.suffix.lower() != ".md":
        raise FileNotFoundInVault(f"not a markdown file: {abs_path}")
    if not p.is_file():
        raise FileNotFoundInVault(f"file not found: {abs_path}")
    with _EXTERNAL_LOCK:
        _EXTERNAL_FILES.add(str(p))
    return f"{EXTERNAL_SCHEME}{p}"


def resolve_external(virtual: str) -> Path:
    """ext:// 가상 경로를 절대경로로 변환한다. 등록된 경로만 허용."""
    abs_str = virtual[len(EXTERNAL_SCHEME):]
    with _EXTERNAL_LOCK:
        allowed = abs_str in _EXTERNAL_FILES
    if not allowed:
        raise FileNotFoundInVault(f"external file not registered: {virtual}")
    p = Path(abs_str)
    if not p.is_file():
        raise FileNotFoundInVault(f"file not found: {virtual}")
    return p


def _extract_title(body: str) -> str | None:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or None
    return None


def read_file(virtual: str, config: AppConfig) -> FileContent:
    if virtual.startswith(EXTERNAL_SCHEME):
        path = resolve_external(virtual)
    else:
        path = resolve_virtual_path(virtual, config)
    if not path.is_file():
        raise FileNotFoundInVault(f"file not found: {virtual}")
    raw = path.read_text(encoding="utf-8")
    post = frontmatter.loads(raw)
    fm = dict(post.metadata) if post.metadata else None
    body = post.content
    stat = path.stat()
    return FileContent(
        path=virtual,
        title=_extract_title(body),
        frontmatter=fm,
        body=body,
        mtime=int(stat.st_mtime),
        size=stat.st_size,
    )


def _is_excluded(name: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(name, pat) for pat in patterns)


def _walk(root: RootConfig, current: Path, exclude: list[str]) -> list[FileNode]:
    nodes: list[FileNode] = []
    try:
        entries = sorted(current.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError:
        return []

    for entry in entries:
        if _is_excluded(entry.name, exclude):
            continue
        rel = entry.relative_to(root.path).as_posix()
        virtual = f"{root.name}://{rel}"
        if entry.is_dir():
            children = _walk(root, entry, exclude)
            if not children:
                continue  # skip empty dirs
            nodes.append(FileNode(name=entry.name, path=virtual, kind="dir", children=children))
        elif entry.is_file() and entry.suffix.lower() == ".md":
            nodes.append(FileNode(name=entry.name, path=virtual, kind="file"))
    return nodes


def collect_flat(config: AppConfig, limit: int = 500) -> list["FileEntry"]:
    from app.schema import FileEntry

    entries: list[FileEntry] = []
    for root in config.roots:
        _collect_files(root, root.path, config.exclude, entries)
    entries.sort(key=lambda e: e.mtime, reverse=True)
    if limit > 0:
        entries = entries[:limit]
    return entries


def _collect_files(
    root: "RootConfig",
    current: Path,
    exclude: list[str],
    out: list,
) -> None:
    from app.schema import FileEntry

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
                _collect_files(root, entry, exclude, out)
            elif entry.is_file() and entry.suffix.lower() == ".md":
                rel = entry.relative_to(root.path).as_posix()
                virtual = f"{root.name}://{rel}"
                stat = entry.stat()
                out.append(
                    FileEntry(
                        path=virtual,
                        name=entry.name,
                        mtime=int(stat.st_mtime),
                        size=stat.st_size,
                        title=None,
                    )
                )
        except (PermissionError, OSError):
            continue


def find_backlinks(target: str, config: AppConfig, limit: int = 200) -> list:
    """Return notes whose body references the target virtual path.

    Matches three patterns inside note bodies:
    - wiki style: [[root://rel/path.md]] or [[rel/path.md]] or [[basename]]
    - markdown link: ](root://rel/path.md) or ](rel/path.md)
    - bare substring: rel/path.md or basename.md

    Always excludes the target itself from results.
    """
    from app.schema import FileEntry

    m = _VIRTUAL_RE.match(target)
    if not m:
        return []
    rel = m.group("rel")
    basename = Path(rel).name
    stem = Path(rel).stem

    needles: list[str] = []
    if rel:
        needles.append(target)  # full virtual path
        needles.append(rel)  # rel path
    if basename and basename not in needles:
        needles.append(basename)
    if stem and stem != basename and stem not in needles:
        needles.append(stem)
    needles = [n for n in needles if n]

    results: list[FileEntry] = []
    for root in config.roots:
        for entry in _iter_md_files(root, root.path, config.exclude):
            virtual = f"{root.name}://{entry.relative_to(root.path).as_posix()}"
            if virtual == target:
                continue
            try:
                text = entry.read_text(encoding="utf-8", errors="ignore")
            except (PermissionError, OSError):
                continue
            if not any(n in text for n in needles):
                continue
            stat = entry.stat()
            results.append(
                FileEntry(
                    path=virtual,
                    name=entry.name,
                    mtime=int(stat.st_mtime),
                    size=stat.st_size,
                    title=_extract_title(text),
                )
            )
    results.sort(key=lambda e: e.mtime, reverse=True)
    if limit > 0:
        results = results[:limit]
    return results


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


def build_tree(config: AppConfig) -> list[FileNode]:
    tree: list[FileNode] = []
    for root in config.roots:
        children = _walk(root, root.path, config.exclude)
        tree.append(
            FileNode(name=root.name, path=f"{root.name}://", kind="dir", children=children)
        )
    return tree
