/**
 * WikiLink — [[파일명]] 패턴을 파싱해 클릭 가능한 링크로 렌더링.
 *
 * rehypeWikiLinks 플러그인: remark-rehype 이후 hast 텍스트 노드에서
 * [[...]] 패턴을 찾아 wiki-link 엘리먼트로 치환한다.
 * code/pre 자손은 변환 제외.
 *
 * WikiLink React 컴포넌트: 클릭 시 `mdedit:open-file` 이벤트를 발사한다.
 * (BacklinksPanel과 동일한 이벤트 버스 사용)
 * 해결된 경로가 있으면 data-wiki-path, 없으면 data-wiki-unresolved 표시.
 */
import type { Plugin } from "unified";
import type { Root, Element, Text, RootContent, Parent } from "hast";
import { visitParents, SKIP } from "unist-util-visit-parents";

// ![[파일명]] embed pattern — processed before wiki-link
const EMBED_RE = /!\[\[([^\[\]|]+?)(?:\|([^\[\]]+))?\]\]/g;

// [[파일명]] or [[파일명^blockId]] or [[파일명|표시]] or [[파일명^blockId|표시]]
const WIKI_RE = /\[\[([^\[\]|^]+?)(?:\^([a-zA-Z0-9][a-zA-Z0-9-]*))?(?:\|([^\[\]]+))?\]\]/g;

export const WIKI_OPEN_EVENT = "mdedit:open-file";

export interface WikiOpenDetail {
  title: string;   // 원본 [[...]] 안 텍스트
  path?: string;   // 서버에서 resolve된 가상 경로 (없으면 미정의)
}

/**
 * Rehype 플러그인: 텍스트 노드에서 [[...]] 패턴을 wiki-link 엘리먼트로 치환.
 */
export const rehypeWikiLinks: Plugin<[], Root> = () => (tree) => {
  visitParents(tree, "text", (node: Text, ancestors: Parent[]) => {
    // code/pre 안쪽 건너뜀
    for (const anc of ancestors) {
      if (anc.type === "element") {
        const tag = (anc as Element).tagName;
        if (tag === "code" || tag === "pre") return;
      }
    }
    const parent = ancestors[ancestors.length - 1] as Parent | undefined;
    if (!parent) return;

    const value = node.value;
    if (!value || !value.includes("[")) return;

    const replacements: RootContent[] = [];
    let lastIdx = 0;
    let found = false;

    // Collect all matches with positions
    const combined: Array<{ start: number; end: number; node: Element }> = [];

    // Embed pattern first
    EMBED_RE.lastIndex = 0;
    let embedMatch: RegExpExecArray | null;
    while ((embedMatch = EMBED_RE.exec(value)) !== null) {
      const title = embedMatch[1].trim();
      const display = embedMatch[2]?.trim() || title;
      if (!title) continue;
      found = true;
      combined.push({
        start: embedMatch.index,
        end: embedMatch.index + embedMatch[0].length,
        node: {
          type: "element",
          tagName: "embed-link",
          properties: { title, display },
          children: [],
        } as Element,
      });
    }

    // Wiki-link pattern (skip positions already covered by embed)
    WIKI_RE.lastIndex = 0;
    let match: RegExpExecArray | null;
    while ((match = WIKI_RE.exec(value)) !== null) {
      const overlaps = combined.some(
        (e) => match!.index >= e.start && match!.index < e.end,
      );
      if (overlaps) continue;
      const title = match[1].trim();
      const blockId = match[2]?.trim() || undefined;
      const display = match[3]?.trim() || title;
      if (!title) continue;
      found = true;
      combined.push({
        start: match.index,
        end: match.index + match[0].length,
        node: {
          type: "element",
          tagName: blockId ? "block-ref" : "wiki-link",
          properties: { title, display, ...(blockId ? { blockId } : {}) },
          children: [],
        } as Element,
      });
    }

    if (!found) return;

    combined.sort((a, b) => a.start - b.start);
    for (const item of combined) {
      if (item.start > lastIdx) {
        replacements.push({ type: "text", value: value.slice(lastIdx, item.start) } as Text);
      }
      replacements.push(item.node);
      lastIdx = item.end;
    }

    if (lastIdx < value.length) {
      replacements.push({
        type: "text",
        value: value.slice(lastIdx),
      } as Text);
    }

    const idx = parent.children.indexOf(node as RootContent);
    if (idx < 0) return;
    (parent.children as RootContent[]).splice(idx, 1, ...replacements);
    return [SKIP, idx + replacements.length];
  });
};

// 클라이언트 측 경로 캐시: title → virtual path | null
const _resolveCache = new Map<string, string | null>();

export async function resolvePath(title: string): Promise<string | null> {
  if (_resolveCache.has(title)) return _resolveCache.get(title)!;
  try {
    const res = await fetch(`/api/resolve?title=${encodeURIComponent(title)}`);
    if (!res.ok) {
      _resolveCache.set(title, null);
      return null;
    }
    const data = (await res.json()) as { path: string | null };
    _resolveCache.set(title, data.path);
    return data.path;
  } catch {
    _resolveCache.set(title, null);
    return null;
  }
}

/**
 * WikiLink React 컴포넌트. rehype-react가 `wiki-link` 엘리먼트를 이걸로 매핑.
 * 마운트 시 /api/resolve로 경로를 비동기 조회한다.
 */
import { useEffect, useState } from "react";

export function WikiLink({
  title,
  display,
}: {
  title?: string;
  display?: string;
}) {
  const [resolvedPath, setResolvedPath] = useState<string | null | undefined>(
    undefined, // undefined = 로딩 중
  );

  useEffect(() => {
    if (!title) return;
    resolvePath(title).then(setResolvedPath);
  }, [title]);

  if (!title) return null;

  const label = display || title;
  const isLoading = resolvedPath === undefined;
  const isUnresolved = resolvedPath === null;

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    const detail: WikiOpenDetail = { title: title!, path: resolvedPath ?? undefined };
    window.dispatchEvent(new CustomEvent(WIKI_OPEN_EVENT, { detail }));
  };

  return (
    <button
      type="button"
      className={[
        "wiki-link",
        isLoading ? "wiki-link-loading" : "",
        isUnresolved ? "wiki-link-unresolved" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      onClick={handleClick}
      title={
        isUnresolved
          ? `파일을 찾을 수 없음: ${title}`
          : resolvedPath
            ? `열기: ${resolvedPath}`
            : title
      }
      data-wiki-title={title}
      data-wiki-path={resolvedPath ?? undefined}
    >
      {label}
    </button>
  );
}
