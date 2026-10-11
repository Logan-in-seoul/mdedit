import { useCallback, useEffect, useRef, useState } from "react";
import { extractFromDom, OutlineItem } from "../lib/outline";

// OutlineSidebar mounts as a fixed-position panel docked to the right edge.
// It observes the rendered reader body (.body) via MutationObserver to keep
// the heading tree in sync with whatever note App is currently rendering.
// This avoids any coupling to App.tsx state — purely DOM-driven.

const OUTLINE_VISIBLE_KEY = "mdedit:outline:visible";
/** 스크롤 영역 위에서 이만큼 아래를 지난 마지막 헤딩을 현재 섹션으로 본다. */
const SPY_OFFSET = 96;
/** 목차 클릭 뒤 부드러운 스크롤이 지나가는 동안은 현재 섹션을 다시 계산하지 않는다. */
const CLICK_LOCK_MS = 800;

function sameItems(a: OutlineItem[], b: OutlineItem[]): boolean {
  return (
    a.length === b.length &&
    a.every((x, i) => x.id === b[i].id && x.text === b[i].text && x.level === b[i].level)
  );
}

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
  const lockUntilRef = useRef(0);

  const refresh = useCallback(() => {
    const body = document.querySelector<HTMLElement>(".body");
    bodyRef.current = body;
    setHasDoc(body != null);
    // 800ms 폴링과 body 전체 관찰이 같은 목록을 계속 돌려주므로, 바뀐 때만 다시 그린다
    const next = body ? extractFromDom(body) : [];
    setItems((prev) => (sameItems(prev, next) ? prev : next));
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

  // 스크롤 위치에 맞춰 현재 섹션을 표시한다. scroll은 버블되지 않아 capture로 받는다.
  useEffect(() => {
    let raf = 0;
    const update = () => {
      raf = 0;
      if (Date.now() < lockUntilRef.current) return;
      const body = bodyRef.current;
      const main = body?.closest<HTMLElement>(".main");
      if (!body || !main) return;
      const line = main.getBoundingClientRect().top + SPY_OFFSET;
      const headings = Array.from(body.querySelectorAll<HTMLElement>("[data-outline-id]"));
      let current: string | null = null;
      for (const h of headings) {
        if (h.getClientRects().length === 0) continue; // 접힌 섹션 안
        if (h.getBoundingClientRect().top > line) break;
        current = h.getAttribute("data-outline-id");
      }
      // 첫 헤딩에 닿기 전에는 첫 항목을 현재로 둔다
      const next = current ?? items[0]?.id ?? null;
      setActiveId((prev) => (prev === next ? prev : next));
    };
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(update);
    };
    window.addEventListener("scroll", onScroll, true);
    window.addEventListener("resize", onScroll);
    update();
    return () => {
      window.removeEventListener("scroll", onScroll, true);
      window.removeEventListener("resize", onScroll);
      if (raf) cancelAnimationFrame(raf);
    };
  }, [items]);

  // 현재 섹션이 목차 안에서 화면 밖으로 밀리지 않게 따라간다
  useEffect(() => {
    if (!activeId || !visible) return;
    document
      .querySelector(".outline-sidebar .outline-active")
      ?.scrollIntoView({ block: "nearest" });
  }, [activeId, visible]);

  const handleClick = useCallback((item: OutlineItem) => {
    const body = bodyRef.current ?? document.querySelector<HTMLElement>(".body");
    if (!body) return;
    const target = body.querySelector<HTMLElement>(
      `[data-outline-id="${CSS.escape(item.id)}"]`,
    );
    if (!target) return;
    lockUntilRef.current = Date.now() + CLICK_LOCK_MS;
    target.scrollIntoView({ behavior: "smooth", block: "start" });
    setActiveId(item.id);
    // Brief highlight pulse so the user notices the jump target.
    target.classList.add("outline-flash");
    window.setTimeout(() => target.classList.remove("outline-flash"), 1200);
  }, []);

  // 문서가 없으면(홈/피드) 패널·토글 모두 숨김
  if (!hasDoc) return null;

  // 문서가 H2부터 시작해도 왼쪽에 붙도록 가장 얕은 레벨을 1로 맞춘다
  const baseLevel = items.reduce((min, i) => Math.min(min, i.level), 6);

  if (!visible) {
    return (
      <button
        type="button"
        className="outline-toggle outline-toggle-collapsed"
        title="목차 열기 (Ctrl+Shift+O)"
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
        <span className="outline-title">목차</span>
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
                className={`outline-item outline-l${item.level - baseLevel + 1} ${
                  item.id === activeId ? "outline-active" : ""
                }`}
              >
                <button
                  type="button"
                  className="outline-link"
                  onClick={() => handleClick(item)}
                  title={item.text}
                >
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
