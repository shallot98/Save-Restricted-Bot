"""
内存时序存储（最近窗口）

实现思路：
- 复用 MetricAggregator 作为指标原始数据的窗口存储
- 复用 ErrorAggregator 作为错误聚合与趋势数据源
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.infrastructure.monitoring.core.aggregator import MetricAggregator
    from src.infrastructure.monitoring.errors.aggregator import ErrorAggregator

_memory_store: Optional["MemoryStore"] = None


def _env_int(key: str, default: int) -> int:
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


class MemoryStore:
    def __init__(self) -> None:
        from src.infrastructure.monitoring import get_metric_aggregator
        from src.infrastructure.monitoring.errors.tracker import get_error_tracker

        self._metrics: MetricAggregator = get_metric_aggregator()
        self._errors: ErrorAggregator = get_error_tracker().aggregator

    def metrics_recent(self, *, limit: int = 200) -> List[Dict[str, Any]]:
        return self._metrics.recent(limit=limit)

    def metrics_snapshot(self, *, window_seconds: int = 60) -> Dict[str, Any]:
        return self._metrics.snapshot(window_seconds=window_seconds)

    def errors_top(self, *, limit: int = 10) -> List[Dict[str, Any]]:
        from src.infrastructure.monitoring.errors.analyzer import get_error_analyzer  # noqa: WPS433

        window_seconds = _env_int("ERROR_TREND_WINDOW_SECONDS", 3600)
        return get_error_analyzer().top_errors(limit=limit, window_seconds=window_seconds)

    def errors_trend(self, *, bucket_seconds: int = 60) -> Dict[str, Any]:
        from src.infrastructure.monitoring.errors.analyzer import get_error_analyzer  # noqa: WPS433

        window_seconds = _env_int("ERROR_TREND_WINDOW_SECONDS", 3600)
        return get_error_analyzer().trend(window_seconds=window_seconds, bucket_seconds=bucket_seconds)


def get_memory_store() -> MemoryStore:
    global _memory_store
    if _memory_store is None:
        _memory_store = MemoryStore()
    return _memory_store

