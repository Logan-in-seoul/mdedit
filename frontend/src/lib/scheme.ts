// 지금 화면이 다크인지 라이트인지. global.css의 prefers-color-scheme과 같은 기준을 쓴다.
import { useSyncExternalStore } from "react";

export type Scheme = "light" | "dark";

const QUERY = "(prefers-color-scheme: dark)";

function mql(): MediaQueryList | null {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia(QUERY)
    : null;
}

export function currentScheme(): Scheme {
  return mql()?.matches ? "dark" : "light";
}

function subscribe(cb: () => void): () => void {
  const m = mql();
  if (!m) return () => {};
  m.addEventListener?.("change", cb);
  return () => m.removeEventListener?.("change", cb);
}

export function useColorScheme(): Scheme {
  return useSyncExternalStore(subscribe, currentScheme, () => "light");
}
