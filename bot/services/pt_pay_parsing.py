"""PT pay message parsing helpers."""

from __future__ import annotations

import re

PT_CODE_LINE_PATTERN = re.compile(r"(?im)^\s*(PT-[A-Za-z0-9][A-Za-z0-9_-]*)\s*$")


def extract_pt_codes(text: str) -> list[str]:
    if not text:
        return []

    result: list[str] = []
    seen: set[str] = set()
    for match in PT_CODE_LINE_PATTERN.finditer(text):
        code = match.group(1).strip()
        if code in seen:
            continue
        seen.add(code)
        result.append(code)
    return result
