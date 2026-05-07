/**
 * GraphPanel — react-force-graph-2d 기반 위키링크 관계 그래프 패널.
 * Ctrl+G 로 토글. mdedit:note-opened 이벤트로 현재 파일 추적.
 */
import { useEffect, useState, useCallback, useRef, lazy, Suspense } from "react";
import ReactDOM from "react-dom/client";
import { api, GraphNode, GraphEdge } from "../lib/api";

const ForceGraph2D = lazy(() => import("react-force-graph-2d"));
import { WIKI_OPEN_EVENT } from "./WikiLink";

const CURRENT_COLOR = "#1D8BFF";
const OUTLINK_COLOR = "#F97316";
const INLINK_COLOR = "#22C55E";
const DEFAULT_COLOR = "#94A3B8";

function GraphPanel() {
  const [currentPath, setCurrentPath] = useState<string | null>(null);
  const [graphData, setGraphData] = useState<{ nodes: GraphNode[]; links: GraphEdge[] }>({
    nodes: [],
    links: [],
  });
  const [depth, setDepth] = useState<1 | 2>(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [visible, setVisible] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handler(ev: Event) {
      const detail = (ev as CustomEvent<{ path: string }>).detail;
      if (detail?.path) setCurrentPath(detail.path);
    }
    window.addEventListener("mdedit:note-opened", handler);
    return () => window.removeEventListener("mdedit:note-opened", handler);
  }, []);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.ctrlKey && e.key === "g") {
        e.preventDefault();
        setVisible((v) => !v);
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, []);

  useEffect(() => {
    if (!currentPath || !visible) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .graph(currentPath, depth)
      .then((res) => {
        if (cancelled) return;
        setGraphData({ nodes: res.nodes, links: res.edges });
      })
      .catch((e) => {
        if (!cancelled) setError(String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [currentPath, depth, visible]);

  const nodeColor = useCallback(
    (node: GraphNode) => {
      if (node.id === currentPath) return CURRENT_COLOR;
      const isInlink = graphData.links.some(
        (e) => e.target === currentPath && e.source === node.id,
      );
      if (isInlink) return INLINK_COLOR;
      const isOutlink = graphData.links.some(
        (e) => e.source === currentPath && e.target === node.id,
      );
      if (isOutlink) return OUTLINK_COLOR;
      return DEFAULT_COLOR;
    },
    [graphData.links, currentPath],
  );

  const handleNodeClick = useCallback((node: GraphNode) => {
    window.dispatchEvent(
      new CustomEvent(WIKI_OPEN_EVENT, {
        detail: { title: node.label, path: node.id },
      }),
    );
  }, []);

  const handleNodeRightClick = useCallback((node: GraphNode) => {
    const linkText = `[[${node.label}]]`;
    navigator.clipboard.writeText(linkText).catch(() => {});
  }, []);

  if (!visible) return null;

  const width = containerRef.current?.offsetWidth ?? 320;

  return (
    <div
      ref={containerRef}
      className="graph-panel"
      style={{
        position: "fixed",
        bottom: "16px",
        right: "16px",
        width: "340px",
        background: "var(--color-surface, #1e1e2e)",
        border: "1px solid var(--color-border, #333)",
        borderRadius: "8px",
        zIndex: 200,
        overflow: "hidden",
        boxShadow: "0 4px 24px rgba(0,0,0,0.4)",
      }}
    >
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "8px 12px", borderBottom: "1px solid var(--color-border, #333)",
        fontSize: "12px", color: "var(--color-text-muted, #888)",
      }}>
        <span>그래프 뷰</span>
        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          <button
            onClick={() => setDepth(depth === 1 ? 2 : 1)}
            style={{ fontSize: "11px", padding: "2px 6px", borderRadius: "4px",
              border: "1px solid var(--color-border, #444)", background: "transparent",
              color: "inherit", cursor: "pointer" }}
          >
            {depth}hop
          </button>
          <button onClick={() => setVisible(false)} aria-label="닫기"
            style={{ fontSize: "14px", background: "transparent", border: "none",
              color: "inherit", cursor: "pointer" }}>×</button>
        </div>
      </div>
      {loading && <div style={{ padding: "24px", textAlign: "center", fontSize: "12px", color: "#888" }}>로딩 중…</div>}
      {error && <div style={{ padding: "12px", fontSize: "12px", color: "#f87171" }}>{error}</div>}
      {!loading && !error && (
        <Suspense fallback={<div style={{ padding: "24px", textAlign: "center", fontSize: "12px", color: "#888" }}>그래프 로딩…</div>}>
          <ForceGraph2D
            graphData={graphData}
            width={width || 320}
            height={300}
            nodeLabel="label"
            nodeColor={nodeColor as (node: object) => string}
            onNodeClick={handleNodeClick as (node: object) => void}
            onNodeRightClick={handleNodeRightClick as (node: object) => void}
            linkColor={() => "#555"}
            nodeRelSize={5}
            cooldownTicks={60}
          />
        </Suspense>
      )}
    </div>
  );
}

const _container = document.createElement("div");
_container.id = "mdedit-graph-panel";
document.body.appendChild(_container);
ReactDOM.createRoot(_container).render(<GraphPanel />);

export {};
