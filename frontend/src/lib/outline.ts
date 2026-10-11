// Outline extraction utility.
// Pulls H1-H6 headings either from a markdown source string or directly
// from a rendered DOM container. Used by OutlineSidebar for the heading tree.

export interface OutlineItem {
  level: number; // 1..6
  text: string;
  id: string; // anchor id (slugified)
  index: number; // sequential index, useful as React key
}

const SLUG_BAD = /[^\p{L}\p{N}\s-]/gu;
const SLUG_SPACE = /\s+/g;

export function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(SLUG_BAD, "")
    .trim()
    .replace(SLUG_SPACE, "-")
    .slice(0, 80);
}

// Extract headings from raw markdown (ignores code blocks).
export function extractHeadings(markdown: string): OutlineItem[] {
  const lines = markdown.split(/\r?\n/);
  const items: OutlineItem[] = [];
  let inFence = false;
  let fenceMarker = "";

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const fenceMatch = /^(\s{0,3})(`{3,}|~{3,})/.exec(line);
    if (fenceMatch) {
      if (!inFence) {
        inFence = true;
        fenceMarker = fenceMatch[2][0];
      } else if (line.trim().startsWith(fenceMarker)) {
        inFence = false;
        fenceMarker = "";
      }
      continue;
    }
    if (inFence) continue;

    const headingMatch = /^(#{1,6})\s+(.+?)\s*#*\s*$/.exec(line);
    if (!headingMatch) continue;
    const level = headingMatch[1].length;
    const text = headingMatch[2].trim();
    if (!text) continue;
    items.push({
      level,
      text,
      id: slugify(text) || `heading-${items.length}`,
      index: items.length,
    });
  }
  return items;
}

// 헤딩 안에 붙는 섹션 접기 토글(fold.ts)의 글리프는 제목이 아니다.
function headingText(node: Element): string {
  let text = "";
  node.childNodes.forEach((child) => {
    if (child instanceof Element && child.classList.contains("fold-toggle")) return;
    text += child.textContent || "";
  });
  return text.trim();
}

// Extract headings from a rendered DOM container (the reader body).
// Each H1-H6 element receives a stable data-outline-id so that clicks can
// scroll back to it via querySelector.
export function extractFromDom(container: HTMLElement): OutlineItem[] {
  const nodes = container.querySelectorAll<HTMLHeadingElement>(
    "h1, h2, h3, h4, h5, h6",
  );
  const items: OutlineItem[] = [];
  nodes.forEach((node, index) => {
    const text = headingText(node);
    if (!text) return;
    const level = parseInt(node.tagName.slice(1), 10);
    let id = node.getAttribute("data-outline-id");
    if (!id) {
      // 같은 제목이 반복되어도 각자 자기 자리로 가도록 순번을 붙인다
      id = `${index}-${slugify(text) || "heading"}`;
      node.setAttribute("data-outline-id", id);
    }
    items.push({ level, text, id, index: items.length });
  });
  return items;
}
