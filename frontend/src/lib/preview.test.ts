import { describe, expect, it } from "vitest";
import { previewText } from "./preview";

describe("previewText", () => {
  it("헤딩 마커와 코드 펜스를 제거하고 첫 줄들만 남긴다", () => {
    const body = "# 제목\n\n본문 첫 줄\n```py\nprint(1)\n```\n둘째 줄";
    expect(previewText(body)).toBe("제목\n본문 첫 줄\n둘째 줄");
  });
  it("줄 수와 글자 수를 제한한다", () => {
    const many = Array.from({ length: 20 }, (_, i) => `줄${i}`).join("\n");
    expect(previewText(many).split("\n")).toHaveLength(6);
    const long = "가".repeat(1000);
    const out = previewText(long);
    expect(out.length).toBe(321);
    expect(out.endsWith("…")).toBe(true);
  });
  it("빈 본문은 빈 문자열", () => {
    expect(previewText("\n\n")).toBe("");
  });
});
