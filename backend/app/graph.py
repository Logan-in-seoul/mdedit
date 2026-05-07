from __future__ import annotations
import sqlite3
from collections import deque


def build_graph(conn: sqlite3.Connection, path_id: str, depth: int) -> dict:
    """BFS로 links 테이블을 탐색해 nodes/edges를 반환한다."""
    if depth < 1:
        return {"nodes": [], "edges": []}

    visited: set[str] = set()
    edges: list[dict] = []
    queue: deque[tuple[str, int]] = deque([(path_id, 0)])

    # Check if source exists in files table
    row = conn.execute("SELECT 1 FROM files WHERE path = ?", (path_id,)).fetchone()
    if not row:
        return {"nodes": [], "edges": []}

    visited.add(path_id)

    while queue:
        current, current_depth = queue.popleft()
        if current_depth >= depth:
            continue
        rows = conn.execute(
            "SELECT dst FROM links WHERE src = ?", (current,)
        ).fetchall()
        for (dst,) in rows:
            edges.append({"source": current, "target": dst})
            if dst not in visited:
                visited.add(dst)
                queue.append((dst, current_depth + 1))

    nodes = [{"id": nid, "label": nid.split("://")[-1]} for nid in visited]
    return {"nodes": nodes, "edges": edges}
