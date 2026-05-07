import { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import { api, FileEntry } from "../lib/api";

// Self-mounting backlinks panel.
// Listens to `mdedit:note-opened` events emitted by lib/api.ts when a note loads,
// then queries /api/backlinks and renders the result in a fixed right-side panel.
// Avoids App.tsx and UnifiedSearch.tsx entanglement by mounting into a fresh root
// appended to document.body on import.

function BacklinksPanel() {
  const [path, setPath] = useState<string | null>(null);
  const [items, setItems] = useState<FileEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    function handler(ev: Event) {
      const detail = (ev as CustomEvent<{ path: string }>).detail;
      if (detail && detail.path) setPath(detail.path);
    }
    window.addEventListener("mdedit:note-opened", handler);
    return () => window.removeEventListener("mdedit:note-opened", handler);
  }, []);

  useEffect(() => {
    if (!path) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .backlinks(path)
      .then((res) => {
        if (!cancelled) setItems(res);
      })
      .catch((e) => {
        if (!cancelled) setError(String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [path]);

  if (collapsed) {
    return (
      <button
        className="bl-toggle bl-toggle-collapsed"
        onClick={() => setCollapsed(false)}
        aria-label="백링크 패널 펼치기"
      >
        ←
      </button>
    );
  }

  return (
    <aside className="bl-panel">
      <header className="bl-header">
        <span className="bl-title">백링크</span>
        <button
          className="bl-toggle"
          onClick={() => setCollapsed(true)}
          aria-label="백링크 패널 접기"
        >
          →
        </button>
      </header>
      {!path && <div className="bl-empty">노트를 선택하세요</div>}
      {path && loading && <div className="bl-empty">검색 중…</div>}
      {path && error && <div className="bl-empty">오류: {error}</div>}
      {path && !loading && !error && items.length === 0 && (
        <div className="bl-empty">참조하는 노트가 없습니다</div>
      )}
      {path && !loading && items.length > 0 && (
        <ul className="bl-list">
          {items.map((it) => (
            <li key={it.path}>
              <a
                href="#"
                onClick={(e) => {
                  e.preventDefault();
                  // dispatch the same event so other listeners (or future App
                  // integration) can react. The panel itself just refreshes.
                  window.dispatchEvent(
                    new CustomEvent("mdedit:backlink-clicked", {
                      detail: { path: it.path },
                    }),
                  );
                }}
                title={it.path}
              >
                {it.title || it.name}
              </a>
              <span className="bl-meta">
                {new Date(it.mtime * 1000).toLocaleDateString()}
              </span>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}

// inject CSS once
function injectStyles() {
  if (document.getElementById("bl-panel-styles")) return;
  const css = `
    .bl-panel {
      position: fixed; top: 0; right: 0; bottom: 0; width: 240px;
      background: #fff; border-left: 1px solid #e5e5e5; padding: 12px;
      overflow-y: auto; font-size: 13px; z-index: 50;
      box-shadow: -2px 0 8px rgba(0,0,0,0.03);
    }
    .bl-header {
      display: flex; align-items: center; justify-content: space-between;
      margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid #eee;
    }
    .bl-title {
      font-size: 11px; font-weight: 600; letter-spacing: 0.05em;
      text-transform: uppercase; color: #666;
    }
    .bl-toggle {
      background: transparent; border: 1px solid #ddd; border-radius: 4px;
      width: 24px; height: 24px; cursor: pointer; color: #666;
    }
    .bl-toggle:hover { background: #f5f5f5; }
    .bl-toggle-collapsed {
      position: fixed; top: 12px; right: 12px; z-index: 50;
      width: 28px; height: 28px;
    }
    .bl-empty { color: #999; font-size: 12px; padding: 8px 0; }
    .bl-list { list-style: none; padding: 0; margin: 0; }
    .bl-list li {
      padding: 6px 0; border-bottom: 1px solid #f5f5f5;
      display: flex; flex-direction: column; gap: 2px;
    }
    .bl-list a {
      color: #1D8BFF; text-decoration: none; font-weight: 500;
      word-break: break-all;
    }
    .bl-list a:hover { text-decoration: underline; }
    .bl-meta { color: #aaa; font-size: 11px; }
  `;
  const style = document.createElement("style");
  style.id = "bl-panel-styles";
  style.textContent = css;
  document.head.appendChild(style);
}

function mount() {
  if (document.getElementById("backlinks-root")) return;
  injectStyles();
  const div = document.createElement("div");
  div.id = "backlinks-root";
  document.body.appendChild(div);
  ReactDOM.createRoot(div).render(<BacklinksPanel />);
}

if (typeof window !== "undefined") {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount, { once: true });
  } else {
    mount();
  }
}

export {};
