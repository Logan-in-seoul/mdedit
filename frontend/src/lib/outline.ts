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

// Extract headings from a rendered DOM container (the reader body).
// Each H1-H6 element receives a stable data-outline-id so that clicks can
// scroll back to it via querySelector.
export function extractFromDom(container: HTMLElement): OutlineItem[] {
  const nodes = container.querySelectorAll<HTMLHeadingElement>(
    "h1, h2, h3, h4, h5, h6",
  );
  const items: OutlineItem[] = [];
  nodes.forEach((node, index) => {
    const text = (node.textContent || "").trim();
    if (!text) return;
    const level = parseInt(node.tagName.slice(1), 10);
    let id = node.getAttribute("data-outline-id");
    if (!id) {
      id = slugify(text) || `heading-${index}`;
      node.setAttribute("data-outline-id", id);
    }
    items.push({ level, text, id, index: items.length });
  });
  return items;
}
