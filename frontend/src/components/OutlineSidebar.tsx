import { useCallback, useEffect, useRef, useState } from "react";
import { extractFromDom, OutlineItem } from "../lib/outline";

// OutlineSidebar mounts as a fixed-position panel docked to the right edge.
// It observes the rendered reader body (.body) via MutationObserver to keep
// the heading tree in sync with whatever note App is currently rendering.
// This avoids any coupling to App.tsx state — purely DOM-driven.

const OUTLINE_VISIBLE_KEY = "mdedit:outline:visible";

function readInitialVisible(): boolean {
  // 기본 표시 (v0.8) — 명시적으로 닫은 적 있을 때만 숨김
  try {
    return localStorage.getItem(OUTLINE_VISIBLE_KEY) !== "0";
  } catch {
    return true;
  }
}

function persistVisible(v: boolean): void {
  try {
    localStorage.setItem(OUTLINE_VISIBLE_KEY, v ? "1" : "0");
  } catch {
    // ignore quota errors
  }
}

export function OutlineSidebar() {
  const [visible, setVisible] = useState<boolean>(() => readInitialVisible());
  const [items, setItems] = useState<OutlineItem[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  // 문서가 열려 있는지 (.reader 존재) — 홈/피드 화면에서는 패널 자체를 숨긴다 (v0.8)
  const [hasDoc, setHasDoc] = useState(false);
  const observerRef = useRef<MutationObserver | null>(null);
  const bodyRef = useRef<HTMLElement | null>(null);

  const refresh = useCallback(() => {
    const body = document.querySelector<HTMLElement>(".body");
    bodyRef.current = body;
    setHasDoc(body != null);
    if (!body) {
      setItems([]);
      return;
    }
    setItems(extractFromDom(body));
  }, []);

  // Toggle visibility with Ctrl+Shift+O (Cmd+Shift+O on macOS).
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const mod = e.metaKey || e.ctrlKey;
      if (!mod || !e.shiftKey) return;
      if (e.key === "o" || e.key === "O") {
        e.preventDefault();
        setVisible((v) => {
          const next = !v;
          persistVisible(next);
          return next;
        });
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Observe the document for body element changes and content mutations.
  // visible 여부와 무관하게 관찰 — hasDoc(문서 존재) 추적에도 쓰인다.
  useEffect(() => {
    refresh();

    const root = document.body;
    const obs = new MutationObserver(() => {
      // If the .body element itself was swapped (note change), or its inner
      // headings changed (re-render), recompute. Cheap operation: querySelectorAll.
      refresh();
    });
    obs.observe(root, {
      subtree: true,
      childList: true,
      characterData: true,
    });
    observerRef.current = obs;

    // Poll every 800ms as a defensive fallback for cases where MutationObserver
    // misses async render commits (rare with React, but cheap insurance).
    const interval = window.setInterval(refresh, 800);

    return () => {
      obs.disconnect();
      observerRef.current = null;
      window.clearInterval(interval);
    };
  }, [refresh]);

  const handleClick = useCallback((item: OutlineItem) => {
    const body = bodyRef.current ?? document.querySelector<HTMLElement>(".body");
    if (!body) return;
    const target = body.querySelector<HTMLElement>(
      `[data-outline-id="${CSS.escape(item.id)}"]`,
    );
    if (!target) return;
    target.scrollIntoView({ behavior: "smooth", block: "start" });
    setActiveId(item.id);
    // Brief highlight pulse so the user notices the jump target.
    target.classList.add("outline-flash");
    window.setTimeout(() => target.classList.remove("outline-flash"), 1200);
  }, []);

  // 문서가 없으면(홈/피드) 패널·토글 모두 숨김
  if (!hasDoc) return null;

  if (!visible) {
    return (
      <button
        type="button"
        className="outline-toggle outline-toggle-collapsed"
        title="Outline 열기 (Ctrl+Shift+O)"
        onClick={() => {
          setVisible(true);
          persistVisible(true);
        }}
      >
        ⫶
      </button>
    );
  }

  return (
    <aside className="outline-sidebar" aria-label="문서 개요">
      <header className="outline-header">
        <span className="outline-title">Outline</span>
        <span className="outline-count">{items.length}</span>
        <button
          type="button"
          className="outline-close"
          title="닫기 (Ctrl+Shift+O)"
          onClick={() => {
            setVisible(false);
            persistVisible(false);
          }}
        >
          ×
        </button>
      </header>
      <div className="outline-body">
        {items.length === 0 ? (
          <div className="outline-empty">헤딩이 없습니다</div>
        ) : (
          <ul className="outline-list">
            {items.map((item) => (
              <li
                key={`${item.index}-${item.id}`}
                className={`outline-item outline-l${item.level} ${
                  item.id === activeId ? "outline-active" : ""
                }`}
              >
                <button
                  type="button"
                  className="outline-link"
                  onClick={() => handleClick(item)}
                  title={item.text}
                >
                  <span className="outline-marker">H{item.level}</span>
                  <span className="outline-text">{item.text}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}
