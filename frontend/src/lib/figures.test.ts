import { describe, expect, it } from "vitest";
import { unified } from "unified";
import remarkParse from "remark-parse";
import remarkGfm from "remark-gfm";
import remarkRehype from "remark-rehype";
import rehypeStringify from "rehype-stringify";
import { assetUrl, isNumericCell, rehypeFigures, rehypeLocalAssets, rehypeNumericColumns, splitAltWidth } from "./figures";

const DOC = "home://workspace/cms/docs/2026-11-09-최저가보상-운영안.md";

async function html(md: string, docPath = DOC): Promise<string> {
  const file = await unified()
    .use(remarkParse)
    .use(remarkGfm)
    .use(remarkRehype)
    .use(rehypeLocalAssets)
    .use(rehypeFigures)
    .use(rehypeNumericColumns)
    .use(rehypeStringify)
    .process({ value: md, data: { docPath } });
  return String(file);
}

describe("assetUrl", () => {
  it("문서 폴더 기준 상대 경로를 /api/asset 주소로 푼다", () => {
    expect(assetUrl(DOC, "workflows/best-price/fig-ops-flow.png")).toBe(
      `/api/asset?path=${encodeURIComponent("home://workspace/cms/docs/workflows/best-price/fig-ops-flow.png")}`,
    );
  });

  it("상위 폴더와 한글 파일 이름, 퍼센트 인코딩", () => {
    const url = assetUrl(DOC, "../img/%EA%B7%B8%EB%A6%BC.png")!;
    expect(decodeURIComponent(url)).toContain("home://workspace/cms/img/그림.png");
  });

  it("절대 경로와 file 주소는 abs로", () => {
    expect(assetUrl(DOC, "/home/logan/x.png")).toBe(`/api/asset?abs=${encodeURIComponent("/home/logan/x.png")}`);
    expect(assetUrl(DOC, "file:///home/logan/x.png")).toBe(`/api/asset?abs=${encodeURIComponent("/home/logan/x.png")}`);
  });

  it("바깥 주소와 data 주소는 그대로 둔다", () => {
    expect(assetUrl(DOC, "https://example.com/a.png")).toBeNull();
    expect(assetUrl(DOC, "data:image/png;base64,AAAA")).toBeNull();
  });

  it("ext:// 문서는 그 폴더 기준", () => {
    expect(decodeURIComponent(assetUrl("ext:///tmp/x/draft.md", "a.png")!)).toContain("ext:///tmp/x/a.png");
  });

  it("문서 판 값을 붙인다", () => {
    expect(assetUrl(DOC, "a.png", 123)).toMatch(/&v=123$/);
  });
});

describe("splitAltWidth", () => {
  it("캡션|폭", () => {
    expect(splitAltWidth("흐름도|600")).toEqual({ caption: "흐름도", width: 600 });
    expect(splitAltWidth("그냥 캡션")).toEqual({ caption: "그냥 캡션" });
  });
});

describe("그림 단락", () => {
  it("그림 하나만 있는 단락은 figure와 캡션이 된다", async () => {
    const out = await html("![트랙별 흐름과 담당 팀](workflows/best-price/fig-ops-flow.png)");
    expect(out).toContain('<figure class="md-figure">');
    expect(out).toContain("<figcaption>트랙별 흐름과 담당 팀</figcaption>");
    expect(out).toContain("/api/asset?path=");
    expect(out).toContain('class="md-img"');
  });

  it("문장 안의 그림은 단락 그대로", async () => {
    const out = await html("앞 글 ![아이콘](i.png) 뒤 글");
    expect(out).not.toContain("<figure");
    expect(out).toContain("/api/asset?path=");
  });

  it("폭 표기는 width로 옮기고 캡션에서 뺀다", async () => {
    const out = await html("![흐름도|480](f.png)");
    expect(out).toContain('width="480"');
    expect(out).toContain("<figcaption>흐름도</figcaption>");
  });

  it("영상 확장자는 video로", async () => {
    const out = await html("![시연](demo.mp4)");
    expect(out).toContain("<video");
    expect(out).toContain("controls");
  });
});

describe("숫자 열", () => {
  it("숫자 칸이 대부분인 열에만 num을 단다", async () => {
    const md = [
      "| 상품 | 거래액 | 비중 | 메모 |",
      "|---|---|---|---|",
      "| 다낭 | 70.61억 | 12.5% | 좋음 |",
      "| 오사카 | 1,234건 | 3%p | - |",
      "| 방콕 | -3 | 0.5% | 보통 |",
    ].join("\n");
    const out = await html(md);
    expect(out).toContain('<th class="num">거래액</th>');
    expect(out).toContain('<td class="num">70.61억</td>');
    expect(out).toContain('<td class="num">12.5%</td>');
    expect(out).not.toContain('<td class="num">다낭</td>');
    expect(out).not.toContain('<td class="num">좋음</td>');
  });

  it("작성자가 정렬을 정한 열은 그대로", async () => {
    const md = ["| a | b |", "|:--|:-:|", "| 1 | 2 |", "| 3 | 4 |"].join("\n");
    const out = await html(md);
    expect(out).not.toContain("num");
  });

  it("숫자 판별", () => {
    for (const t of ["1,234", "12.5%", "70.61억", "₩1,000", "+3.5%p", "2.4x", "(3)"]) expect(isNumericCell(t)).toBe(true);
    for (const t of ["다낭", "1분기 목표", "v2.1 출시", ""]) expect(isNumericCell(t)).toBe(false);
  });
});
