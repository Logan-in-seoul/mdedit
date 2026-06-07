// 내비게이션 영속 상태 (v0.8) — 최근 파일, 파일별 스크롤 위치, 마지막 세션 문서.
// 전부 localStorage 기반, 실패는 조용히 무시한다.

const RECENT_KEY = "mdedit:recent";
const LAST_DOC_KEY = "mdedit:last-doc";
const SCROLL_PREFIX = "mdedit:scroll:";
const RECENT_MAX = 30;

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw == null ? fallback : (JSON.parse(raw) as T);
  } catch {
    return fallback;
  }
}

function write(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // quota 등 — 무시
  }
}

export function getRecent(): string[] {
  return read<string[]>(RECENT_KEY, []);
}

export function pushRecent(path: string): void {
  const list = getRecent().filter((p) => p !== path);
  list.unshift(path);
  write(RECENT_KEY, list.slice(0, RECENT_MAX));
}

export function getLastDoc(): string | null {
  return read<string | null>(LAST_DOC_KEY, null);
}

export function setLastDoc(path: string): void {
  write(LAST_DOC_KEY, path);
}

export function getScroll(path: string): number {
  return read<number>(SCROLL_PREFIX + path, 0);
}

export function saveScroll(path: string, top: number): void {
  write(SCROLL_PREFIX + path, Math.round(top));
}
