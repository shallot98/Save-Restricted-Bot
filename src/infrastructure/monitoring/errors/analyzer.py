"""
错误分析器

提供：
- Top N 错误热点
- 时间趋势（按 bucket 聚合）
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .aggregator import ErrorAggregator, ErrorGroup

_error_analyzer: Optional["ErrorAnalyzer"] = None


def _env_int(key: str, default: int) -> int:
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


@dataclass(frozen=True)
class TrendPoint:
    bucket_start_epoch: float
    count: int

    def to_dict(self) -> Dict[str, Any]:
        return {"bucket_start_epoch": self.bucket_start_epoch, "count": self.count}


class ErrorAnalyzer:
    def __init__(self, aggregator: ErrorAggregator) -> None:
        self._aggregator = aggregator

    def top_errors(self, *, limit: int = 10, window_seconds: Optional[int] = None) -> List[Dict[str, Any]]:
        limit = max(int(limit), 1)
        window_seconds = window_seconds if window_seconds is not None else _env_int("ERROR_TREND_WINDOW_SECONDS", 3600)
        cutoff = time.time() - max(int(window_seconds), 1)

        groups = self._aggregator.groups()
        scored: List[ErrorGroup] = []
        for group in groups:
            if group.last_seen_epoch < cutoff:
                continue
            scored.append(group)

        scored.sort(key=lambda g: (g.count, g.last_seen_epoch), reverse=True)
        return [g.to_dict() for g in scored[:limit]]

    def trend(self, *, window_seconds: Optional[int] = None, bucket_seconds: int = 60) -> Dict[str, Any]:
        window_seconds = window_seconds if window_seconds is not None else _env_int("ERROR_TREND_WINDOW_SECONDS", 3600)
        window_seconds = max(int(window_seconds), 1)
        bucket_seconds = max(int(bucket_seconds), 1)

        now = time.time()
        cutoff = now - window_seconds
        events = self._aggregator.recent_events(window_seconds=window_seconds)

        buckets: Dict[int, int] = {}
        for ts, _fp in events:
            if ts < cutoff:
                continue
            bucket_index = int((ts - cutoff) // bucket_seconds)
            buckets[bucket_index] = buckets.get(bucket_index, 0) + 1

        points: List[TrendPoint] = []
        bucket_count = int((window_seconds + bucket_seconds - 1) // bucket_seconds)
        for idx in range(bucket_count):
            bucket_start = cutoff + idx * bucket_seconds
            points.append(TrendPoint(bucket_start_epoch=bucket_start, count=buckets.get(idx, 0)))

        return {
            "window_seconds": window_seconds,
            "bucket_seconds": bucket_seconds,
            "points": [p.to_dict() for p in points],
        }


def get_error_analyzer() -> ErrorAnalyzer:
    global _error_analyzer
    if _error_analyzer is None:
        from .tracker import get_error_tracker  # noqa: WPS433

        _error_analyzer = ErrorAnalyzer(get_error_tracker().aggregator)
    return _error_analyzer

