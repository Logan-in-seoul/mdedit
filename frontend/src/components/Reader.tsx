import { useEffect, useRef, useState } from "react";
import { api, FileContent } from "../lib/api";
import { renderMarkdown } from "../lib/markdown";
import { setupFolding } from "../lib/fold";
import { hasScheme, isMarkdownHref, resolveRelative } from "../lib/links";
import { slugify } from "../lib/outline";
import { Lightbox, type ZoomTarget } from "./Lightbox";

/** 블록 하나를 비교할 열쇠. 글자와 그림 주소(문서 판 표시는 뗀다)를 합친다. */
function blockKey(el: Element): string {
  const srcs = Array.from(el.querySelectorAll("img"))
    .map((i) => (i.getAttribute("src") || "").replace(/&v=\d+$/, ""))
    .join("|");
  return `${el.tagName}:${(el.textContent || "").replace(/\s+/g, " ").trim()}:${srcs}`;
}

/** 열려 있는 문서가 디스크에서 바뀌었는지 확인하는 간격. */
const REFRESH_MS = 5000;

function clock(d: Date): string {
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

interface Props {
  path: string;
  scrollToLine?: number | null;
  /** 본문 안의 다른 문서 링크를 눌렀을 때 */
  onOpen?: (path: string) => void;
}

export function Reader({ path, scrollToLine, onOpen }: Props) {
  const [content, setContent] = useState<FileContent | null>(null);
  const [rendered, setRendered] = useState<React.ReactElement | null>(null);
  const [error, setError] = useState<string | null>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const mtimeRef = useRef<number | null>(null);
  // 열어 둔 사이에 파일이 바뀌어 다시 그린 시각. 처음 연 것과 구분해 스크롤을 건드리지 않는다.
  const [refreshedAt, setRefreshedAt] = useState<Date | null>(null);
  const refreshedRef = useRef(false);
  // 자동 갱신 직전 블록 열쇠. 다시 그린 뒤 새로 생기거나 바뀐 블록에 표시를 단다.
  const prevKeysRef = useRef<Set<string> | null>(null);
  const [changed, setChanged] = useState<HTMLElement[]>([]);
  const changeCursor = useRef(0);
  const [zoom, setZoom] = useState<ZoomTarget | null>(null);

  useEffect(() => {
    let cancelled = false;
    setContent(null);
    setRendered(null);
    setError(null);
    setRefreshedAt(null);
    refreshedRef.current = false;
    mtimeRef.current = null;
    prevKeysRef.current = null;
    setChanged([]);
    setZoom(null);
    api
      .file(path)
      .then(async (c) => {
        if (cancelled) return;
        mtimeRef.current = c.mtime;
        setContent(c);
        const node = await renderMarkdown(c.body, { docPath: path, assetVersion: c.mtime });
        if (!cancelled) setRendered(node);
      })
      .catch((e) => {
        if (!cancelled) setError(String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [path]);

  // 열어 둔 문서가 디스크에서 바뀌면 제자리에서 다시 그린다. 에이전트가 계속 고쳐 쓰는
  // 문서를 읽는 일이 많아서, 새로고침 없이는 옛 판을 읽게 된다. 탭이 보일 때만 확인한다.
  useEffect(() => {
    let cancelled = false;
    let busy = false;
    const check = async () => {
      if (busy || document.hidden || mtimeRef.current == null) return;
      busy = true;
      try {
        const { mtime } = await api.mtime(path);
        if (cancelled || mtime === mtimeRef.current) return;
        const c = await api.peek(path);
        if (cancelled) return;
        const node = await renderMarkdown(c.body, { docPath: path, assetVersion: c.mtime });
        if (cancelled) return;
        mtimeRef.current = c.mtime;
        refreshedRef.current = true;
        const body = bodyRef.current;
        prevKeysRef.current = body ? new Set(Array.from(body.children).map(blockKey)) : null;
        setContent(c);
        setRendered(node);
        setRefreshedAt(new Date());
      } catch {
        // 잠깐 못 읽은 것(쓰는 중·서버 재시작)은 다음 주기에 다시 본다
      } finally {
        busy = false;
      }
    };
    const timer = window.setInterval(check, REFRESH_MS);
    document.addEventListener("visibilitychange", check);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", check);
    };
  }, [path]);

  // 자동 갱신으로 다시 그렸으면 바뀐 블록을 표시한다. 에이전트가 고쳐 쓰는 문서를 읽을 때
  // 어디가 바뀌었는지 다시 훑지 않아도 되게 한다.
  useEffect(() => {
    const prev = prevKeysRef.current;
    const body = bodyRef.current;
    if (!prev || !rendered || !body) return;
    prevKeysRef.current = null;
    const raf = requestAnimationFrame(() => {
      body.querySelectorAll(".changed-block").forEach((el) => el.classList.remove("changed-block"));
      const fresh = Array.from(body.children).filter(
        (el): el is HTMLElement => el instanceof HTMLElement && !prev.has(blockKey(el)) && blockKey(el).length > 4,
      );
      fresh.forEach((el) => el.classList.add("changed-block"));
      changeCursor.current = 0;
      setChanged(fresh);
    });
    return () => cancelAnimationFrame(raf);
  }, [rendered]);

  const jumpToChange = () => {
    if (changed.length === 0) return;
    const el = changed[changeCursor.current % changed.length];
    changeCursor.current += 1;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const clearChanges = () => {
    changed.forEach((el) => el.classList.remove("changed-block"));
    setChanged([]);
  };

  // 브라우저 탭 제목을 문서 제목으로
  useEffect(() => {
    if (!content) return;
    const name = content.title || path.split("/").pop() || path;
    document.title = `${name} · mdedit`;
    return () => {
      document.title = "mdedit";
    };
  }, [content, path]);

  // 렌더 완료 알림 — App이 읽던 위치 복원 타이밍으로 사용 (v0.8)
  // 자동 갱신으로 다시 그린 경우는 읽던 자리를 그대로 둔다.
  useEffect(() => {
    if (!rendered || refreshedRef.current) return;
    window.dispatchEvent(
      new CustomEvent("mdedit:rendered", { detail: { path } }),
    );
  }, [rendered, path]);

  // 본문 링크: 바깥 주소는 새 탭, 다른 md 문서는 mdedit 안에서, #는 문서 안 이동.
  // 그대로 두면 상대 링크가 앱 밖 주소로 나가 홈 화면으로 떨어진다.
  const onBodyClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.defaultPrevented || e.button !== 0) return;
    const el = e.target as HTMLElement;
    const a = el.closest<HTMLAnchorElement>("a[href]");
    if (!a) {
      // 그림과 도식은 눌러서 크게 본다
      const img = el.closest<HTMLImageElement>("img.md-img");
      if (img) {
        const fig = img.closest("figure");
        setZoom({
          kind: "img",
          src: img.currentSrc || img.src,
          caption: fig?.querySelector("figcaption")?.textContent || img.alt || undefined,
          plate: true,
        });
        return;
      }
      const diagram = el.closest<HTMLElement>(".mermaid.zoomable");
      const svg = diagram?.querySelector("svg");
      if (diagram && svg) {
        setZoom({ kind: "svg", html: svg.outerHTML, plate: diagram.classList.contains("mermaid-authored") });
      }
      return;
    }
    const href = a.getAttribute("href") || "";
    if (href.startsWith("#")) {
      e.preventDefault();
      const id = decodeURIComponent(href.slice(1));
      const body = bodyRef.current;
      if (!body || !id) return;
      const target =
        body.querySelector<HTMLElement>(`[id="${CSS.escape(id)}"]`) ??
        Array.from(body.querySelectorAll<HTMLElement>("h1, h2, h3, h4, h5, h6")).find(
          (h) => slugify((h.textContent || "").replace(/[▾▸]/g, "")) === slugify(id),
        );
      target?.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    if (hasScheme(href)) {
      if (/^https?:/i.test(href)) {
        e.preventDefault();
        window.open(href, "_blank", "noopener,noreferrer");
      }
      return;
    }
    e.preventDefault();
    const file = decodeURI(href.split("#")[0]);
    if (!isMarkdownHref(file)) return;
    const next = resolveRelative(path, file);
    if (next) onOpen?.(next);
  };

  // 렌더링 완료 후 대상 라인으로 스크롤한다
  useEffect(() => {
    if (!scrollToLine || !rendered || !bodyRef.current) return;
    // data-line 정확 일치 → 인접 라인 순으로 후보 탐색
    const container = bodyRef.current;
    const findTarget = () => {
      for (let offset = 0; offset <= 5; offset++) {
        const el =
          container.querySelector(`[data-line="${scrollToLine + offset}"]`) ??
          (offset > 0
            ? container.querySelector(`[data-line="${scrollToLine - offset}"]`)
            : null);
        if (el) return el;
      }
      return null;
    };
    // 렌더링 직후 DOM 반영 전에 requestAnimationFrame으로 대기
    const raf = requestAnimationFrame(() => {
      const target = findTarget();
      if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "center" });
        target.classList.add("line-highlight");
        setTimeout(() => target.classList.remove("line-highlight"), 2000);
      }
    });
    return () => cancelAnimationFrame(raf);
  }, [rendered, scrollToLine]);

  // 헤딩 접기 토글 (노트별 상태 저장)
  useEffect(() => {
    if (!rendered || !bodyRef.current) return;
    return setupFolding(bodyRef.current, path);
  }, [rendered, path]);

  if (error) return <div className="placeholder">로드 실패: {error}</div>;
  if (!content) return <div className="placeholder">로딩 중…</div>;

  return (
    <article className="reader">
      {path.startsWith("ext://") && (
        <div className="external-note" title={path.slice(6)}>
          vault 밖 문서 — 검색·백링크에는 포함되지 않습니다
          <span className="external-path">{path.slice(6)}</span>
        </div>
      )}
      {content.reading && content.reading.minutes > 0 && (
        <div className="reading-time" title={`${content.reading.characters.toLocaleString()}자 · ${content.reading.words.toLocaleString()}단어`}>
          약 {content.reading.minutes}분 · {content.reading.characters.toLocaleString()}자
          {content.reading.words > 0 && ` · ${content.reading.words.toLocaleString()}단어`}
          {refreshedAt && <span className="reading-refreshed"> · {clock(refreshedAt)} 변경분 반영</span>}
          {changed.length > 0 && (
            <span className="change-nav">
              <button type="button" className="change-jump" onClick={jumpToChange} title="바뀐 곳으로 차례로 이동">
                바뀐 곳 {changed.length}
              </button>
              <button type="button" className="change-clear" onClick={clearChanges} title="표시 지우기" aria-label="바뀐 곳 표시 지우기">
                ×
              </button>
            </span>
          )}
        </div>
      )}
      {content.frontmatter && (
        <details className="frontmatter">
          <summary>frontmatter · {Object.keys(content.frontmatter).length}개 항목</summary>
          <pre>{JSON.stringify(content.frontmatter, null, 2)}</pre>
        </details>
      )}
      <div className="body" ref={bodyRef} onClick={onBodyClick}>{rendered}</div>
      {zoom && <Lightbox target={zoom} onClose={() => setZoom(null)} />}
    </article>
  );
}
