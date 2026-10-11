import { useCallback, useEffect, useRef, useState, type CSSProperties } from "react";
import { ActivityFeed } from "./components/ActivityFeed";
import { FileTree } from "./components/FileTree";
import { FlatList } from "./components/FlatList";
import { QuickSwitcher } from "./components/QuickSwitcher";
import { Reader } from "./components/Reader";
import { ReaderControls } from "./components/ReaderControls";
import { ReadingToolbar } from "./components/ReadingToolbar";
import { api, FileEntry } from "./lib/api";
import { getScroll, pushRecent, saveScroll, setLastDoc } from "./lib/nav";
import { useDesktopOpen } from "./lib/useDesktopOpen";
import { useMeasure } from "./lib/useMeasure";
import { useReadingMode } from "./lib/useReadingMode";

type ViewMode = "flat" | "tree";

const SIDEBAR_KEY = "mdedit:sidebar:collapsed";

/** 주소의 `#/<문서 경로>`. 새로고침해도 보던 문서가 유지되고 주소를 복사해 둘 수 있다. */
function docFromHash(): string | null {
  const h = window.location.hash;
  if (!h.startsWith("#/")) return null;
  try {
    return decodeURIComponent(h.slice(2)) || null;
  } catch {
    return null;
  }
}

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(SIDEBAR_KEY) === "1";
  } catch {
    return false;
  }
}

const SHORTCUTS: [string, string][] = [
  ["Ctrl K", "빠른 열기"],
  ["/", "검색창으로"],
  ["Ctrl [  Ctrl ]", "이전·다음 문서"],
  ["Ctrl \\", "사이드바 접기"],
  ["Ctrl Shift O", "목차 접기"],
  ["Ctrl .", "읽기 모드"],
  ["+  −  0", "읽기 모드 글자 크기"],
  ["j  k", "읽기 모드 발언 이동"],
];

interface UpdateInfo {
  current: string;
  latest: string | null;
  update_available: boolean;
  url: string;
}

export default function App() {
  const [selected, setSelected] = useState<string | null>(null);
  const [scrollToLine, setScrollToLine] = useState<number | null>(null);
  const [mode, setMode] = useState<ViewMode>("flat");
  const [update, setUpdate] = useState<UpdateInfo | null>(null);
  const [switcherOpen, setSwitcherOpen] = useState(false);
  const [files, setFiles] = useState<FileEntry[] | null>(null);
  const [collapsed, setCollapsed] = useState<boolean>(readCollapsed);
  const mainRef = useRef<HTMLElement>(null);
  const progressRef = useRef<HTMLDivElement>(null);
  // 뒤로/앞으로 히스토리 스택 (⌘[ ⌘])
  const historyRef = useRef<string[]>([]);
  const historyIdxRef = useRef(-1);
  const navigatingRef = useRef(false);
  const scrollSaveRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const selectedRef = useRef<string | null>(null);
  const scrollToLineRef = useRef<number | null>(null);
  selectedRef.current = selected;
  scrollToLineRef.current = scrollToLine;

  // 스위처·피드용 파일 목록 (FlatList와 별도 — 결합 최소화)
  useEffect(() => {
    api.filesFlat(1000).then(setFiles).catch(() => {});
  }, []);

  // 업데이트 체크 — 실패(오프라인)는 조용히 무시
  useEffect(() => {
    api.updateCheck().then(setUpdate).catch(() => {});
  }, []);

  // 문서 전환 시 우측 패널을 맨 위로. 저장 위치/라인 점프 복원은 렌더 후 수행.
  useEffect(() => {
    mainRef.current?.scrollTo(0, 0);
  }, [selected]);

  // 파일 선택: 히스토리 push + 최근/세션 기록
  const handleSelect = useCallback((path: string, line?: number) => {
    setScrollToLine(line ?? null);
    setSelected((prev) => {
      if (path !== prev) {
        if (!navigatingRef.current) {
          const h = historyRef.current.slice(0, historyIdxRef.current + 1);
          h.push(path);
          historyRef.current = h;
          historyIdxRef.current = h.length - 1;
        }
        pushRecent(path);
        setLastDoc(path);
        return path;
      }
      return prev;
    });
  }, []);

  const navigateHistory = useCallback((delta: -1 | 1) => {
    const idx = historyIdxRef.current + delta;
    if (idx < 0 || idx >= historyRef.current.length) return;
    historyIdxRef.current = idx;
    navigatingRef.current = true;
    setScrollToLine(null);
    setSelected(historyRef.current[idx]);
    navigatingRef.current = false;
  }, []);

  const toggleSidebar = useCallback(() => {
    setCollapsed((v) => {
      try {
        localStorage.setItem(SIDEBAR_KEY, v ? "0" : "1");
      } catch {
        // 저장 불가 환경에서는 세션 내 상태만 유지
      }
      return !v;
    });
  }, []);

  // 주소에 문서가 있으면 그 문서로 시작하고, 주소를 직접 고쳐도 따라간다
  useEffect(() => {
    const open = () => {
      const doc = docFromHash();
      if (doc) handleSelect(doc);
    };
    open();
    window.addEventListener("hashchange", open);
    return () => window.removeEventListener("hashchange", open);
  }, [handleSelect]);

  // 보고 있는 문서를 주소에 남긴다. replaceState라 브라우저 뒤로 가기 기록은 늘리지 않는다.
  useEffect(() => {
    const { pathname, search } = window.location;
    const hash = selected ? `#/${encodeURIComponent(selected)}` : "";
    if (window.location.hash !== hash) {
      window.history.replaceState(null, "", pathname + search + hash);
    }
  }, [selected]);

  // 전역 단축키: ⌘K 스위처, ⌘[ 뒤로, ⌘] 앞으로, ⌘\ 사이드바
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // "/" 는 검색창으로 간다. 접혀 있으면 먼저 편다 (포커스는 FlatList가 잡는다).
      if (e.key === "/" && !e.metaKey && !e.ctrlKey && !e.altKey) {
        const el = e.target as HTMLElement | null;
        const tag = el?.tagName?.toLowerCase();
        if (tag !== "input" && tag !== "textarea" && !el?.isContentEditable) {
          setCollapsed(false);
        }
        return;
      }
      if (!(e.metaKey || e.ctrlKey)) return;
      if (e.key === "k") {
        e.preventDefault();
        setSwitcherOpen((v) => !v);
      } else if (e.key === "[") {
        e.preventDefault();
        navigateHistory(-1);
      } else if (e.key === "]") {
        e.preventDefault();
        navigateHistory(1);
      } else if (e.key === "\\") {
        e.preventDefault();
        toggleSidebar();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [navigateHistory, toggleSidebar]);

  // 읽던 위치 복원: Reader 렌더 완료 시점에, 라인 점프가 없을 때만
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<{ path: string }>).detail;
      if (detail?.path !== selectedRef.current) return;
      if (scrollToLineRef.current != null) return; // 검색 점프 우선
      const top = getScroll(detail.path);
      if (top > 0) mainRef.current?.scrollTo({ top });
    };
    window.addEventListener("mdedit:rendered", handler);
    return () => window.removeEventListener("mdedit:rendered", handler);
  }, []);

  // 읽은 만큼 상단 진행 막대를 채운다
  const updateProgress = useCallback(() => {
    const main = mainRef.current;
    const bar = progressRef.current;
    if (!main || !bar) return;
    const room = main.scrollHeight - main.clientHeight;
    const ratio = room > 0 ? Math.min(1, main.scrollTop / room) : 0;
    bar.style.transform = `scaleX(${ratio})`;
  }, []);

  useEffect(() => {
    updateProgress();
    window.addEventListener("mdedit:rendered", updateProgress);
    return () => window.removeEventListener("mdedit:rendered", updateProgress);
  }, [selected, updateProgress]);

  // 스크롤 위치 저장 (debounce 300ms)
  const handleScroll = () => {
    updateProgress();
    if (!selectedRef.current) return;
    if (scrollSaveRef.current) clearTimeout(scrollSaveRef.current);
    scrollSaveRef.current = setTimeout(() => {
      if (selectedRef.current && mainRef.current) {
        saveScroll(selectedRef.current, mainRef.current.scrollTop);
      }
    }, 300);
  };

  // 데스크톱(pywebview) 셸: Finder .md 더블클릭 열기 요청 폴링
  useDesktopOpen(handleSelect);

  // 읽기(발표) 모드 — 문서가 열려 있을 때만, 스위처가 떠 있으면 키를 양보한다
  const readingMode = useReadingMode(mainRef, selected != null, switcherOpen);
  const measure = useMeasure();

  return (
    <div
      className={`app${readingMode.reading ? " reading" : ""}${collapsed ? " no-sidebar" : ""}`}
      style={{ "--reader-scale": readingMode.scale, "--measure": measure.css } as CSSProperties}
    >
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1
            className="brand brand-home"
            onClick={() => setSelected(null)}
            title="홈 (최근 활동)"
          >
            mdedit
          </h1>
          <button
            className="sidebar-collapse"
            onClick={toggleSidebar}
            title="사이드바 접기 (Ctrl/Cmd + \)"
            aria-label="사이드바 접기"
          >
            «
          </button>
          <div className="view-toggle">
            <button
              className={mode === "flat" ? "active" : ""}
              onClick={() => setMode("flat")}
            >
              All
            </button>
            <button
              className={mode === "tree" ? "active" : ""}
              onClick={() => setMode("tree")}
            >
              Tree
            </button>
          </div>
        </div>
        {mode === "flat" ? (
          <FlatList onSelect={handleSelect} selected={selected} />
        ) : (
          <FileTree onSelect={(p) => handleSelect(p)} selected={selected} />
        )}
        <div className="sidebar-footer">
          <details className="shortcuts">
            <summary>단축키</summary>
            <dl>
              {SHORTCUTS.map(([keys, what]) => (
                <div key={keys}>
                  <dt>{keys}</dt>
                  <dd>{what}</dd>
                </div>
              ))}
            </dl>
          </details>
          {update && (
            <div className="sidebar-version">
              <span className="app-version">v{update.current}</span>
              {update.update_available && update.latest && (
                <a
                  className="update-badge"
                  href={update.url}
                  target="_blank"
                  rel="noreferrer"
                  title="새 버전이 있습니다"
                >
                  {update.latest.replace(/^v/, "v")} 업데이트 ↗
                </a>
              )}
            </div>
          )}
        </div>
      </aside>
      {collapsed && !readingMode.reading && (
        <button
          className="sidebar-expand"
          onClick={toggleSidebar}
          title="사이드바 펴기 (Ctrl/Cmd + \)"
          aria-label="사이드바 펴기"
        >
          »
        </button>
      )}
      <main className="main" ref={mainRef} onScroll={handleScroll}>
        {selected && (
          <div className="read-progress-anchor">
            <div className="read-progress" ref={progressRef} />
          </div>
        )}
        {selected && <ReaderControls mode={readingMode} measure={measure} />}
        <div className="main-inner">
          {selected ? (
            <Reader path={selected} scrollToLine={scrollToLine} onOpen={handleSelect} />
          ) : (
            <ActivityFeed files={files} onSelect={handleSelect} />
          )}
        </div>
      </main>
      <ReadingToolbar mode={readingMode} measure={measure} />
      <QuickSwitcher
        open={switcherOpen}
        files={files}
        onClose={() => setSwitcherOpen(false)}
        onSelect={handleSelect}
      />
    </div>
  );
}
