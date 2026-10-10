// 섹션 접기: 렌더된 본문의 헤딩에 접기 토글을 달고, 접힌 헤딩 키를 노트별로 localStorage에 저장한다.

const STORAGE_PREFIX = "mdedit:fold:";
const HEADING_SELECTOR = "h1, h2, h3, h4, h5, h6";

function level(el: Element): number {
  return parseInt(el.tagName.slice(1), 10);
}

// 같은 제목이 반복되어도 구분되도록 "순번:텍스트"를 키로 쓴다
function headingKey(el: Element, index: number): string {
  return `${index}:${(el.textContent || "").replace(/[▾▸]/g, "").trim().slice(0, 60)}`;
}

export function loadFolded(path: string): Set<string> {
  try {
    const raw = localStorage.getItem(STORAGE_PREFIX + path);
    const arr = raw ? JSON.parse(raw) : [];
    return new Set(Array.isArray(arr) ? arr.filter((x) => typeof x === "string") : []);
  } catch {
    return new Set();
  }
}

export function saveFolded(path: string, folded: Set<string>): void {
  try {
    if (folded.size === 0) localStorage.removeItem(STORAGE_PREFIX + path);
    else localStorage.setItem(STORAGE_PREFIX + path, JSON.stringify([...folded]));
  } catch {
    /* 저장 불가 환경에서는 세션 내 상태만 유지 */
  }
}

// 접힌 헤딩 아래 내용을 숨김 처리한다 (다음 같거나 높은 레벨 헤딩 전까지, 중첩 접기 포함)
function applyVisibility(container: HTMLElement): void {
  const children = Array.from(container.children);
  let hideUntilLevel: number | null = null;
  for (const el of children) {
    const isHeading = el.matches(HEADING_SELECTOR);
    if (hideUntilLevel !== null) {
      if (isHeading && level(el) <= hideUntilLevel) hideUntilLevel = null;
      else {
        el.classList.add("fold-hidden");
        continue;
      }
    }
    el.classList.remove("fold-hidden");
    if (isHeading && el.getAttribute("data-folded") === "true") hideUntilLevel = level(el);
  }
}

/** 헤딩에 토글을 부착하고 저장된 접힘 상태를 복원한다. 정리 함수를 반환한다. */
export function setupFolding(container: HTMLElement, path: string): () => void {
  const folded = loadFolded(path);
  const headings = Array.from(container.children).filter((el) => el.matches(HEADING_SELECTOR));

  headings.forEach((h, i) => {
    const key = headingKey(h, i);
    const isFolded = folded.has(key);
    h.setAttribute("data-fold-key", key);
    h.setAttribute("data-folded", String(isFolded));
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "fold-toggle";
    btn.setAttribute("aria-label", "섹션 접기/펼치기");
    btn.setAttribute("aria-expanded", String(!isFolded));
    btn.textContent = isFolded ? "▸" : "▾";
    btn.addEventListener("click", () => {
      const next = h.getAttribute("data-folded") !== "true";
      h.setAttribute("data-folded", String(next));
      btn.setAttribute("aria-expanded", String(!next));
      btn.textContent = next ? "▸" : "▾";
      if (next) folded.add(key);
      else folded.delete(key);
      saveFolded(path, folded);
      applyVisibility(container);
    });
    h.insertBefore(btn, h.firstChild);
  });
  applyVisibility(container);

  return () => {
    container.querySelectorAll(".fold-toggle").forEach((b) => b.remove());
    container.querySelectorAll(".fold-hidden").forEach((e) => e.classList.remove("fold-hidden"));
  };
}
