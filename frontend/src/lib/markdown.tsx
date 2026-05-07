import { Fragment, jsx, jsxs } from "react/jsx-runtime";
import { useState, useEffect } from "react";
import { unified } from "unified";
import remarkParse from "remark-parse";
import remarkGfm from "remark-gfm";
import remarkFrontmatter from "remark-frontmatter";
import remarkMath from "remark-math";
import remarkRehype from "remark-rehype";
import rehypeRaw from "rehype-raw";
import rehypeKatex from "rehype-katex";
import rehypeShikiFromHighlighter from "@shikijs/rehype/core";
import { createHighlighterCore } from "shiki/core";
import { type HighlighterGeneric } from "@shikijs/types";
import { createJavaScriptRegexEngine } from "shiki/engine/javascript";
import getWasm from "shiki/wasm";
import rehypeReact from "rehype-react";
import { MermaidBlock } from "../components/MermaidBlock";
import { rehypeTagChips, TagChip } from "../components/TagChip";
import { rehypeWikiLinks, WikiLink, resolvePath } from "../components/WikiLink";
import { EmbedBlock } from "../components/EmbedBlock";
import { BlockRef } from "../components/BlockRef";
import type { Plugin } from "unified";
import type { Root, Element } from "hast";

/**
 * rehype 플러그인: remark-parse가 파싱한 position 정보를 기반으로
 * 블록 레벨 요소에 `data-line="N"` 속성을 부여한다.
 * 검색 결과 라인 점프(D-4)에 사용된다.
 */
const rehypeLineNumbers: Plugin<[], Root> = () => {
  return (tree: Root) => {
    // hast 노드를 순회하며 position이 있는 element에 data-line 추가
    const visit = (node: Root | Element) => {
      if (node.type === "element") {
        const el = node as Element;
        if (el.position?.start?.line != null) {
          el.properties = el.properties ?? {};
          // 이미 하위에서 설정된 경우 덮어쓰지 않는다
          if (!("dataLine" in el.properties)) {
            el.properties["dataLine"] = String(el.position.start.line);
          }
        }
        if (el.children) {
          for (const child of el.children) {
            if (child.type === "element") {
              visit(child as Element);
            }
          }
        }
      } else if (node.type === "root") {
        for (const child of node.children) {
          if (child.type === "element") {
            visit(child as Element);
          }
        }
      }
    };
    visit(tree);
  };
};

const highlighter = (await createHighlighterCore({
  themes: [import("shiki/themes/github-light.mjs")],
  langs: [
    import("shiki/langs/typescript.mjs"),
    import("shiki/langs/javascript.mjs"),
    import("shiki/langs/python.mjs"),
    import("shiki/langs/bash.mjs"),
    import("shiki/langs/yaml.mjs"),
    import("shiki/langs/json.mjs"),
    import("shiki/langs/markdown.mjs"),
    import("shiki/langs/sql.mjs"),
  ],
  loadWasm: getWasm,
  engine: createJavaScriptRegexEngine(),
})) as unknown as HighlighterGeneric<any, any>;

const processor = unified()
  .use(remarkParse)
  .use(remarkFrontmatter, ["yaml"])
  .use(remarkGfm)
  .use(remarkMath)
  .use(remarkRehype, { allowDangerousHtml: true })
  .use(rehypeRaw)
  .use(rehypeLineNumbers)
  .use(rehypeShikiFromHighlighter, highlighter, { theme: "github-light" })
  .use(rehypeKatex)
  .use(rehypeTagChips)
  .use(rehypeWikiLinks)
  .use(rehypeReact, {
    Fragment,
    jsx,
    jsxs,
    components: {
      "tag-chip": TagChip as any,
      "wiki-link": WikiLink as any,
      "embed-link": ({ title, display: _display }: { title?: string; display?: string }) => {
        const [resolvedPath, setResolvedPath] = useState<string | null | undefined>(undefined);
        useEffect(() => {
          if (!title) return;
          resolvePath(title).then(setResolvedPath);
        }, [title]);
        return <EmbedBlock title={title || ""} path={resolvedPath ?? undefined} isNested={false} />;
      },
      "block-ref": ({ title, blockId, display }: { title?: string; blockId?: string; display?: string }) => {
        const [resolvedPath, setResolvedPath] = useState<string | null | undefined>(undefined);
        useEffect(() => {
          if (!title) return;
          resolvePath(title).then(setResolvedPath);
        }, [title]);
        return <BlockRef title={title || ""} blockId={blockId || ""} display={display} path={resolvedPath ?? undefined} />;
      },
      pre: (props: any) => {
        const child = Array.isArray(props.children)
          ? props.children[0]
          : props.children;
        const lang = child?.props?.className?.match(/language-(\w+)/)?.[1];
        if (lang === "mermaid") {
          const code =
            typeof child.props.children === "string"
              ? child.props.children
              : Array.isArray(child.props.children)
                ? child.props.children.join("")
                : "";
          return <MermaidBlock code={code.trim()} />;
        }
        return <pre {...props} />;
      },
    },
  });

export async function renderMarkdown(source: string) {
  const file = await processor.process(source);
  return file.result as React.ReactElement;
}
