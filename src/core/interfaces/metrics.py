"""
Observability Ports
===================

Narrow ports for the two monitoring entry points `src.application` uses.

调用面只有三个方法（`record_note_saved` / `record_forward` / `track_error`），
实现是 `src/infrastructure/monitoring/performance/business_metrics.py` 与
`src/infrastructure/monitoring/errors/tracker.py`，由组合根
`composition/container.py` 以 provider 形式注入。

为什么保留而不是删除这条链路：monitoring 只停用了**持久化**
（`src/infrastructure/monitoring/__init__.py:is_metric_persistence_enabled`
默认 False），内存聚合仍然在跑，且 `web/__init__.py:99` 仍注册了
`/monitoring` 蓝图读取这些聚合值——不是死路径。
"""

from __future__ import annotations

from typing import (
    Any,
    Callable,
    Dict,
    Optional,
    Protocol,
    runtime_checkable,
)


@runtime_checkable
class BusinessMetricsRecorder(Protocol):
    """Port for business counters (in-memory aggregation)."""

    def record_note_saved(
        self,
        *,
        success: bool,
        has_media: bool,
        error_type: Optional[str] = None,
    ) -> None:
        """Count one note-save attempt."""
        ...

    def record_forward(
        self,
        *,
        success: bool,
        preserve_source: bool,
        error_type: Optional[str] = None,
    ) -> None:
        """Count one forward attempt."""
        ...


@runtime_checkable
class ErrorTracker(Protocol):
    """Port for structured error tracking."""

    def track_error(
        self,
        *,
        error: BaseException,
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Record an error together with its handling context."""
        ...


#: 组合根注入的惰性提供者：未装配时返回 None，调用方必须显式处理。
BusinessMetricsProvider = Callable[[], Optional[BusinessMetricsRecorder]]
ErrorTrackerProvider = Callable[[], Optional[ErrorTracker]]
