/**
 * scr-plugins — 가독성 표기 rehype 플러그인 모음.
 *
 * mdedit는 /scr이 생성한 발언 대본을 미팅 중 띄워놓고 읽는 텔레프롬프터다.
 * 흘긋 봐도 다음이 구분되도록 표기를 시각화한다.
 *
 *  1. ==하이라이트==      → <mark>            (단색 형광)
 *  2. (소개)(질문) 등 라벨  → <span.scr-label>  (타입군별 색 배지)
 *  3. *영어 백업* 단락      → <p.scr-en>        (muted 이탤릭)
 *  4. "만약 …하면:" 분기    → <p.scr-branch>    (좌측 테두리 + 틴트 블록)
 *
 * 볼드(**)와 이탤릭(*)은 remark-gfm가 이미 처리하므로 여기선 손대지 않고
 * CSS prose 스타일만 styles/global.css에서 다듬는다.
 *
 * 감지는 보수적으로(narrative-context). 라벨은 curated set + 단락 첫머리,
 * 분기는 "만약" 시작으로 제한해 일반 문서 오감지를 막는다.
 */
import type { Plugin } from "unified";
import type { Root, Element, Text, RootContent, Parent } from "hast";
import { visitParents, SKIP } from "unist-util-visit-parents";

/* ============ 1. ==하이라이트== ============ */

// ==텍스트== — 안에 = 를 포함하지 않고, 빈 문자열 아님. 비탐욕.
const HIGHLIGHT_RE = /==([^=\n]+?)==/g;

/**
 * Rehype 플러그인: 텍스트 노드에서 ==...== 를 <mark>로 치환.
 * code/pre 자손은 제외 (TagChip과 동일 규칙).
 */
export const rehypeHighlight: Plugin<[], Root> = () => (tree) => {
  visitParents(tree, "text", (node: Text, ancestors: Parent[]) => {
    for (const anc of ancestors) {
      if (anc.type === "element") {
        const tag = (anc as Element).tagName;
        if (tag === "code" || tag === "pre" || tag === "mark") return;
      }
    }
    const parent = ancestors[ancestors.length - 1] as Parent | undefined;
    if (!parent) return;

    const value = node.value;
    if (!value || !value.includes("==")) return;

    const replacements: RootContent[] = [];
    let lastIdx = 0;
    let match: RegExpExecArray | null;
    HIGHLIGHT_RE.lastIndex = 0;
    let found = false;

    while ((match = HIGHLIGHT_RE.exec(value)) !== null) {
      const inner = match[1];
      if (!inner) continue;
      found = true;
      if (match.index > lastIdx) {
        replacements.push({ type: "text", value: value.slice(lastIdx, match.index) } as Text);
      }
      replacements.push({
        type: "element",
        tagName: "mark",
        properties: {},
        children: [{ type: "text", value: inner } as Text],
      } as Element);
      lastIdx = match.index + match[0].length;
    }

    if (!found) return;

    if (lastIdx < value.length) {
      replacements.push({ type: "text", value: value.slice(lastIdx) } as Text);
    }

    const idx = parent.children.indexOf(node as RootContent);
    if (idx < 0) return;
    (parent.children as RootContent[]).splice(idx, 1, ...replacements);
    return [SKIP, idx + replacements.length];
  });
};

/* ============ 2~4. /scr 시맨틱 ============ */

// 콘텐츠 타입 라벨 → 타입군. curated set만 칩으로 렌더(일반 문서 오감지 방지).
// 현행 /scr 표준 라벨(소개·프레임·설명·묻는다·답에 따라·되물으면·입장·마무리)을
// 1차로 두고, 구형 스크립트 라벨(어젠다·배경·질문·후속·답변)을 별칭으로 함께 받는다.
const SCR_LABEL_GROUP: Record<string, string> = {
  // 오프닝·자기소개
  소개: "intro",
  오프닝: "intro",
  // 판·어젠다·레버리지 깔기
  프레임: "frame",
  어젠다: "frame", // 구형
  기준: "frame",
  레버리지: "frame",
  제안: "frame",
  // 질문 흐름
  묻는다: "ask",
  질문: "ask", // 구형
  확인: "ask",
  후속: "ask", // 구형
  "답에 따라": "ask",
  // 우리가 답하거나 포지션을 내는 말
  되물으면: "answer",
  답변: "answer", // 구형
  입장: "answer",
  // 배경·설명·정리
  설명: "context",
  배경: "context", // 구형
  정리: "context",
  레퍼런스: "context",
  // 마무리
  마무리: "close",
  // 우려·리스크·눌러야 할 카드
  우려: "caution",
  리스크: "caution",
  카드: "caution",
};

// 단락 첫머리 "(라벨) " 패턴. 라벨은 한글 1~8자.
const LABEL_LEAD_RE = /^\(([가-힣]{1,8})\)(\s*)/;

/** hast element/text의 텍스트를 이어붙인다(얕은 깊이까지). */
function textOf(node: RootContent): string {
  if (node.type === "text") return (node as Text).value;
  if (node.type === "element") {
    const el = node as Element;
    return (el.children || []).map((c) => textOf(c as RootContent)).join("");
  }
  return "";
}

/** 공백만 있는 텍스트 노드인지. */
function isBlank(node: RootContent): boolean {
  return node.type === "text" && /^\s*$/.test((node as Text).value);
}

function addClass(el: Element, cls: string) {
  el.properties = el.properties ?? {};
  const cur = el.properties.className;
  if (Array.isArray(cur)) {
    if (!cur.includes(cls)) cur.push(cls);
  } else if (typeof cur === "string" && cur) {
    el.properties.className = cur.split(/\s+/).concat(cls);
  } else {
    el.properties.className = [cls];
  }
}

/**
 * Rehype 플러그인: p / li 단락에 /scr 시맨틱을 적용한다.
 *  - 첫머리 curated 라벨 → scr-label 배지 span으로 치환
 *  - 단락 전체가 이탤릭 하나 → scr-en 클래스(영어 백업)
 *  - "만약 …" 시작 → scr-branch 클래스(분기 블록)
 */
export const rehypeScrSemantics: Plugin<[], Root> = () => (tree) => {
  const walk = (node: Root | Element) => {
    const children = node.children as RootContent[] | undefined;
    if (!children) return;
    for (const child of children) {
      if (child.type !== "element") continue;
      const el = child as Element;

      if (el.tagName === "p" || el.tagName === "li") {
        applyLabel(el);
        applyBranch(el);
      }
      if (el.tagName === "p") {
        applyEnglishBackup(el);
      }

      // 자손도 순회(중첩 리스트 등)
      walk(el);
    }
  };
  walk(tree);
};

function makeLabelChip(label: string, group: string): Element {
  return {
    type: "element",
    tagName: "span",
    properties: { className: ["scr-label", `scr-label-${group}`] },
    children: [{ type: "text", value: label } as Text],
  };
}

/**
 * 첫머리 라벨 → scr-label 칩. curated set만. 두 형식 지원:
 *  - form 1 (현행 /scr): 굵은 단어 라벨  **소개**  (단독 줄 또는 줄머리)
 *  - form 2 (구형 스크립트): 괄호 라벨   (소개) 발언
 */
function applyLabel(el: Element) {
  const first = el.children[0];
  if (!first) return;

  // form 1: 굵은 단어 라벨 — 첫 자식이 <strong>이고 그 텍스트가 curated 라벨
  if (first.type === "element" && (first as Element).tagName === "strong") {
    const label = textOf(first as RootContent).trim();
    const group = SCR_LABEL_GROUP[label];
    if (!group) return;
    el.children.splice(0, 1, makeLabelChip(label, group));
    return;
  }

  // form 2: 괄호 라벨 — 첫 텍스트가 "(라벨) "로 시작
  if (first.type === "text") {
    const m = LABEL_LEAD_RE.exec((first as Text).value);
    if (!m) return;
    const label = m[1];
    const group = SCR_LABEL_GROUP[label];
    if (!group) return; // curated 아니면 변환 안 함

    const rest = (first as Text).value.slice(m[0].length);
    const newNodes: Element["children"] = [makeLabelChip(label, group)];
    if (rest) newNodes.push({ type: "text", value: rest } as Text);
    el.children.splice(0, 1, ...newNodes);
  }
}

/**
 * 단락 children이 (공백 제외) 이탤릭 em 하나뿐이고 라틴 문자를 포함하면
 * 영어 백업으로 표시. 라틴 조건으로 순수 한국어 이탤릭 인용 단락의 오감지를 막는다.
 */
function applyEnglishBackup(el: Element) {
  const meaningful = el.children.filter((c) => !isBlank(c as RootContent));
  if (meaningful.length !== 1) return;
  const only = meaningful[0];
  if (only.type !== "element" || (only as Element).tagName !== "em") return;
  if (!/[A-Za-z]/.test(textOf(only as RootContent))) return; // 영어 백업만
  addClass(el, "scr-en");
}

/**
 * /scr 분기 cue 단락/항목이면 분기 블록으로 표시.
 * "만약" 또는 "상대가" 로 시작 + 조건 cue("…하면:", "…한다면:", 또는 콜론 종결)를
 * 모두 요구해 "만약에도 …" 같은 일반 문장 오감지를 막는다.
 * 현행 /scr은 "답에 따라" 라벨 아래 "상대가 X하면: 발언" 불릿(li)으로 깐다.
 */
const BRANCH_CUE_RE = /하면\s*[:：]|한다면\s*[:：]|[:：]\s*$/;
function applyBranch(el: Element) {
  // 라벨 치환 후일 수 있으므로 텍스트 전체로 판단
  const t = textOf(el as unknown as RootContent).trimStart();
  if ((t.startsWith("만약") || t.startsWith("상대가")) && BRANCH_CUE_RE.test(t)) {
    addClass(el, "scr-branch");
  }
}
