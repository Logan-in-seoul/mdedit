// 위키링크 호버 프리뷰: 대상 노트의 첫 줄들을 짧은 텍스트로 만든다.
import { api } from "./api";

const MAX_LINES = 6;
const MAX_CHARS = 320;

export function previewText(body: string): string {
  const lines: string[] = [];
  let inFence = false;
  for (const raw of body.split(/\r?\n/)) {
    const line = raw.trim();
    if (line.startsWith("```") || line.startsWith("~~~")) {
      inFence = !inFence;
      continue;
    }
    if (inFence || !line) continue;
    lines.push(line.replace(/^#{1,6}\s+/, ""));
    if (lines.length >= MAX_LINES) break;
  }
  const text = lines.join("\n");
  return text.length > MAX_CHARS ? text.slice(0, MAX_CHARS).trimEnd() + "…" : text;
}

const cache = new Map<string, Promise<string>>();

// 같은 노트는 한 번만 가져온다. 실패는 캐시하지 않고 빈 문자열을 돌려준다.
export function loadPreview(path: string): Promise<string> {
  let p = cache.get(path);
  if (!p) {
    p = api
      .peek(path)
      .then((c) => previewText(c.body))
      .catch(() => {
        cache.delete(path);
        return "";
      });
    cache.set(path, p);
  }
  return p;
}

export function clearPreviewCache(): void {
  cache.clear();
}
