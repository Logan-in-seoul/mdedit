// 본문 줄 너비. px이 아니라 글자 수(em)로 잡아서 글자를 키워도 한 줄 글자 수가 유지된다.
// 값은 global.css의 `.main-inner > .reader { max-width: var(--measure) }`가 읽는다.

import { useCallback, useState } from "react";

// v2: 기본값을 화면 폭에 맞추는 「자동」으로 바꾸면서 예전 저장값(보통 47em)을 버린다.
const MEASURE_KEY = "mdedit:measure:v2";

export const MEASURES = [
  // 본문 칸 폭을 그대로 쓴다. 창을 줄이면 같이 줄어든다. 2,844px 창에서 92em 상한이 본문을 60%로 묶었다.
  { id: "auto", label: "자동", css: "100%" },
  { id: "narrow", label: "좁게", css: "40em" },
  { id: "normal", label: "보통", css: "47em" },
  { id: "wide", label: "넓게", css: "62em" },
  { id: "full", label: "전체", css: "none" },
] as const;

export type MeasureId = (typeof MEASURES)[number]["id"];

const DEFAULT_ID: MeasureId = "auto";

function readInitial(): MeasureId {
  try {
    const raw = localStorage.getItem(MEASURE_KEY);
    return MEASURES.some((m) => m.id === raw) ? (raw as MeasureId) : DEFAULT_ID;
  } catch {
    return DEFAULT_ID;
  }
}

export interface Measure {
  id: MeasureId;
  label: string;
  css: string;
  /** 자동, 좁게, 보통, 넓게, 전체 순서로 돈다. */
  cycle: () => void;
}

export function useMeasure(): Measure {
  const [id, setId] = useState<MeasureId>(readInitial);

  const cycle = useCallback(() => {
    setId((prev) => {
      const i = MEASURES.findIndex((m) => m.id === prev);
      const next = MEASURES[(i + 1) % MEASURES.length].id;
      try {
        localStorage.setItem(MEASURE_KEY, next);
      } catch {
        // 저장 불가 환경에서는 세션 내 상태만 유지
      }
      return next;
    });
  }, []);

  const current = MEASURES.find((m) => m.id === id) ?? MEASURES[0];
  return { id: current.id, label: current.label, css: current.css, cycle };
}
