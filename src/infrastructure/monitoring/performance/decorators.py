"""
性能监控装饰器与上下文管理器

提供对同步/异步函数的执行耗时监控，并将指标提交到全局 MetricCollector。
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar

from src.infrastructure.monitoring import get_metric_collector, is_monitoring_enabled
from src.infrastructure.monitoring.core.metrics import MetricType, PerformanceMetric

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(frozen=True)
class PerformanceMonitorRuntime:
    collector: Any
    operation: str
    threshold_ms: int
    tags: Dict[str, str]


def _env_int(key: str, default: int) -> int:
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


def _try_send_alert(level: str, title: str, message: str, *, details: Dict[str, Any]) -> None:
    try:
        from src.infrastructure.monitoring.alerting.alert_manager import get_alert_manager  # noqa: WPS433

        alert_manager = get_alert_manager()
        alert_manager.send_alert(level=level, title=title, message=message, details=details)
    except Exception:
        # 阶段3未落地前，或告警系统故障时，保证不影响主流程
        return


def monitor_performance(
    name: Optional[str] = None,
    *,
    threshold_ms: Optional[int] = None,
    tags: Optional[Dict[str, str]] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    函数性能监控装饰器

    Args:
        name: 指标中的 operation 名称（默认使用 module.qualname）
        threshold_ms: 慢操作阈值，超过则记录 warning（默认读取 SLOW_OPERATION_THRESHOLD_MS，默认1000）
        tags: 自定义 tags
    """
    threshold_ms = threshold_ms if threshold_ms is not None else _env_int("SLOW_OPERATION_THRESHOLD_MS", 1000)
    tags = tags or {}

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        runtime = PerformanceMonitorRuntime(
            collector=get_metric_collector(),
            operation=_operation_name(name, func),
            threshold_ms=threshold_ms,
            tags=tags,
        )

        if asyncio.iscoroutinefunction(func):
            return _wrap_async_function(func, runtime)
        return _wrap_sync_function(func, runtime)

    return decorator


def _operation_name(name: Optional[str], func: Callable[..., Any]) -> str:
    return name or f"{func.__module__}.{getattr(func, '__qualname__', func.__name__)}"


def _wrap_async_function(func: Callable[..., T], runtime: PerformanceMonitorRuntime) -> Callable[..., T]:
    @wraps(func)
    async def async_wrapper(*args: Any, **kwargs: Any):  # type: ignore[override]
        if not is_monitoring_enabled():
            return await func(*args, **kwargs)

        start = time.perf_counter()
        try:
            return await func(*args, **kwargs)
        finally:
            _record_duration(runtime, _duration_ms(start))

    return async_wrapper  # type: ignore[return-value]


def _wrap_sync_function(func: Callable[..., T], runtime: PerformanceMonitorRuntime) -> Callable[..., T]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any):  # type: ignore[override]
        if not is_monitoring_enabled():
            return func(*args, **kwargs)

        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            _record_duration(runtime, _duration_ms(start))

    return wrapper  # type: ignore[return-value]


def _duration_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000.0


def _record_duration(runtime: PerformanceMonitorRuntime, duration_ms: float) -> None:
    runtime.collector.collect(_build_performance_metric(runtime, duration_ms))
    if duration_ms >= runtime.threshold_ms:
        _log_and_alert_slow_operation(runtime, duration_ms)


def _build_performance_metric(
    runtime: PerformanceMonitorRuntime,
    duration_ms: float,
) -> PerformanceMetric:
    return PerformanceMetric(
        name="performance.duration_ms",
        value=duration_ms,
        metric_type=MetricType.TIMER,
        duration_ms=duration_ms,
        tags={**runtime.tags, "operation": runtime.operation},
    )


def _log_and_alert_slow_operation(runtime: PerformanceMonitorRuntime, duration_ms: float) -> None:
    logger.warning("慢操作: %s (%.2fms >= %dms)", runtime.operation, duration_ms, runtime.threshold_ms)
    _try_send_alert(
        level="warning",
        title="慢操作检测",
        message=f"{runtime.operation} 耗时 {duration_ms:.2f}ms",
        details={
            "operation": runtime.operation,
            "duration_ms": duration_ms,
            "threshold_ms": runtime.threshold_ms,
        },
    )


@contextmanager
def performance_context(
    operation: str,
    *,
    threshold_ms: Optional[int] = None,
    tags: Optional[Dict[str, str]] = None,
) -> Any:
    """代码块性能监控上下文管理器"""
    threshold_ms = threshold_ms if threshold_ms is not None else _env_int("SLOW_OPERATION_THRESHOLD_MS", 1000)
    tags = tags or {}

    if not is_monitoring_enabled():
        yield
        return

    runtime = PerformanceMonitorRuntime(
        collector=get_metric_collector(),
        operation=operation,
        threshold_ms=threshold_ms,
        tags=tags,
    )
    start = time.perf_counter()
    try:
        yield
    finally:
        _record_duration(runtime, _duration_ms(start))
