from __future__ import annotations
import re

BLOCK_RE = re.compile(r'^(.+?)\s+\^([a-zA-Z0-9-]+)\s*$', re.MULTILINE)


def extract_blocks(text: str) -> dict[str, str]:
    """마크다운 텍스트에서 ^block-id 블록을 추출해 {block_id: content} 반환."""
    result: dict[str, str] = {}
    for m in BLOCK_RE.finditer(text):
        content, block_id = m.group(1).strip(), m.group(2)
        result[block_id] = content
    return result
