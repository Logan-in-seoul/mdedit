import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";

vi.mock("../lib/api", () => ({
  api: {
    filesFlat: vi.fn(),
    starred: vi.fn(),
    star: vi.fn(),
    unstar: vi.fn(),
    search: vi.fn(),
  },
}));

import { api } from "../lib/api";
import { FlatList } from "./FlatList";

const now = Date.now() / 1000;
const entry = (name: string) => ({
  path: `vault://${name}.md`,
  name: `${name}.md`,
  mtime: now,
  size: 10,
  title: name,
});
const mocked = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

beforeEach(() => {
  Object.values(mocked).forEach((f) => f.mockReset());
  mocked.filesFlat.mockResolvedValue([entry("alpha"), entry("beta"), entry("gamma")]);
  mocked.starred.mockResolvedValue({ paths: ["vault://beta.md"], files: [entry("beta")] });
  mocked.star.mockResolvedValue({});
  mocked.unstar.mockResolvedValue({});
});

describe("FlatList 별표 목록", () => {
  it("별표 파일을 고정 섹션에 먼저 보여 준다", async () => {
    render(<FlatList onSelect={() => {}} selected={null} />);
    await screen.findByText("★ 고정");
    const names = screen.getAllByText(/^(alpha|beta|gamma)$/).map((n) => n.textContent);
    expect(names).toEqual(["beta", "alpha", "gamma"]);
  });

  it("별표 버튼으로 해제하면 API를 호출하고 고정 섹션이 사라진다", async () => {
    render(<FlatList onSelect={() => {}} selected={null} />);
    const btn = await screen.findByLabelText("별표 해제");
    fireEvent.click(btn);
    expect(mocked.unstar).toHaveBeenCalledWith("vault://beta.md");
    await waitFor(() => expect(screen.queryByText("★ 고정")).toBeNull());
  });

  it("행 클릭은 onSelect로 경로를 전달한다", async () => {
    const onSelect = vi.fn();
    render(<FlatList onSelect={onSelect} selected={null} />);
    fireEvent.click(await screen.findByText("alpha"));
    expect(onSelect).toHaveBeenCalledWith("vault://alpha.md");
  });
});

describe("FlatList 검색창", () => {
  it("입력하면 검색 API를 호출하고 결과를 그린다", async () => {
    mocked.search.mockResolvedValue({
      query: "hello",
      total: 1,
      truncated: false,
      hits: [
        { path: "vault://alpha.md", name: "alpha.md", line: 3, snippet: "say hello world", match_start: 4, match_end: 9 },
      ],
    });
    render(<FlatList onSelect={() => {}} selected={null} />);
    const input = await screen.findByPlaceholderText(/개 파일/);
    fireEvent.change(input, { target: { value: "hello" } });
    await screen.findByText("L3");
    expect(mocked.search).toHaveBeenCalledWith("hello", undefined, 200, undefined, undefined);
    expect(screen.getByText("hello").tagName).toBe("MARK");
  });

  it("정규식 토글을 켜면 regex 모드로 검색한다", async () => {
    mocked.search.mockResolvedValue({ query: "a.c", total: 0, truncated: false, hits: [] });
    render(<FlatList onSelect={() => {}} selected={null} />);
    const input = await screen.findByPlaceholderText(/개 파일/);
    fireEvent.click(screen.getByRole("button", { name: ".*" }));
    fireEvent.change(input, { target: { value: "a.c" } });
    await screen.findByText("결과 없음");
    expect(mocked.search).toHaveBeenCalledWith("a.c", undefined, 200, undefined, undefined, true);
  });

  it("정규식 거부 시 안내 문구를 보여 준다", async () => {
    mocked.search.mockRejectedValue(new Error("400"));
    render(<FlatList onSelect={() => {}} selected={null} />);
    const input = await screen.findByPlaceholderText(/개 파일/);
    fireEvent.click(screen.getByRole("button", { name: ".*" }));
    fireEvent.change(input, { target: { value: "(a+)+" } });
    await screen.findByText(/정규식을 사용할 수 없습니다/);
  });
});
