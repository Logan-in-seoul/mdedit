import { useEffect, useRef } from "react";

declare global {
  interface Window {
    pywebview?: unknown;
  }
}

/** pywebview 셸 내부에서 실행 중인지 감지한다. */
function isDesktop(): boolean {
  if (typeof window === "undefined") return false;
  if (window.pywebview != null) return true;
  // pywebview JS bridge 주입 전에도 동작하도록 데스크톱 진입점이 붙이는 쿼리 파람 확인
  return new URLSearchParams(window.location.search).get("desktop") === "1";
}

/**
 * 데스크톱 앱(Finder .md 더블클릭) 열기 요청 폴링 훅.
 *
 * pywebview 안에서만 동작한다: 로드 직후 + 2초 간격으로
 * /api/open/pending을 폴링해 경로가 오면 onOpen으로 연다.
 * 브라우저 접속 시에는 아무것도 하지 않는다.
 */
export function useDesktopOpen(onOpen: (path: string) => void): void {
  const onOpenRef = useRef(onOpen);
  onOpenRef.current = onOpen;

  useEffect(() => {
    if (!isDesktop()) return;
    let stopped = false;

    const poll = async () => {
      try {
        const res = await fetch("/api/open/pending");
        if (!res.ok) return;
        const data = (await res.json()) as { path: string | null };
        if (!stopped && data.path) onOpenRef.current(data.path);
      } catch {
        // 서버 재시작 등 일시적 실패는 무시하고 다음 주기에 재시도
      }
    };

    void poll();
    const id = window.setInterval(poll, 2000);
    return () => {
      stopped = true;
      window.clearInterval(id);
    };
  }, []);
}
