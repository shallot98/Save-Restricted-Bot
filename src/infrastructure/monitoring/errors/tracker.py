"""
错误追踪器

作为统一入口：
- 记录 ErrorMetric（写入 MetricCollector）
- 写入 ErrorAggregator（错误聚合/趋势数据源）
- 可选触发告警（由 AlertManager 去重/抑制）
"""

from __future__ import annotations

import logging
import os
import traceback
from typing import Any, Dict, Optional

from src.infrastructure.monitoring import get_metric_collector, is_monitoring_enabled
from src.infrastructure.monitoring.core.metrics import ErrorMetric, MetricType
from src.infrastructure.monitoring.errors.aggregator import ErrorAggregator, ErrorGroup

logger = logging.getLogger(__name__)

_error_tracker: Optional["ErrorTracker"] = None


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


def _safe_stacktrace(error: BaseException, *, max_length: int) -> str:
    try:
        stack = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        return stack[:max_length]
    except Exception:
        return ""


def _try_send_alert(level: str, title: str, message: str, details: Dict[str, Any]) -> None:
    try:
        from src.infrastructure.monitoring.alerting.alert_manager import get_alert_manager  # noqa: WPS433

        get_alert_manager().send_alert(level=level, title=title, message=message, details=details)
    except Exception:
        return


class ErrorTracker:
    def __init__(
        self,
        *,
        enabled: bool = True,
        aggregation_window_seconds: Optional[int] = None,
        retention_seconds: Optional[int] = None,
        max_stacktrace_length: Optional[int] = None,
        alert_enabled: Optional[bool] = None,
    ) -> None:
        self._enabled = enabled
        self._collector = get_metric_collector()
        self._max_stacktrace_length = max_stacktrace_length if max_stacktrace_length is not None else _env_int("ERROR_MAX_STACKTRACE_LENGTH", 2000)
        self._alert_enabled = alert_enabled if alert_enabled is not None else _env_bool("ERROR_ALERT_ENABLED", True)

        self._aggregator = ErrorAggregator(
            aggregation_window_seconds=aggregation_window_seconds if aggregation_window_seconds is not None else _env_int("ERROR_AGGREGATION_WINDOW_SECONDS", 300),
            retention_seconds=retention_seconds if retention_seconds is not None else _env_int("ERROR_RETENTION_SECONDS", 3600),
        )

    @property
    def enabled(self) -> bool:
        return self._enabled and is_monitoring_enabled() and _env_bool("ERROR_TRACKING_ENABLED", True)

    @property
    def aggregator(self) -> ErrorAggregator:
        return self._aggregator

    def track_error(self, *, error: BaseException, context: Optional[Dict[str, Any]] = None) -> Optional[ErrorGroup]:
        if not self.enabled:
            return None

        context = context or {}
        error_type = type(error).__name__
        error_message = str(error)
        stacktrace = _safe_stacktrace(error, max_length=self._max_stacktrace_length)

        try:
            group = self._aggregator.add(
                error_type=error_type,
                error_message=error_message,
                stacktrace=stacktrace,
                context=context,
            )
        except Exception:
            logger.exception("错误聚合失败（已忽略）")
            group = None

        try:
            metric = ErrorMetric(
                name="error.occurred",
                value=1.0,
                metric_type=MetricType.COUNTER,
                error_type=error_type,
                error_message=error_message,
                stacktrace=stacktrace,
                context=context,
                tags={
                    "error_type": error_type,
                    "fingerprint": group.fingerprint if group else "unknown",
                },
            )
            self._collector.collect(metric)
        except Exception:
            logger.exception("错误指标记录失败（已忽略）")

        if self._alert_enabled and group is not None:
            # 告警内容保持稳定，便于 AlertManager 去重
            _try_send_alert(
                level="error",
                title="错误追踪",
                message=f"{group.error_type}: {group.last_message}",
                details={"fingerprint": group.fingerprint, "error_type": group.error_type},
            )

        return group


def get_error_tracker() -> ErrorTracker:
    global _error_tracker
    if _error_tracker is None:
        _error_tracker = ErrorTracker()
    return _error_tracker

