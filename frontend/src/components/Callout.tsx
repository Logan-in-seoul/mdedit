/**
 * Callout — Obsidian/GitHub 스타일 콜아웃.
 *
 *   > [!key] 제목(선택)
 *   > 본문…
 *
 * blockquote 첫 문단이 `[!type] ...`로 시작하면 `div.callout.callout-{type}`로
 * 변환하고 제목 줄(아이콘 + 라벨/커스텀 제목)을 얹는다. 순수 HTML/CSS 변환이라
 * 별도 React 컴포넌트 없이 rehype-react가 div를 그대로 렌더한다. code/pre는
 * blockquote가 아니므로 영향 없음.
 *
 * 회의 자료처럼 "이 문장을 말하라(say)" · "유일한 요청(ask)" · "주의(warning)" 같은
 * 시각 강조가 필요한 문서를 위해 추가됨 (v0.9.0).
 */
import type { Plugin } from "unified";
import type { Root, Element, Text, RootContent } from "hast";

interface CalloutSpec {
  label: string;
  icon: string;
}

// 표준(note/tip/important/warning/caution) + 회의용 커스텀(say/ask/goal/key).
const CALLOUTS: Record<string, CalloutSpec> = {
  note: { label: "노트", icon: "📝" },
  info: { label: "참고", icon: "ℹ️" },
  tip: { label: "팁", icon: "💡" },
  key: { label: "핵심", icon: "🎯" },
  important: { label: "핵심", icon: "🎯" },
  goal: { label: "목표", icon: "🧭" },
  say: { label: "이렇게 말한다", icon: "🗣️" },
  ask: { label: "ASK", icon: "🙋" },
  warning: { label: "주의", icon: "⚠️" },
  caution: { label: "주의", icon: "⚠️" },
  danger: { label: "함정", icon: "🚫" },
};

const MARKER_RE = /^\s*\[!(\w+)\]\s*(.*?)\s*$/;

function isElement(node: RootContent, tag?: string): node is Element {
  return node.type === "element" && (!tag || (node as Element).tagName === tag);
}

function transform(node: Element): void {
  // 첫 문단(p)을 찾는다.
  const firstP = node.children.find((c): c is Element => isElement(c, "p"));
  if (!firstP) return;

  const head = firstP.children[0];
  if (!head || head.type !== "text") return;
  const textNode = head as Text;

  // 첫 줄만 마커로 검사 (나머지는 soft break로 같은 문단에 붙어 있을 수 있음).
  const nlIdx = textNode.value.indexOf("\n");
  const firstLine = nlIdx === -1 ? textNode.value : textNode.value.slice(0, nlIdx);
  const m = firstLine.match(MARKER_RE);
  if (!m) return;

  const type = m[1].toLowerCase();
  const spec = CALLOUTS[type] ?? { label: type.toUpperCase(), icon: "🔹" };
  const customTitle = (m[2] ?? "").trim();

  // 마커 줄을 본문에서 제거.
  textNode.value = nlIdx === -1 ? "" : textNode.value.slice(nlIdx + 1);
  if (textNode.value === "") firstP.children.shift();
  if (firstP.children.length === 0) {
    node.children = node.children.filter((c) => c !== firstP);
  }

  const titleEl: Element = {
    type: "element",
    tagName: "div",
    properties: { className: ["callout-title"] },
    children: [
      {
        type: "element",
        tagName: "span",
        properties: { className: ["callout-icon"] },
        children: [{ type: "text", value: spec.icon }],
      },
      { type: "text", value: " " + (customTitle || spec.label) },
    ],
  };

  node.tagName = "div";
  node.properties = {
    ...(node.properties ?? {}),
    className: ["callout", `callout-${type}`],
    "data-callout": type,
  };
  node.children = [titleEl, ...node.children];
}

/**
 * Rehype 플러그인: blockquote → callout div. 재귀 walk로 중첩 blockquote도 처리.
 */
export const rehypeCallouts: Plugin<[], Root> = () => (tree) => {
  const walk = (node: Root | Element) => {
    for (const child of node.children) {
      if (child.type === "element") {
        const el = child as Element;
        if (el.tagName === "blockquote") transform(el);
        walk(el);
      }
    }
  };
  walk(tree);
};
