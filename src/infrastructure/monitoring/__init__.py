"""
监控与可观测性基础设施

提供全局可复用的指标收集/聚合能力，供性能监控、告警与错误追踪模块使用。
"""

from __future__ import annotations

import os
from typing import Optional

from .core.aggregator import MetricAggregator
from .core.collector import MetricCollector
from .storage.sqlite_store2 import get_sqlite_store2

_metric_aggregator: Optional[MetricAggregator] = None
_metric_collector: Optional[MetricCollector] = None


def _env_bool(key: str, default: bool) -> bool:
    value = os.environ.get(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(key: str, default: int) -> int:
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


def _env_float(key: str, default: float) -> float:
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return float(value.strip())
    except ValueError:
        return default


def is_monitoring_enabled() -> bool:
    return _env_bool("MONITORING_ENABLED", True)


def is_metric_persistence_enabled() -> bool:
    """指标持久化默认停用（monitoring.db 曾以 3.3MB/天 增长且 UI 无入口）。

    需要重新采集时显式设置 MONITORING_PERSIST_ENABLED=1。
    """
    return _env_bool("MONITORING_PERSIST_ENABLED", False) and is_monitoring_enabled()


def get_metric_aggregator() -> MetricAggregator:
    global _metric_aggregator
    if _metric_aggregator is None:
        retention_hours = _env_int("MONITORING_MEMORY_RETENTION_HOURS", 1)
        _metric_aggregator = MetricAggregator(retention_seconds=retention_hours * 3600)
    return _metric_aggregator


def get_metric_collector() -> MetricCollector:
    global _metric_collector
    if _metric_collector is None:
        persist_interval_seconds = _env_float("MONITORING_PERSIST_INTERVAL_SECONDS", 5.0)
        persist_batch_size = _env_int("MONITORING_PERSIST_BATCH_SIZE", 1000)
        persist_store = get_sqlite_store2() if is_metric_persistence_enabled() else None
        _metric_collector = MetricCollector(
            aggregator=get_metric_aggregator(),
            enabled=is_monitoring_enabled(),
            persist_store=persist_store,
            persist_interval_seconds=persist_interval_seconds,
            persist_batch_size=persist_batch_size,
        )
    return _metric_collector


__all__ = [
    "MetricAggregator",
    "MetricCollector",
    "get_metric_aggregator",
    "get_metric_collector",
    "is_monitoring_enabled",
    "is_metric_persistence_enabled",
]
