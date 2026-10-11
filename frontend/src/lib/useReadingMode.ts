// 읽기(발표) 모드 — 사이드바·패널을 숨기고 본문만 크게 띄운다.
// 스타일은 global.css의 `.app.reading` / `body.reading-active` / `.reading-toolbar`가 이미 갖고 있고,
// 이 훅은 그 클래스를 켜고 끄는 상태·단축키·비트 점프만 담당한다.
// 표기 규약 SoT: docs/notation-contract.md

import { RefObject, useCallback, useEffect, useRef, useState } from "react";

const READING_KEY = "mdedit:reading";
const SCALE_KEY = "mdedit:reader-scale";

export const SCALE_MIN = 0.8;
export const SCALE_MAX = 1.8;
const SCALE_STEP = 0.1;

/** 발언 단위 점프 대상. /scr 라벨 칩과 분기 블록. */
const BEAT_SELECTOR = ".scr-label, .scr-branch";
/** 라벨은 span이므로 감싸는 블록으로 올려서 잡는다. */
const BLOCK_SELECTOR = "p, li, h1, h2, h3, h4, blockquote";
/** 점프 후 상단에 남길 여백. */
const BEAT_OFFSET = 24;

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw == null ? fallback : (JSON.parse(raw) as T);
  } catch {
    return fallback;
  }
}

function write(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // quota 등 — 무시
  }
}

function clampScale(v: number): number {
  return Math.min(SCALE_MAX, Math.max(SCALE_MIN, Math.round(v * 10) / 10));
}

/** 입력 중이면 단축키를 삼키지 않는다. */
function isTyping(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el || !el.tagName) return false;
  const tag = el.tagName.toLowerCase();
  return tag === "input" || tag === "textarea" || tag === "select" || el.isContentEditable;
}

export interface ReadingMode {
  reading: boolean;
  scale: number;
  toggle: () => void;
  exit: () => void;
  setScale: (v: number) => void;
  bumpScale: (delta: number) => void;
  resetScale: () => void;
  jumpBeat: (dir: -1 | 1) => void;
}

/**
 * 읽기 모드 상태와 단축키.
 *
 * - `Cmd/Ctrl + .` 토글 (문서가 열려 있을 때만)
 * - 읽기 중 `Esc` 종료, `+` `-` 글자 크기, `0` 초기화
 * - 읽기 중 `j` `k` 발언 단위 점프 (라벨 칩·분기 블록 기준)
 *
 * @param container 스크롤 컨테이너(main). 비트 점프의 기준이다.
 * @param enabled 문서가 열려 있는지. 홈 화면에서는 켜지지 않는다.
 * @param blocked 다른 오버레이(스위처 등)가 키를 쓰고 있는지.
 */
export function useReadingMode(
  container: RefObject<HTMLElement | null>,
  enabled: boolean,
  blocked = false,
): ReadingMode {
  const [reading, setReading] = useState<boolean>(() => read(READING_KEY, false));
  const [scale, setScaleState] = useState<number>(() => clampScale(read(SCALE_KEY, 1)));

  const readingRef = useRef(reading);
  readingRef.current = reading;
  const enabledRef = useRef(enabled);
  enabledRef.current = enabled;
  const blockedRef = useRef(blocked);
  blockedRef.current = blocked;

  // 문서를 닫으면 읽기 모드도 내린다. 홈 화면에 툴바만 떠 있으면 이상하다.
  const active = reading && enabled;

  useEffect(() => {
    document.body.classList.toggle("reading-active", active);
    return () => document.body.classList.remove("reading-active");
  }, [active]);

  const setScale = useCallback((v: number) => {
    const next = clampScale(v);
    setScaleState(next);
    write(SCALE_KEY, next);
  }, []);

  // 단축키 핸들러는 한 번만 등록되므로 setState 함수형 갱신으로 최신 값을 읽는다.
  const bumpScale = useCallback((delta: number) => {
    setScaleState((prev) => {
      const next = clampScale(prev + delta);
      write(SCALE_KEY, next);
      return next;
    });
  }, []);

  const resetScale = useCallback(() => setScale(1), [setScale]);

  const toggle = useCallback(() => {
    setReading((v) => {
      const next = !v;
      write(READING_KEY, next);
      return next;
    });
  }, []);

  const exit = useCallback(() => {
    setReading(false);
    write(READING_KEY, false);
  }, []);

  /** 라벨·분기 블록 사이를 오간다. 없으면 헤딩으로 대신한다. */
  const jumpBeat = useCallback(
    (dir: -1 | 1) => {
      const root = container.current;
      if (!root) return;
      const body = root.querySelector(".reader .body");
      if (!body) return;

      let marks = Array.from(body.querySelectorAll(BEAT_SELECTOR));
      if (marks.length === 0) marks = Array.from(body.querySelectorAll("h2, h3"));
      if (marks.length === 0) return;

      const rootTop = root.getBoundingClientRect().top;
      const seen = new Set<HTMLElement>();
      const tops: number[] = [];
      for (const m of marks) {
        const block = ((m as HTMLElement).closest(BLOCK_SELECTOR) as HTMLElement) ?? (m as HTMLElement);
        if (seen.has(block)) continue;
        seen.add(block);
        tops.push(block.getBoundingClientRect().top - rootTop + root.scrollTop);
      }
      tops.sort((a, b) => a - b);

      const cur = root.scrollTop + BEAT_OFFSET;
      const target =
        dir === 1
          ? tops.find((t) => t > cur + 4)
          : [...tops].reverse().find((t) => t < cur - 4);
      if (target == null) return;
      root.scrollTo({ top: Math.max(0, target - BEAT_OFFSET), behavior: "smooth" });
    },
    [container],
  );

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (isTyping(e.target)) return;

      // 토글은 읽기 모드 밖에서도 받는다.
      if ((e.metaKey || e.ctrlKey) && e.key === ".") {
        if (!enabledRef.current) return;
        e.preventDefault();
        toggle();
        return;
      }

      if (!readingRef.current || !enabledRef.current || blockedRef.current) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      if (e.key === "Escape") {
        e.preventDefault();
        exit();
      } else if (e.key === "+" || e.key === "=") {
        e.preventDefault();
        bumpScale(SCALE_STEP);
      } else if (e.key === "-" || e.key === "_") {
        e.preventDefault();
        bumpScale(-SCALE_STEP);
      } else if (e.key === "0") {
        e.preventDefault();
        resetScale();
      } else if (e.key === "j") {
        e.preventDefault();
        jumpBeat(1);
      } else if (e.key === "k") {
        e.preventDefault();
        jumpBeat(-1);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [toggle, exit, bumpScale, resetScale, jumpBeat]);

  return { reading: active, scale, toggle, exit, setScale, bumpScale, resetScale, jumpBeat };
}
