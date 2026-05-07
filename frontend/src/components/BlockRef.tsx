/**
 * BlockRef — [[파일명^block-id]] 블록 참조 렌더링.
 */
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { WIKI_OPEN_EVENT } from "./WikiLink";

interface BlockRefProps {
  title: string;
  blockId: string;
  display?: string;
  path?: string;
}

export function BlockRef({ title, blockId, display, path }: BlockRefProps) {
  const [content, setContent] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!path || !blockId) { setError(true); return; }
    api.block(path, blockId)
      .then((res) => setContent(res.content))
      .catch(() => setError(true));
  }, [path, blockId]);

  const label = display || `${title}^${blockId}`;

  const handleClick = () => {
    if (!path) return;
    window.dispatchEvent(new CustomEvent(WIKI_OPEN_EVENT, { detail: { title, path } }));
  };

  return (
    <span
      style={{
        borderLeft: `2px dashed ${error ? "#f87171" : "var(--color-border, #444)"}`,
        padding: "4px 10px",
        margin: "4px 0",
        fontSize: "0.9em",
        color: error ? "#f87171" : "inherit",
        cursor: path ? "pointer" : "default",
        display: "inline-block",
      }}
      className={`block-ref ${error ? "block-ref-error" : ""}`}
      onClick={handleClick}
      title={content ?? (error ? `블록 없음: ^${blockId}` : "로딩 중…")}
    >
      {label}
    </span>
  );
}
