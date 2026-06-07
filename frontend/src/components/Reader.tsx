import { useEffect, useRef, useState } from "react";
import { api, FileContent } from "../lib/api";
import { renderMarkdown } from "../lib/markdown";

interface Props {
  path: string;
  scrollToLine?: number | null;
}

export function Reader({ path, scrollToLine }: Props) {
  const [content, setContent] = useState<FileContent | null>(null);
  const [rendered, setRendered] = useState<React.ReactElement | null>(null);
  const [error, setError] = useState<string | null>(null);
  const bodyRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    setContent(null);
    setRendered(null);
    setError(null);
    api
      .file(path)
      .then(async (c) => {
        if (cancelled) return;
        setContent(c);
        const node = await renderMarkdown(c.body);
        if (!cancelled) setRendered(node);
      })
      .catch((e) => {
        if (!cancelled) setError(String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [path]);

  // 렌더 완료 알림 — App이 읽던 위치 복원 타이밍으로 사용 (v0.8)
  useEffect(() => {
    if (!rendered) return;
    window.dispatchEvent(
      new CustomEvent("mdedit:rendered", { detail: { path } }),
    );
  }, [rendered, path]);

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
      {content.frontmatter && (
        <section className="frontmatter">
          <h3>frontmatter</h3>
          <pre>{JSON.stringify(content.frontmatter, null, 2)}</pre>
        </section>
      )}
      <div className="body" ref={bodyRef}>{rendered}</div>
    </article>
  );
}
