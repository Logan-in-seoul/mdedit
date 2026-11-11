// 좁은 화면 판정. 이 폭 아래에서 목록과 목차는 본문 칸을 나눠 갖지 않고 위에 겹쳐 뜬다.
// global.css 「좁은 화면」 절의 미디어 쿼리와 같은 값이다.
export const NARROW_QUERY = "(max-width: 760px)";

export function isNarrow(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia(NARROW_QUERY).matches
    : false;
}
