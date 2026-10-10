import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { WikiLink } from "./WikiLink";
import { clearPreviewCache } from "../lib/preview";

function mockFetch() {
  const fn = vi.fn(async (url: string) => {
    if (url.startsWith("/api/resolve"))
      return new Response(JSON.stringify({ path: "notes/target.md" }), { status: 200 });
    if (url.startsWith("/api/file"))
      return new Response(
        JSON.stringify({ path: "notes/target.md", body: "# 대상\n\n첫 문단입니다." }),
        { status: 200 },
      );
    return new Response("{}", { status: 404 });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("WikiLink 호버 프리뷰", () => {
  beforeEach(() => clearPreviewCache());
  afterEach(() => vi.unstubAllGlobals());

  it("호버하면 대상 노트의 첫 줄을 팝오버로 보여주고, 벗어나면 숨긴다", async () => {
    const fetchMock = mockFetch();
    render(<WikiLink title="target" />);
    const link = await screen.findByRole("button");
    await vi.waitFor(() => expect(link.getAttribute("data-wiki-path")).toBe("notes/target.md"));
    const user = userEvent.setup();
    await user.hover(link);
    const tip = await screen.findByRole("tooltip", {}, { timeout: 2000 });
    expect(tip.textContent).toContain("첫 문단입니다.");
    expect(fetchMock.mock.calls.some(([u]) => String(u).includes("/api/file"))).toBe(true);
    await act(async () => {
      await user.unhover(link);
    });
    expect(screen.queryByRole("tooltip")).toBeNull();
  });

  it("해결되지 않은 링크는 프리뷰를 요청하지 않는다", async () => {
    const fetchMock = vi.fn(async (_u: string) => new Response(JSON.stringify({ path: null }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<WikiLink title="nope" />);
    const link = await screen.findByRole("button");
    const user = userEvent.setup();
    await user.hover(link);
    await new Promise((r) => setTimeout(r, 500));
    expect(screen.queryByRole("tooltip")).toBeNull();
    expect(fetchMock.mock.calls.some(([u]) => String(u).includes("/api/file"))).toBe(false);
  });
});
