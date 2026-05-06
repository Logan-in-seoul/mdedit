"""Wiki Link([[파일명]]) 파서 및 경로 리졸버.

`[[파일명]]` 또는 `[[파일명|표시텍스트]]` 패턴을 파싱하고,
files 인덱스에서 일치하는 가상 경로를 찾아 반환한다.

검색 우선순위:
1. 정확한 파일명 일치 (확장자 포함)
2. stem 일치 (확장자 제외)
3. 경로 끝부분 일치 (서브디렉토리 포함 제목으로 검색 시)

여러 개 일치하면 첫 번째 결과를 반환한다 (mdedit 규칙: 가장 짧은 경로 우선).
"""
from __future__ import annotations

import re
from typing import NamedTuple

import app.index as fts_index

# [[파일명]] 또는 [[파일명|표시텍스트]]
_WIKI_RE = re.compile(r"\[\[([^\[\]|]+?)(?:\|([^\[\]]+))?\]\]")

_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")

# Reject titles that are clearly code artifacts, not file paths.
# Matches: contains quotes, starts with $, bare :word: char-class, coord like "1,1"
_INVALID_TITLE_RE = re.compile(r'["\']|\$|^:\w+:$|^\d+,\d+$')


def _mask_code_blocks(text: str) -> str:
    """코드 블록 내부를 공백으로 대체해 wiki link 파싱에서 제외한다.

    오프셋을 보존하므로 WikiRef.start/end는 원문 기준으로 유효하다.
    펜스 블록은 라인 단위 파서로 처리해 중첩/연속 펜스 오인식을 방지한다.
    """
    chars = list(text)

    # Fenced code blocks: line-by-line state machine to correctly handle
    # consecutive blocks (regex approach misidentifies bare ``` as opening fence)
    fence_open: str | None = None
    pos = 0
    for line in text.splitlines(keepends=True):
        stripped = line.rstrip("\r\n")
        if fence_open is None:
            # Opening fence: ``` or ~~~ followed by optional language
            if stripped.startswith("```") or stripped.startswith("~~~"):
                fence_open = stripped[:3]
                for i in range(pos, pos + len(line)):
                    chars[i] = " "
        else:
            for i in range(pos, pos + len(line)):
                chars[i] = " "
            # Closing fence: same marker, nothing else (or only spaces after)
            if stripped.rstrip() == fence_open:
                fence_open = None
        pos += len(line)

    # Inline code spans
    for m in _INLINE_CODE_RE.finditer(text):
        for i in range(m.start(), m.end()):
            chars[i] = " "

    return "".join(chars)


class WikiRef(NamedTuple):
    title: str        # [[...]] 안의 파일명/제목
    display: str      # 표시 텍스트 (없으면 title과 동일)
    start: int        # 원문에서 [[ 시작 오프셋
    end: int          # 원문에서 ]] 끝 오프셋


def parse_wikilinks(text: str) -> list[WikiRef]:
    """마크다운 본문에서 [[...]] 패턴을 모두 추출한다."""
    masked = _mask_code_blocks(text)
    refs: list[WikiRef] = []
    for m in _WIKI_RE.finditer(masked):
        title = m.group(1).strip()
        if _INVALID_TITLE_RE.search(title):
            continue
        display = m.group(2).strip() if m.group(2) else title
        refs.append(WikiRef(title=title, display=display, start=m.start(), end=m.end()))
    return refs


def resolve_title(title: str) -> str | None:
    """title에 해당하는 가상 경로를 인덱스에서 찾아 반환한다.

    없으면 None을 반환한다.
    """
    try:
        db = fts_index.get_db()
    except RuntimeError:
        return None

    rows = db.execute("SELECT path, name FROM files").fetchall()
    if not rows:
        return None

    title_lower = title.lower()
    # 확장자 포함 파일명이 주어진 경우
    if not title_lower.endswith(".md"):
        title_with_ext = title_lower + ".md"
    else:
        title_with_ext = title_lower

    exact: list[str] = []
    stem: list[str] = []
    partial: list[str] = []

    for path, name in rows:
        name_lower = name.lower()
        # 1순위: 정확한 파일명 일치
        if name_lower == title_with_ext or name_lower == title_lower:
            exact.append(path)
        else:
            # stem 추출 (foo.md → foo)
            name_stem = name_lower[:-3] if name_lower.endswith(".md") else name_lower
            title_stem = title_lower[:-3] if title_lower.endswith(".md") else title_lower
            # 2순위: stem 일치
            if name_stem == title_stem:
                stem.append(path)
            # 3순위: 경로 끝부분 포함
            elif path.lower().endswith("/" + title_lower) or path.lower().endswith("/" + title_with_ext):
                partial.append(path)

    # 우선순위 순으로 첫 번째 반환, 동점이면 경로 길이 짧은 것 우선
    for candidates in (exact, stem, partial):
        if candidates:
            return min(candidates, key=len)
    return None
