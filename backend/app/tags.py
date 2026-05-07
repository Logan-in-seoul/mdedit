"""마크다운 본문에서 #tag 형식을 추출한다.

P3 태그 시스템 1단계: 순수 추출 함수.
- frontmatter, fenced code, inline code, URL fragment, 숫자전용은 제외
- 한글, 영숫자, _, -, / 허용 (계층 태그 #project/guidedtour 지원)
- 등장 순서 유지 + dedupe
"""
from __future__ import annotations

import re
from typing import List

# 태그 본체 문자: 영숫자, 언더스코어, 대시, 슬래시, 한글
_TAG_BODY = r"[A-Za-z0-9_\-/\uAC00-\uD7A3]+"

# 태그 패턴: 직전이 공백/문자열 시작/구두점, # 다음 첫 글자가 숫자가 아니어야 하며
# # 자체가 두 번 연속(##)이면 헤딩으로 간주
_TAG_RE = re.compile(
    rf"(?:(?<=^)|(?<=[\s,.\!?;:\(\[\{{]))#(?!#)(?P<tag>(?![0-9])(?:{_TAG_BODY}))"
)

_FENCE_RE = re.compile(r"^```", re.MULTILINE)
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
_FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)


def _strip_frontmatter(text: str) -> str:
    return _FRONTMATTER_RE.sub("", text, count=1)


def _strip_fenced_code(text: str) -> str:
    """```...``` 블록 통째로 제거."""
    out: list[str] = []
    in_fence = False
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append(line)
    return "".join(out)


def _strip_inline_code(text: str) -> str:
    return _INLINE_CODE_RE.sub("", text)


def extract_tags(source: str) -> List[str]:
    """마크다운 source에서 태그 목록을 등장 순서대로 dedupe해서 반환한다."""
    if not source:
        return []
    cleaned = _strip_frontmatter(source)
    cleaned = _strip_fenced_code(cleaned)
    cleaned = _strip_inline_code(cleaned)

    seen: set[str] = set()
    tags: list[str] = []
    for match in _TAG_RE.finditer(cleaned):
        tag = match.group("tag")
        # 끝에 붙은 / 는 잘라내기 (#a/b/ -> a/b)
        tag = tag.rstrip("/-_")
        if not tag:
            continue
        if tag not in seen:
            seen.add(tag)
            tags.append(tag)
    return tags
