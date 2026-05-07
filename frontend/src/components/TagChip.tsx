/**
 * TagChip — 본문 안의 #tag를 시각화하는 칩.
 *
 * P3 step 3: backend `extract_tags`와 동일한 정규식·경계 규칙으로
 * 텍스트 노드에서 #tag를 찾아 React 컴포넌트로 치환한다. 클릭 시
 * 커스텀 이벤트 `mdedit:tag-search`를 발사해 사이드바 검색에
 * `tag:<name>` 쿼리를 적용한다.
 *
 * code/pre 자손 텍스트는 변환에서 제외한다 (backend 패턴과 일관).
 */
import type { Plugin } from "unified";
import type { Root, Element, Text, RootContent, Parent } from "hast";
import { visitParents, SKIP } from "unist-util-visit-parents";

// 백엔드 _TAG_BODY와 동일: 영숫자, 언더스코어, 대시, 슬래시, 한글
const TAG_BODY = "[A-Za-z0-9_\\-/\\uAC00-\\uD7A3]+";

// 백엔드 _TAG_RE 미러: 직전 문자가 시작/공백/구두점, ## 아닌 단독 #, 첫 글자 숫자 제외.
// JS는 lookbehind 가변폭을 V8/최신 엔진에서 지원하지만 안전하게 단순화:
// 텍스트 시작이거나 비-tagbody 문자 직후에 #가 와야 한다.
const TAG_RE = new RegExp(
  `(^|[\\s,.!?;:\\(\\[\\{])#(?!#)(?![0-9])(${TAG_BODY})`,
  "g",
);

const TAG_NAME_TRIM_RE = /[/\-_]+$/;

export const TAG_SEARCH_EVENT = "mdedit:tag-search";

export interface TagSearchDetail {
  tag: string;
}

/**
 * Rehype 플러그인: 본문 텍스트 노드에서 #tag를 찾아 tag-chip 엘리먼트로 치환.
 * code/pre 안쪽은 건너뛴다.
 */
export const rehypeTagChips: Plugin<[], Root> = () => (tree) => {
  visitParents(tree, "text", (node: Text, ancestors: Parent[]) => {
    // 조상 중 code/pre가 있으면 변환 제외 (Shiki가 만든 span 자손도 안전)
    for (const anc of ancestors) {
      if (anc.type === "element") {
        const tag = (anc as Element).tagName;
        if (tag === "code" || tag === "pre") return;
      }
    }
    const parent = ancestors[ancestors.length - 1] as Parent | undefined;
    if (!parent) return;

    const value = node.value;
    if (!value || !value.includes("#")) return;

    const replacements: RootContent[] = [];
    let lastIdx = 0;
    let match: RegExpExecArray | null;
    TAG_RE.lastIndex = 0;
    let found = false;

    while ((match = TAG_RE.exec(value)) !== null) {
      const lead = match[1] ?? "";
      let tagName = match[2] ?? "";
      tagName = tagName.replace(TAG_NAME_TRIM_RE, "");
      if (!tagName) continue;

      found = true;
      const matchStart = match.index + lead.length; // # 위치
      if (matchStart > lastIdx) {
        replacements.push({
          type: "text",
          value: value.slice(lastIdx, matchStart),
        } as Text);
      }
      replacements.push({
        type: "element",
        tagName: "tag-chip",
        properties: { name: tagName },
        children: [],
      } as Element);
      lastIdx = matchStart + 1 + tagName.length;
    }

    if (!found) return;

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

/**
 * TagChip React 컴포넌트. rehype-react가 `tag-chip` 엘리먼트를 이걸로 매핑한다.
 */
export function TagChip({ name }: { name?: string }) {
  if (!name) return null;
  const onClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const detail: TagSearchDetail = { tag: name };
    window.dispatchEvent(new CustomEvent(TAG_SEARCH_EVENT, { detail }));
  };
  return (
    <button
      type="button"
      className="tag-chip"
      onClick={onClick}
      title={`태그 검색: tag:${name}`}
    >
      <span className="tag-chip-hash">#</span>
      {name}
    </button>
  );
}
