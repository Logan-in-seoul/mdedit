import { describe, expect, it } from "vitest";
import { hasScheme, isMarkdownHref, resolveRelative } from "./links";

describe("resolveRelative", () => {
  it("같은 폴더와 하위 폴더", () => {
    expect(resolveRelative("home://a/b/doc.md", "other.md")).toBe("home://a/b/other.md");
    expect(resolveRelative("home://a/b/doc.md", "./sub/x.md")).toBe("home://a/b/sub/x.md");
  });

  it("상위 폴더로 올라간다", () => {
    expect(resolveRelative("home://a/b/doc.md", "../x.md")).toBe("home://a/x.md");
  });

  it("루트 밖으로 나가면 null", () => {
    expect(resolveRelative("home://doc.md", "../x.md")).toBeNull();
  });

  it("/로 시작하면 루트 기준", () => {
    expect(resolveRelative("home://a/b/doc.md", "/c/x.md")).toBe("home://c/x.md");
  });

  it("vault 밖 문서는 절대 경로를 유지한다", () => {
    expect(resolveRelative("ext:///tmp/a/doc.md", "../x.md")).toBe("ext:///tmp/x.md");
  });
});

describe("링크 판별", () => {
  it("md 확장자와 스킴", () => {
    expect(isMarkdownHref("a/b.MD")).toBe(true);
    expect(isMarkdownHref("a/b.png")).toBe(false);
    expect(hasScheme("https://x.y")).toBe(true);
    expect(hasScheme("mailto:a@b.c")).toBe(true);
    expect(hasScheme("./a.md")).toBe(false);
  });
});
