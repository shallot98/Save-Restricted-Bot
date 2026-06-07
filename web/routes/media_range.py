"""HTTP Range parsing and streaming helpers for media routes."""

from __future__ import annotations

import re
from dataclasses import dataclass

RANGE_CHUNK_SIZE = 8192
RANGE_PATTERN = re.compile(r"bytes=(\d*)-(\d*)")


@dataclass(frozen=True)
class ByteRange:
    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start + 1


def parse_byte_range(range_header: str, file_size: int) -> ByteRange | None:
    match = RANGE_PATTERN.search(range_header)
    if not match:
        return None

    start_str, end_str = match.group(1), match.group(2)
    byte_range = _suffix_range(end_str, file_size) if not start_str else _explicit_range(
        start_str,
        end_str,
        file_size,
    )
    return byte_range if _is_valid_range(byte_range, file_size) else None


def _suffix_range(end_str: str, file_size: int) -> ByteRange | None:
    if not end_str:
        return None
    suffix_len = int(end_str)
    if suffix_len <= 0:
        return None
    return ByteRange(start=max(file_size - suffix_len, 0), end=file_size - 1)


def _explicit_range(start_str: str, end_str: str, file_size: int) -> ByteRange:
    start = int(start_str)
    end = int(end_str) if end_str else file_size - 1
    return ByteRange(start=start, end=min(end, file_size - 1))


def _is_valid_range(byte_range: ByteRange | None, file_size: int) -> bool:
    if byte_range is None:
        return False
    return 0 <= byte_range.start < file_size and byte_range.end >= byte_range.start


def iter_file_range(path: str, byte_range: ByteRange):
    with open(path, "rb") as file_obj:
        file_obj.seek(byte_range.start)
        remaining = byte_range.length
        while remaining > 0:
            chunk = file_obj.read(min(RANGE_CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk
