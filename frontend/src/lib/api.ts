export interface FileNode {
  name: string;
  path: string;
  kind: "file" | "dir";
  children?: FileNode[];
}

export interface FileContent {
  path: string;
  title: string | null;
  frontmatter: Record<string, unknown> | null;
  body: string;
  mtime: number;
  size: number;
}

export interface FileEntry {
  path: string;
  name: string;
  mtime: number;
  size: number;
  title: string | null;
}

export interface ConfigResponse {
  roots: { name: string }[];
  server: { host: string; port: number };
}

export interface SearchHit {
  path: string;
  name: string;
  line: number;
  snippet: string;
  match_start: number;
  match_end: number;
}

export interface SearchResponse {
  query: string;
  total: number;
  truncated: boolean;
  hits: SearchHit[];
}

export interface TagEntry {
  tag: string;
  count: number;
}

export interface GraphNode {
  id: string;
  label: string;
  isCurrent: boolean;
}

export interface GraphEdge {
  source: string;
  target: string;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface EmbedResponse {
  path: string;
  title: string | null;
  body: string;
}

export interface BlockResponse {
  path: string;
  block_id: string;
  content: string;
}

async function json<T>(url: string, method = "GET"): Promise<T> {
  const res = await fetch(url, { method });
  if (!res.ok) {
    throw new Error(`${url} returned ${res.status}`);
  }
  return (await res.json()) as T;
}

export const api = {
  health: () => json<{ status: string }>("/api/health"),
  config: () => json<ConfigResponse>("/api/config"),
  tree: () => json<FileNode[]>("/api/tree"),
  file: async (virtualPath: string) => {
    const res = await json<FileContent>(
      `/api/file?path=${encodeURIComponent(virtualPath)}`,
    );
    // notify listeners (GraphPanel) which note is now open
    if (typeof window !== "undefined") {
      window.dispatchEvent(
        new CustomEvent("mdedit:note-opened", { detail: { path: virtualPath } }),
      );
    }
    return res;
  },
  filesFlat: (limit = 500) =>
    json<FileEntry[]>(`/api/files/flat?limit=${limit}`),
  backlinks: (virtualPath: string, limit = 200) =>
    json<FileEntry[]>(
      `/api/backlinks?path=${encodeURIComponent(virtualPath)}&limit=${limit}`,
    ),
  search: (q: string, tag?: string, limit = 200, path?: string, type?: string) => {
    const params = new URLSearchParams({ q, limit: String(limit) });
    if (tag) params.set("tag", tag);
    if (path) params.set("path", path);
    if (type) params.set("type", type);
    return json<SearchResponse>(`/api/search?${params}`);
  },
  tags: (limit = 500) =>
    json<TagEntry[]>(`/api/tags?limit=${limit}`),
  activity: (days = 14) =>
    json<{
      days: number;
      entries: {
        path: string;
        name: string;
        title: string | null;
        mtime: number;
        created_same_day: boolean;
      }[];
    }>(`/api/activity?days=${days}`),
  updateCheck: () =>
    json<{
      current: string;
      latest: string | null;
      update_available: boolean;
      url: string;
    }>("/api/update-check"),
  starred: () =>
    json<{ paths: string[]; files?: FileEntry[] }>("/api/starred"),
  star: (virtualPath: string) =>
    json<{ ok: boolean }>(
      `/api/starred?path=${encodeURIComponent(virtualPath)}`,
      "PUT",
    ),
  unstar: (virtualPath: string) =>
    json<{ ok: boolean }>(
      `/api/starred?path=${encodeURIComponent(virtualPath)}`,
      "DELETE",
    ),
  graph: (virtualPath: string, depth = 1) =>
    json<GraphResponse>(
      `/api/graph?path=${encodeURIComponent(virtualPath)}&depth=${depth}`,
    ),
  embed: (virtualPath: string) =>
    json<EmbedResponse>(`/api/embed?path=${encodeURIComponent(virtualPath)}`),
  block: (virtualPath: string, blockId: string) =>
    json<BlockResponse>(
      `/api/block?path=${encodeURIComponent(virtualPath)}&block_id=${encodeURIComponent(blockId)}`,
    ),
};

// side-effect: mount panels as second React roots — dynamic to keep main chunk lean.
// BacklinksPanel은 v0.8에서 제거 — 우측은 개요(OutlineSidebar)가 기본.
void import("../components/GraphPanel");
