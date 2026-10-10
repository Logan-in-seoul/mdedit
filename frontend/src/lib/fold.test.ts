import { beforeEach, describe, expect, it } from "vitest";
import { loadFolded, setupFolding } from "./fold";

function build(): HTMLElement {
  const c = document.createElement("div");
  c.innerHTML =
    "<h1>A</h1><p id='a'>a</p><h2>A1</h2><p id='a1'>a1</p><h1>B</h1><p id='b'>b</p>";
  document.body.appendChild(c);
  return c;
}
const hidden = (c: HTMLElement, id: string) =>
  c.querySelector("#" + id)!.classList.contains("fold-hidden");

describe("setupFolding", () => {
  beforeEach(() => {
    localStorage.clear();
    document.body.innerHTML = "";
  });

  it("접으면 다음 같은 레벨 헤딩 전까지 숨기고 하위 헤딩도 포함한다", () => {
    const c = build();
    setupFolding(c, "n.md");
    (c.querySelector("h1 .fold-toggle") as HTMLElement).click();
    expect(hidden(c, "a")).toBe(true);
    expect(hidden(c, "a1")).toBe(true);
    expect(hidden(c, "b")).toBe(false);
    (c.querySelector("h1 .fold-toggle") as HTMLElement).click();
    expect(hidden(c, "a1")).toBe(false);
  });

  it("접힘 상태를 노트별로 저장하고 복원한다", () => {
    const c = build();
    setupFolding(c, "n.md");
    (c.querySelectorAll("h2 .fold-toggle")[0] as HTMLElement).click();
    expect(loadFolded("n.md").size).toBe(1);
    expect(loadFolded("other.md").size).toBe(0);

    c.remove();
    const c2 = build();
    setupFolding(c2, "n.md");
    expect(hidden(c2, "a1")).toBe(true);
    expect(hidden(c2, "a")).toBe(false);
  });

  it("정리 함수는 토글과 숨김을 제거한다", () => {
    const c = build();
    const cleanup = setupFolding(c, "n.md");
    (c.querySelector("h1 .fold-toggle") as HTMLElement).click();
    cleanup();
    expect(c.querySelectorAll(".fold-toggle").length).toBe(0);
    expect(hidden(c, "a")).toBe(false);
  });
});
