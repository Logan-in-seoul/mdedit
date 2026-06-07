import { useCallback, useEffect, useRef, useState } from "react";
import { ActivityFeed } from "./components/ActivityFeed";
import { FileTree } from "./components/FileTree";
import { FlatList } from "./components/FlatList";
import { QuickSwitcher } from "./components/QuickSwitcher";
import { Reader } from "./components/Reader";
import { api, FileEntry } from "./lib/api";
import { getScroll, pushRecent, saveScroll, setLastDoc } from "./lib/nav";
import { useDesktopOpen } from "./lib/useDesktopOpen";

type ViewMode = "flat" | "tree";

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
  const mainRef = useRef<HTMLElement>(null);
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

  // 전역 단축키: ⌘K 스위처, ⌘[ 뒤로, ⌘] 앞으로
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
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
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [navigateHistory]);

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

  // 스크롤 위치 저장 (debounce 300ms)
  const handleScroll = () => {
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

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1
            className="brand brand-home"
            onClick={() => setSelected(null)}
            title="홈 (최근 활동)"
          >
            mdedit
          </h1>
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
        {update && (
          <div className="sidebar-footer">
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
      </aside>
      <main className="main" ref={mainRef} onScroll={handleScroll}>
        <div className="main-inner">
          {selected ? (
            <Reader path={selected} scrollToLine={scrollToLine} />
          ) : (
            <ActivityFeed files={files} onSelect={handleSelect} />
          )}
        </div>
      </main>
      <QuickSwitcher
        open={switcherOpen}
        files={files}
        onClose={() => setSwitcherOpen(false)}
        onSelect={handleSelect}
      />
    </div>
  );
}
