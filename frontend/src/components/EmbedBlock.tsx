/**
 * EmbedBlock — ![[파일명]] 인라인 임베드 렌더링.
 */
import { useEffect, useState } from "react";
import { Fragment, jsx, jsxs } from "react/jsx-runtime";
import { api } from "../lib/api";
import { WIKI_OPEN_EVENT } from "./WikiLink";
import { unified } from "unified";
import remarkParse from "remark-parse";
import remarkGfm from "remark-gfm";
import remarkRehype from "remark-rehype";
import rehypeReact from "rehype-react";

interface EmbedBlockProps {
  title: string;
  path?: string;
  isNested?: boolean;
}

function EmbedMarkdownContent({ body }: { body: string }) {
  const [rendered, setRendered] = useState<React.ReactElement | null>(null);

  useEffect(() => {
    unified()
      .use(remarkParse)
      .use(remarkGfm)
      .use(remarkRehype, { allowDangerousHtml: false })
      .use(rehypeReact, {
        Fragment,
        jsx,
        jsxs,
      })
      .process(body)
      .then((vfile) => setRendered(vfile.result as React.ReactElement))
      .catch(() => setRendered(<span style={{ fontSize: "12px", color: "#888" }}>렌더링 실패</span>));
  }, [body]);

  return rendered ?? <span style={{ fontSize: "12px", color: "#888" }}>렌더링 중…</span>;
}

export function EmbedBlock({ title, path, isNested = false }: EmbedBlockProps) {
  const [data, setData] = useState<{ title: string | null; body: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!path) {
      setError(`파일 없음: ${title}`);
      setLoading(false);
      return;
    }
    let cancelled = false;
    api.embed(path)
      .then((res) => { if (!cancelled) setData(res); })
      .catch((e) => { if (!cancelled) setError(String(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [path, title]);

  const handleClick = () => {
    if (!path) return;
    window.dispatchEvent(new CustomEvent(WIKI_OPEN_EVENT, { detail: { title, path } }));
  };

  const containerStyle: React.CSSProperties = {
    borderLeft: `2px solid ${error ? "#f87171" : "var(--color-primary, #1D8BFF)"}`,
    background: "var(--color-surface-raised, rgba(255,255,255,0.03))",
    padding: "8px 12px",
    margin: "8px 0",
    borderRadius: "0 4px 4px 0",
    cursor: path ? "pointer" : "default",
  };

  if (loading) return <div style={containerStyle}><span style={{ fontSize: "12px", color: "#888" }}>로딩 중: [[{title}]]</span></div>;
  if (error || !data) return <div style={containerStyle}><span style={{ fontSize: "12px", color: "#f87171" }}>파일 없음: [[{title}]]</span></div>;
  if (isNested) return <div style={containerStyle} onClick={handleClick}><span style={{ fontSize: "12px", color: "#888" }}>[[{title}]]</span></div>;

  return (
    <div style={containerStyle} className="embed-block" onClick={handleClick}>
      <EmbedMarkdownContent body={data.body} />
    </div>
  );
}
