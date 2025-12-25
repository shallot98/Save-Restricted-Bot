"""
业务指标收集器

以低开销的方式在内存中聚合计数，并定期刷新到 MetricCollector。
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from src.infrastructure.monitoring import get_metric_collector, is_monitoring_enabled
from src.infrastructure.monitoring.core.metrics import BusinessMetric, MetricType

logger = logging.getLogger(__name__)

_business_metrics: Optional["BusinessMetricsCollector"] = None


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


@dataclass(frozen=True)
class _CounterKey:
    name: str
    tags: Tuple[Tuple[str, str], ...]
    category: str
    success: bool
    error_type: Optional[str]


class BusinessMetricsCollector:
    """业务指标聚合收集器（周期性刷新）"""

    def __init__(
        self,
        *,
        enabled: bool = True,
        report_interval_seconds: Optional[int] = None,
    ) -> None:
        self._enabled = enabled
        self._interval = report_interval_seconds if report_interval_seconds is not None else _env_int("BUSINESS_METRICS_REPORT_INTERVAL_SECONDS", 300)
        self._collector = get_metric_collector()
        self._lock = threading.RLock()
        self._counters: Dict[_CounterKey, int] = {}
        self._stop_event = threading.Event()
        self._worker = threading.Thread(target=self._run, name="business-metrics", daemon=True)

        if self.enabled:
            self._worker.start()

    @property
    def enabled(self) -> bool:
        return self._enabled and is_monitoring_enabled() and _env_bool("BUSINESS_METRICS_ENABLED", True)

    def stop(self, timeout_seconds: float = 2.0) -> None:
        self._stop_event.set()
        if self._worker.is_alive():
            self._worker.join(timeout=timeout_seconds)

    def flush(self) -> None:
        if not self.enabled:
            return
        self._flush_once()

    def record_message_processed(self, *, success: bool, category: str, error_type: Optional[str] = None) -> None:
        self._inc(
            name="business.message_processed.count",
            tags={"category": category, "success": str(success).lower()},
            category=category,
            success=success,
            error_type=error_type,
        )

    def record_forward(self, *, success: bool, preserve_source: bool, error_type: Optional[str] = None) -> None:
        self._inc(
            name="business.forward.count",
            tags={"preserve_source": str(preserve_source).lower(), "success": str(success).lower()},
            category="forward",
            success=success,
            error_type=error_type,
        )

    def record_note_saved(self, *, success: bool, has_media: bool, error_type: Optional[str] = None) -> None:
        self._inc(
            name="business.note_saved.count",
            tags={"has_media": str(has_media).lower(), "success": str(success).lower()},
            category="note_saved",
            success=success,
            error_type=error_type,
        )

    def record_calibration(self, *, success: bool, task_type: str, error_type: Optional[str] = None) -> None:
        self._inc(
            name="business.calibration.count",
            tags={"task_type": task_type, "success": str(success).lower()},
            category="calibration",
            success=success,
            error_type=error_type,
        )

    def _inc(
        self,
        *,
        name: str,
        tags: Dict[str, str],
        category: str,
        success: bool,
        error_type: Optional[str],
    ) -> None:
        if not self.enabled:
            return
        key = _CounterKey(
            name=name,
            tags=tuple(sorted(tags.items())),
            category=category,
            success=success,
            error_type=error_type,
        )
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + 1

    def _run(self) -> None:
        next_flush = time.monotonic() + max(self._interval, 1)
        while not self._stop_event.is_set():
            now = time.monotonic()
            sleep_seconds = max(next_flush - now, 0.1)
            self._stop_event.wait(timeout=sleep_seconds)
            if self._stop_event.is_set():
                break
            if not self.enabled:
                next_flush = time.monotonic() + max(self._interval, 1)
                continue
            self._flush_once()
            next_flush = time.monotonic() + max(self._interval, 1)

        # 退出前尽力刷新
        try:
            self._flush_once()
        except Exception:
            logger.exception("业务指标退出刷新失败（已忽略）")

    def _flush_once(self) -> None:
        with self._lock:
            if not self._counters:
                return
            snapshot = self._counters
            self._counters = {}

        metrics = []
        for key, count in snapshot.items():
            metrics.append(
                BusinessMetric(
                    name=key.name,
                    value=float(count),
                    metric_type=MetricType.COUNTER,
                    category=key.category,
                    success=key.success,
                    error_type=key.error_type,
                    tags=dict(key.tags),
                )
            )

        self._collector.collect_many(metrics)


def get_business_metrics() -> BusinessMetricsCollector:
    global _business_metrics
    if _business_metrics is None:
        _business_metrics = BusinessMetricsCollector()
    return _business_metrics

