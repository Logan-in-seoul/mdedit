import { describe, expect, it } from "vitest";
import { extractFromDom } from "./outline";

function build(html: string): HTMLElement {
  const c = document.createElement("div");
  c.innerHTML = html;
  return c;
}

describe("extractFromDom", () => {
  it("섹션 접기 토글 글리프를 제목에 넣지 않는다", () => {
    const c = build('<h2><button class="fold-toggle">▾</button>대본</h2>');
    expect(extractFromDom(c).map((i) => i.text)).toEqual(["대본"]);
  });

  it("같은 제목이 반복되어도 id가 겹치지 않는다", () => {
    const c = build("<h2>배경</h2><p>a</p><h2>배경</h2>");
    const ids = extractFromDom(c).map((i) => i.id);
    expect(new Set(ids).size).toBe(2);
    expect(c.querySelectorAll(`[data-outline-id="${ids[1]}"]`).length).toBe(1);
  });

  it("다시 추출해도 이미 붙인 id를 유지한다", () => {
    const c = build("<h1>A</h1><h2>B</h2>");
    const first = extractFromDom(c).map((i) => i.id);
    expect(extractFromDom(c).map((i) => i.id)).toEqual(first);
  });
});
