import { useEffect, useMemo, useRef, useState } from "react";
import { api, FileEntry, SearchHit } from "../lib/api";
import { getRecent } from "../lib/nav";

// ⌘K Quick Switcher (v0.8) — 파일명 퍼지 매치 + FTS 본문 매치 점프 모달.
// 빈 입력이면 최근 연 파일을 보여준다.

interface Props {
  open: boolean;
  files: FileEntry[] | null;
  onClose: () => void;
  onSelect: (path: string, line?: number) => void;
}

interface Item {
  kind: "file" | "hit";
  path: string;
  label: string;
  detail: string;
  line?: number;
  snippet?: { text: string; start: number; end: number };
}

/** 단순 퍼지 매치: 쿼리 문자가 순서대로 등장하면 매치. 연속 매치에 가점. */
function fuzzyScore(query: string, target: string): number {
  const q = query.toLowerCase();
  const t = target.toLowerCase();
  let qi = 0;
  let score = 0;
  let streak = 0;
  for (let ti = 0; ti < t.length && qi < q.length; ti++) {
    if (t[ti] === q[qi]) {
      qi += 1;
      streak += 1;
      score += 1 + streak; // 연속 매치 가점
    } else {
      streak = 0;
    }
  }
  if (qi < q.length) return -1; // 미매치
  return score - t.length * 0.01; // 짧은 대상 우대
}

function dirOf(path: string): string {
  return path.replace(/^[^:]+:\/\//, "").replace(/\/[^/]*$/, "");
}

export function QuickSwitcher({ open, files, onClose, onSelect }: Props) {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // 열릴 때 초기화 + 포커스
  useEffect(() => {
    if (open) {
      setQuery("");
      setHits([]);
      setActive(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  // FTS 본문 매치 (디바운스)
  useEffect(() => {
    if (!open) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const q = query.trim();
    if (q.length < 2) {
      setHits([]);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      try {
        const res = await api.search(q, undefined, 8);
        setHits(res.hits);
      } catch {
        setHits([]);
      }
    }, 250);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, open]);

  const items = useMemo<Item[]>(() => {
    if (!files) return [];
    const q = query.trim();
    const byPath = new Map(files.map((f) => [f.path, f]));

    if (!q) {
      // 최근 연 파일
      return getRecent()
        .map((p) => byPath.get(p))
        .filter((f): f is FileEntry => f != null)
        .slice(0, 12)
        .map((f) => ({
          kind: "file" as const,
          path: f.path,
          label: f.title || f.name,
          detail: dirOf(f.path),
        }));
    }

    // 파일명·제목 퍼지 매치
    const fileItems = files
      .map((f) => ({
        f,
        score: Math.max(
          fuzzyScore(q, f.name),
          f.title ? fuzzyScore(q, f.title) : -1,
        ),
      }))
      .filter((x) => x.score >= 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 8)
      .map((x) => ({
        kind: "file" as const,
        path: x.f.path,
        label: x.f.title || x.f.name,
        detail: dirOf(x.f.path),
      }));

    // 본문 매치 (파일 매치와 중복 경로 제외)
    const seen = new Set(fileItems.map((i) => i.path));
    const hitItems = hits
      .filter((h) => !seen.has(h.path))
      .slice(0, 8)
      .map((h) => ({
        kind: "hit" as const,
        path: h.path,
        label: h.name,
        detail: `L${h.line}`,
        line: h.line,
        snippet: { text: h.snippet, start: h.match_start, end: h.match_end },
      }));

    return [...fileItems, ...hitItems];
  }, [files, query, hits]);

  useEffect(() => setActive(0), [items.length, query]);

  // 활성 항목이 보이도록 스크롤
  useEffect(() => {
    listRef.current
      ?.querySelector(`[data-idx="${active}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [active]);

  if (!open) return null;

  const choose = (item: Item) => {
    onSelect(item.path, item.line);
    onClose();
  };

  return (
    <div className="qs-backdrop" onMouseDown={onClose}>
      <div className="qs-modal" onMouseDown={(e) => e.stopPropagation()}>
        <input
          ref={inputRef}
          className="qs-input"
          placeholder="파일명·본문으로 이동…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") onClose();
            else if (e.key === "ArrowDown") {
              e.preventDefault();
              setActive((a) => Math.min(a + 1, items.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setActive((a) => Math.max(a - 1, 0));
            } else if (e.key === "Enter" && items[active]) {
              e.preventDefault();
              choose(items[active]);
            }
          }}
        />
        <div className="qs-list" ref={listRef}>
          {items.length === 0 && (
            <div className="qs-empty">
              {query.trim() ? "결과 없음" : "최근 연 파일이 없습니다"}
            </div>
          )}
          {items.map((item, i) => (
            <div
              key={`${item.kind}:${item.path}:${item.line ?? ""}`}
              data-idx={i}
              className={`qs-item ${i === active ? "active" : ""}`}
              onMouseEnter={() => setActive(i)}
              onClick={() => choose(item)}
            >
              <div className="qs-item-main">
                <span className="qs-label">{item.label}</span>
                <span className="qs-detail">{item.detail}</span>
              </div>
              {item.snippet && (
                <div className="qs-snippet">
                  {item.snippet.text.slice(0, item.snippet.start)}
                  <mark>
                    {item.snippet.text.slice(item.snippet.start, item.snippet.end)}
                  </mark>
                  {item.snippet.text.slice(item.snippet.end)}
                </div>
              )}
            </div>
          ))}
        </div>
        <div className="qs-hint">↑↓ 이동 · Enter 열기 · Esc 닫기</div>
      </div>
    </div>
  );
}
