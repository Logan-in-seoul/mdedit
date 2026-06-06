import { useEffect, useMemo, useRef, useState } from "react";
import { api, FileEntry, SearchHit } from "../lib/api";
import { TAG_SEARCH_EVENT, TagSearchDetail } from "./TagChip";
import { WIKI_OPEN_EVENT, WikiOpenDetail } from "./WikiLink";

interface Props {
  onSelect: (virtualPath: string, line?: number) => void;
  selected: string | null;
}

type Mode = "flat" | "search" | "wiki-suggest";

function formatRelative(mtime: number): string {
  const now = Date.now() / 1000;
  const diff = now - mtime;
  if (diff < 60) return "방금";
  if (diff < 3600) return `${Math.floor(diff / 60)}분 전`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}일 전`;
  const d = new Date(mtime * 1000);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function SnippetText({
  snippet,
  start,
  end,
}: {
  snippet: string;
  start: number;
  end: number;
}) {
  const before = snippet.slice(0, start);
  const match = snippet.slice(start, end);
  const after = snippet.slice(end);
  return (
    <span className="search-snippet">
      {before}
      <mark>{match}</mark>
      {after}
    </span>
  );
}

export function FlatList({ onSelect, selected }: Props) {
  const [files, setFiles] = useState<FileEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [searchHits, setSearchHits] = useState<SearchHit[] | null>(null);
  const [mode, setMode] = useState<Mode>("flat");
  const [searching, setSearching] = useState(false);
  // wiki-suggest: [[ 입력 후 파일명 필터
  const [wikiQuery, setWikiQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    api
      .filesFlat(1000)
      .then(setFiles)
      .catch((e) => setError(String(e)));
  }, []);

  // tag: 검색 이벤트 수신 (TagChip 클릭)
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<TagSearchDetail>).detail;
      const q = `tag:${detail.tag}`;
      setFilter(q);
      if (inputRef.current) {
        inputRef.current.focus();
      }
    };
    window.addEventListener(TAG_SEARCH_EVENT, handler);
    return () => window.removeEventListener(TAG_SEARCH_EVENT, handler);
  }, []);

  // wiki-link 클릭: 경로가 resolve된 경우 바로 열고, 없으면 검색창에 파일명 입력
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<WikiOpenDetail>).detail;
      if (detail.path) {
        // 이미 resolve된 경우 바로 선택
        onSelect(detail.path);
      } else {
        // 못 찾은 경우: 검색창에 타이틀 입력해 사용자가 직접 선택
        setFilter(detail.title);
        if (inputRef.current) inputRef.current.focus();
      }
    };
    window.addEventListener(WIKI_OPEN_EVENT, handler);
    return () => window.removeEventListener(WIKI_OPEN_EVENT, handler);
  }, [onSelect]);

  // backlinks panel 클릭 → 해당 파일 선택
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<{ path: string }>).detail;
      if (detail?.path) onSelect(detail.path);
    };
    window.addEventListener("mdedit:backlink-clicked", handler);
    return () => window.removeEventListener("mdedit:backlink-clicked", handler);
  }, [onSelect]);

  // [[ 입력 감지: wiki-suggest 모드 전환
  useEffect(() => {
    const q = filter;
    const wikiIdx = q.lastIndexOf("[[");
    if (wikiIdx !== -1) {
      const after = q.slice(wikiIdx + 2);
      // ]] 가 없으면 wiki-suggest 모드
      if (!after.includes("]]")) {
        setMode("wiki-suggest");
        setWikiQuery(after.toLowerCase());
        return;
      }
    }
    // wiki-suggest 모드가 아닌 경우 기존 로직으로 넘어감
    if (mode === "wiki-suggest") {
      setMode("flat");
      setWikiQuery("");
    }
  }, [filter]); // eslint-disable-line react-hooks/exhaustive-deps

  // 검색 쿼리 변경 시 처리
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const q = filter.trim();

    // [[ 모드는 별도 처리
    if (q.includes("[[") && !q.includes("]]")) return;

    if (q.length < 2) {
      setMode("flat");
      setSearchHits(null);
      return;
    }

    setMode("search");
    setSearching(true);

    debounceRef.current = setTimeout(async () => {
      try {
        // 연산자를 파싱해 API 파라미터로 분리한다
        // tag:, path:, type: 각각 첫 번째만 추출하고 나머지는 텍스트로 넘긴다
        let tagParam: string | undefined;
        let pathParam: string | undefined;
        let typeParam: string | undefined;
        const restTokens: string[] = [];

        for (const tok of q.split(/\s+/).filter(Boolean)) {
          const low = tok.toLowerCase();
          if (low.startsWith("tag:") && tok.length > 4 && !tagParam) {
            tagParam = tok.slice(4);
          } else if (low.startsWith("path:") && tok.length > 5 && !pathParam) {
            pathParam = tok.slice(5);
          } else if (low.startsWith("type:") && tok.length > 5 && !typeParam) {
            typeParam = tok.slice(5);
          } else {
            restTokens.push(tok);
          }
        }

        const textParam = restTokens.join(" ");
        const res = await api.search(textParam, tagParam, 200, pathParam, typeParam);
        // 파일명·경로에 검색어가 들어간 hit를 위로 끌어올린다. 줄 단위 bm25가
        // 짧은 주변 언급(예: "Airwallex" 한 줄)을 본문 문서보다 위에 두는 문제 보정.
        // 그룹 내 원래(bm25) 순서는 안정 정렬로 유지한다.
        const needle = textParam.trim().toLowerCase();
        // 제목 > 파일명 > 경로 순으로 끌어올린다. 줄 단위 bm25가 짧은 주변 언급
        // (예: "Airwallex" 한 줄)을 본문 문서보다 위에 두는 문제 보정.
        // 그룹 내 원래(bm25) 순서는 안정 정렬로 유지한다.
        const titleByPath = new Map(
          (files ?? []).map((f) => [f.path, (f.title || "").toLowerCase()])
        );
        const ranked = needle
          ? res.hits
              .map((h, i) => {
                const title = titleByPath.get(h.path) || "";
                const name = (h.name || "").toLowerCase();
                const path = (h.path || "").toLowerCase();
                const tier = title.includes(needle)
                  ? 0
                  : name.includes(needle)
                  ? 1
                  : path.includes(needle)
                  ? 2
                  : 3;
                return { h, i, tier };
              })
              .sort((a, b) => a.tier - b.tier || a.i - b.i)
              .map((x) => x.h)
          : res.hits;
        setSearchHits(ranked);
      } catch {
        setSearchHits([]);
      } finally {
        setSearching(false);
      }
    }, 250);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [filter]);

  const filteredFiles = useMemo(() => {
    if (!files) return [];
    const q = filter.trim().toLowerCase();
    if (!q || q.length < 2) return files;
    // 파일명 필터 (flat 모드에서만 사용)
    return files.filter(
      (f) =>
        f.name.toLowerCase().includes(q) || f.path.toLowerCase().includes(q),
    );
  }, [files, filter]);

  // wiki-suggest 모드: [[ 이후 입력으로 파일 필터링
  const wikiSuggestFiles = useMemo(() => {
    if (!files || mode !== "wiki-suggest") return [];
    if (!wikiQuery) return files.slice(0, 20);
    return files
      .filter(
        (f) =>
          f.name.toLowerCase().includes(wikiQuery) ||
          f.path.toLowerCase().includes(wikiQuery),
      )
      .slice(0, 20);
  }, [files, wikiQuery, mode]);

  if (error) return <div className="placeholder">로드 실패: {error}</div>;
  if (!files) return <div className="placeholder">로딩 중…</div>;

  const placeholder =
    files.length > 0
      ? `${files.length}개 파일 — 검색: tag: path: type: 연산자 지원`
      : "파일 없음";

  return (
    <div className="flatlist">
      <input
        ref={inputRef}
        type="text"
        className="flatlist-filter"
        placeholder={placeholder}
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        onKeyDown={(e) => {
          if (e.ctrlKey && e.key === "Enter") {
            e.preventDefault();
            // Ctrl+Enter: copy [[filename]] of selected or first visible file
            let targetPath: string | undefined;
            if (selected) {
              targetPath = selected;
            } else if (mode === "flat" && filteredFiles.length > 0) {
              targetPath = filteredFiles[0].path;
            } else if (mode === "search" && searchHits && searchHits.length > 0) {
              targetPath = searchHits[0].path;
            }
            if (targetPath) {
              const entry = files?.find((f) => f.path === targetPath);
              const name = entry?.name ?? targetPath.split("/").pop() ?? targetPath;
              const stem = name.endsWith(".md") ? name.slice(0, -3) : name;
              navigator.clipboard.writeText(`[[${stem}]]`).catch(() => {});
            }
          }
        }}
      />
      {searching && <div className="flatlist-status">검색 중…</div>}
      {mode === "wiki-suggest" ? (
        <div className="flatlist-items wiki-suggest-list">
          <div className="flatlist-status wiki-suggest-hint">
            [[링크 삽입 — 파일 선택
          </div>
          {wikiSuggestFiles.length === 0 && (
            <div className="placeholder">파일 없음</div>
          )}
          {wikiSuggestFiles.map((f) => (
            <div
              key={f.path}
              className="flatlist-row"
              onClick={() => {
                // [[ 이후 텍스트를 선택한 파일명 stem으로 교체
                const wikiIdx = filter.lastIndexOf("[[");
                const stem = f.name.endsWith(".md") ? f.name.slice(0, -3) : f.name;
                setFilter(filter.slice(0, wikiIdx) + `[[${stem}]]`);
                setMode("flat");
                setWikiQuery("");
                onSelect(f.path);
              }}
              title={f.path}
            >
              <div className="flatlist-name">{f.name}</div>
              <div className="flatlist-meta">
                <span className="flatlist-path">
                  {f.path.replace(/^[^:]+:\/\//, "").replace(/\/[^/]*$/, "")}
                </span>
              </div>
            </div>
          ))}
        </div>
      ) : mode === "search" && searchHits !== null ? (
        <div className="flatlist-items">
          {searchHits.length === 0 && !searching && (
            <div className="placeholder">결과 없음</div>
          )}
          {searchHits.map((hit, i) => (
            <div
              key={`${hit.path}:${hit.line}:${i}`}
              className={`flatlist-row ${hit.path === selected ? "selected" : ""}`}
              onClick={() => onSelect(hit.path, hit.line)}
              title={hit.path}
            >
              <div className="flatlist-name">{hit.name}</div>
              <SnippetText
                snippet={hit.snippet}
                start={hit.match_start}
                end={hit.match_end}
              />
              <div className="flatlist-meta">
                <span className="flatlist-path">
                  {hit.path.replace(/^[^:]+:\/\//, "").replace(/\/[^/]*$/, "")}
                </span>
                <span className="flatlist-time">L{hit.line}</span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="flatlist-items">
          {filteredFiles.map((f) => (
            <div
              key={f.path}
              className={`flatlist-row ${f.path === selected ? "selected" : ""}`}
              onClick={() => onSelect(f.path)}
              title={f.path}
            >
              <div className="flatlist-name">{f.title || f.name}</div>
              <div className="flatlist-meta">
                <span className="flatlist-time">{formatRelative(f.mtime)}</span>
                <span className="flatlist-path">
                  {f.path.replace(/^[^:]+:\/\//, "").replace(/\/[^/]*$/, "")}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
