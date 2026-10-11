// 본문 링크 처리. 문서 안의 상대 경로 링크를 mdedit 가상 경로로 바꾼다.

const SCHEME = /^([^:/]+:\/\/)(.*)$/;

/**
 * 현재 문서의 가상 경로(`root://dir/a.md`, `ext:///abs/a.md`)를 기준으로 상대 링크를 푼다.
 * 풀 수 없으면 null.
 */
export function resolveRelative(current: string, href: string): string | null {
  const m = SCHEME.exec(current);
  if (!m || !href) return null;
  const [, scheme, rest] = m;
  const absolute = href.startsWith("/");
  // ext://는 절대 경로를 그대로 담으므로 맨 앞 빈 조각(루트)을 지킨다
  const keepRoot = rest.startsWith("/");
  const base = absolute ? [] : rest.split("/").slice(0, -1).filter((s) => s !== "");
  const out = [...base];
  for (const seg of href.split("/")) {
    if (seg === "" || seg === ".") continue;
    if (seg === "..") {
      if (out.length === 0) return null; // 루트 밖
      out.pop();
    } else {
      out.push(seg);
    }
  }
  if (out.length === 0) return null;
  return scheme + (keepRoot ? "/" : "") + out.join("/");
}

export function isMarkdownHref(href: string): boolean {
  return /\.(md|markdown)$/i.test(href);
}

/** `scheme:` 으로 시작하는 절대 URL인지 (http, mailto 등). */
export function hasScheme(href: string): boolean {
  return /^[a-z][a-z0-9+.-]*:/i.test(href);
}
