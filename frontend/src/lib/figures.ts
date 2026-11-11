/**
 * 그림과 표의 표현 충실성 (v0.11).
 *
 *  1. 로컬 그림: 문서가 상대 경로로 거는 그림을 /api/asset 주소로 바꾼다. 전에는 앱 주소 기준으로
 *     풀려 서버가 index.html을 돌려줬고 그림 자리가 빈 칸이 됐다.
 *  2. 그림 단락: 그림 하나만 있는 단락은 <figure>로 바꾸고 대체 문구를 캡션으로 단다.
 *  3. 숫자 열: 칸 대부분이 숫자인 표 열은 오른쪽 정렬과 고정폭 숫자로 그린다.
 *
 * sanitize 뒤에 도는 신뢰 플러그인이다. 주소는 서버가 다시 루트 안인지 확인한다.
 */
import type { Plugin } from "unified";
import type { Root, Element, ElementContent, Text } from "hast";
import type { VFile } from "vfile";
import { visit, SKIP } from "unist-util-visit";
import { hasScheme, resolveRelative } from "./links";

export interface DocData {
  /** 지금 문서의 가상 경로 (`home://a/b.md`, `ext:///abs/b.md`) */
  docPath?: string;
  /** 문서가 바뀌면 그림도 새로 받도록 주소에 붙이는 값 */
  assetVersion?: number;
}

const VIDEO_EXT = /\.(mp4|webm)$/i;
const IMAGE_EXT = /\.(png|jpe?g|gif|webp|avif|bmp|svg)$/i;

function safeDecode(s: string): string {
  try {
    return decodeURI(s);
  } catch {
    return s;
  }
}

/** 문서 위치를 기준으로 그림 주소를 /api/asset 주소로 푼다. 바꿀 필요가 없거나 못 풀면 null. */
export function assetUrl(docPath: string | undefined, src: string, version?: number): string | null {
  if (!src) return null;
  const v = version ? `&v=${version}` : "";
  if (/^file:\/\//i.test(src)) {
    return `/api/asset?abs=${encodeURIComponent(safeDecode(src.replace(/^file:\/\//i, "")))}${v}`;
  }
  if (hasScheme(src) || src.startsWith("//") || src.startsWith("/api/")) return null;
  const clean = safeDecode(src.split("#")[0].split("?")[0]);
  if (clean.startsWith("/")) {
    return `/api/asset?abs=${encodeURIComponent(clean)}${v}`;
  }
  if (!docPath) return null;
  const resolved = resolveRelative(docPath, clean);
  if (!resolved) return null;
  return `/api/asset?path=${encodeURIComponent(resolved)}${v}`;
}

/** `캡션|600` 꼴의 대체 문구에서 폭을 떼어 낸다 (Obsidian 표기). */
export function splitAltWidth(alt: string): { caption: string; width?: number } {
  const m = /^(.*?)\s*\|\s*(\d{2,4})(?:x\d{2,4})?\s*$/.exec(alt);
  if (m) return { caption: m[1].trim(), width: Number(m[2]) };
  if (/^\d{2,4}$/.test(alt.trim())) return { caption: "", width: Number(alt.trim()) };
  return { caption: alt };
}

function textOf(node: ElementContent): string {
  if (node.type === "text") return node.value;
  if (node.type === "element") return node.children.map(textOf).join("");
  return "";
}

/** 로컬 그림 주소 풀기, ![[그림.png]] 임베드를 그림으로, 영상 확장자는 <video>로. */
export const rehypeLocalAssets: Plugin<[], Root> = () => (tree: Root, file: VFile) => {
  const data = (file.data ?? {}) as DocData;
  visit(tree, "element", (node: Element, index, parent) => {
    // ![[그림.png|600]] — 위키 임베드가 그림을 가리키면 문서 임베드 대신 그림으로 그린다
    if (node.tagName === "embed-link") {
      const title = String(node.properties?.title ?? "");
      if (!IMAGE_EXT.test(title) && !VIDEO_EXT.test(title)) return;
      const display = String(node.properties?.display ?? "");
      node.tagName = "img";
      node.properties = { src: title, alt: display && display !== title ? display : "" };
    }
    if (node.tagName !== "img") return;
    const props = node.properties ?? {};
    const src = String(props.src ?? "");
    const url = assetUrl(data.docPath, src, data.assetVersion);
    if (url) props.src = url;
    const { caption, width } = splitAltWidth(String(props.alt ?? ""));
    if (width && props.width == null) {
      props.width = width;
      props.alt = caption;
    }
    props.loading = "lazy";
    props.decoding = "async";
    if (props.className == null) props.className = ["md-img"];
    node.properties = props;
    if (VIDEO_EXT.test(src) && parent && index != null) {
      parent.children[index] = {
        type: "element",
        tagName: "video",
        properties: { src: props.src, controls: true, preload: "metadata", className: ["md-video"] },
        children: [],
        position: node.position,
      } as Element;
      return SKIP;
    }
  });
};

function isBlank(n: ElementContent): boolean {
  return n.type === "text" && !n.value.trim();
}

/** 그림 하나만 있는 단락을 <figure>로. 링크로 감싼 그림도 받는다. */
export const rehypeFigures: Plugin<[], Root> = () => (tree: Root) => {
  visit(tree, "element", (node: Element, index, parent) => {
    if (node.tagName !== "p" || !parent || index == null) return;
    const kids = node.children.filter((c) => !isBlank(c));
    if (kids.length !== 1 || kids[0].type !== "element") return;
    let media = kids[0] as Element;
    if (media.tagName === "a") {
      const inner = media.children.filter((c) => !isBlank(c));
      if (inner.length !== 1 || inner[0].type !== "element") return;
      if (!["img", "video"].includes((inner[0] as Element).tagName)) return;
    } else if (!["img", "video"].includes(media.tagName)) {
      return;
    }
    const img = media.tagName === "a" ? (media.children.find((c) => c.type === "element") as Element) : media;
    const alt = String(img.properties?.alt ?? "").trim();
    const children: ElementContent[] = [media];
    if (alt && !IMAGE_EXT.test(alt)) {
      children.push({
        type: "element",
        tagName: "figcaption",
        properties: {},
        children: [{ type: "text", value: alt } as Text],
      });
    }
    parent.children[index] = {
      type: "element",
      tagName: "figure",
      properties: { ...node.properties, className: ["md-figure"] },
      children,
      position: node.position,
    } as Element;
    return SKIP;
  });
};

// 1,234 / 12.5% / 70.61억 / -3건 / ₩1,000 / 1.2배 / +3.5%p / 2.4x
const NUMERIC_RE =
  /^[(+\-−±~]?\s*[₩$€¥]?\s*\d[\d,]*(\.\d+)?\s*(%p?|퍼센트(포인트)?|pp|bp|원|천원|만원|억원?|조원?|만|천|건|개|명|일|회|배|x|×|시간|분|초|점|위|곳|팀|주|개월|년|ms|s|KB|MB|GB)?\)?$/i;

export function isNumericCell(text: string): boolean {
  const t = text.replace(/\s+/g, " ").trim();
  if (!t) return false;
  return NUMERIC_RE.test(t);
}

/** 칸 70% 이상이 숫자인 열에 num 클래스를 단다. 작성자가 정렬을 정한 열은 건드리지 않는다. */
export const rehypeNumericColumns: Plugin<[], Root> = () => (tree: Root) => {
  visit(tree, "element", (table: Element) => {
    if (table.tagName !== "table") return;
    const rows: Element[] = [];
    visit(table, "element", (el: Element) => {
      if (el.tagName === "tr") rows.push(el);
    });
    if (rows.length < 2) return;
    const cellsOf = (tr: Element) =>
      tr.children.filter((c): c is Element => c.type === "element" && (c.tagName === "td" || c.tagName === "th"));
    const body = rows.filter((tr) => cellsOf(tr).some((c) => c.tagName === "td"));
    if (body.length === 0) return;
    const cols = Math.max(...rows.map((r) => cellsOf(r).length));
    for (let col = 0; col < cols; col++) {
      let filled = 0;
      let numeric = 0;
      let aligned = false;
      for (const tr of body) {
        const cell = cellsOf(tr)[col];
        if (!cell) continue;
        if (cell.properties?.align || cell.properties?.style) aligned = true;
        const text = textOf(cell).trim();
        if (!text || text === "-" || text === "—") continue;
        filled++;
        if (isNumericCell(text)) numeric++;
      }
      if (aligned || filled === 0 || numeric / filled < 0.7) continue;
      for (const tr of rows) {
        const cell = cellsOf(tr)[col];
        if (!cell) continue;
        const cls = cell.properties?.className;
        const list = Array.isArray(cls) ? cls.map(String) : cls ? [String(cls)] : [];
        cell.properties = { ...cell.properties, className: [...list, "num"] };
      }
    }
    return SKIP;
  });
};
