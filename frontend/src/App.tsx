import { useState } from "react";
import { FileTree } from "./components/FileTree";
import { FlatList } from "./components/FlatList";
import { Reader } from "./components/Reader";

type ViewMode = "flat" | "tree";

export default function App() {
  const [selected, setSelected] = useState<string | null>(null);
  const [scrollToLine, setScrollToLine] = useState<number | null>(null);
  const [mode, setMode] = useState<ViewMode>("flat");

  // 파일 선택 시: path만 변경하면 scrollToLine을 초기화한다
  const handleSelect = (path: string, line?: number) => {
    if (path !== selected) {
      setSelected(path);
      setScrollToLine(line ?? null);
    } else if (line != null) {
      // 같은 파일에서 다른 라인 클릭 시 즉시 스크롤
      setScrollToLine(line);
    }
  };

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1 className="brand">mdedit</h1>
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
      </aside>
      <main className="main">
        {selected ? (
          <Reader path={selected} scrollToLine={scrollToLine} />
        ) : (
          <div className="placeholder">파일을 선택하세요</div>
        )}
      </main>
    </div>
  );
}
