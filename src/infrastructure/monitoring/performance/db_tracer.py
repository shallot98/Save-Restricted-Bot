"""
数据库查询追踪（SQLite）

提供查询耗时监控与慢查询检测。通过 enable(conn) 返回连接包装器，
拦截 cursor.execute/executemany 并记录指标。
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from typing import Any, Dict, Iterable, Optional, Tuple

from src.infrastructure.monitoring import get_metric_collector, is_monitoring_enabled
from src.infrastructure.monitoring.core.metrics import DatabaseMetric, MetricType

logger = logging.getLogger(__name__)

_db_tracer: Optional["DatabaseTracer"] = None


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


def _classify_query(query: str) -> str:
    head = query.strip().split(None, 1)
    if not head:
        return "unknown"
    return head[0].lower()


def _try_send_alert(level: str, title: str, message: str, details: Dict[str, Any]) -> None:
    try:
        from src.infrastructure.monitoring.alerting.alert_manager import get_alert_manager  # noqa: WPS433

        alert_manager = get_alert_manager()
        alert_manager.send_alert(level=level, title=title, message=message, details=details)
    except Exception:
        return


class DatabaseTracer:
    """SQLite 查询追踪器"""

    def __init__(
        self,
        *,
        enabled: bool = True,
        slow_threshold_ms: Optional[int] = None,
        log_query: Optional[bool] = None,
        alert_enabled: Optional[bool] = None,
    ) -> None:
        self._enabled = enabled
        self._slow_threshold_ms = slow_threshold_ms if slow_threshold_ms is not None else _env_int("SLOW_QUERY_THRESHOLD_MS", 100)
        self._log_query = log_query if log_query is not None else _env_bool("SLOW_QUERY_LOG_QUERY", True)
        self._alert_enabled = alert_enabled if alert_enabled is not None else _env_bool("SLOW_QUERY_ALERT_ENABLED", True)
        self._collector = get_metric_collector()

    @property
    def enabled(self) -> bool:
        return self._enabled and is_monitoring_enabled() and _env_bool("DB_MONITORING_ENABLED", True)

    @property
    def slow_threshold_ms(self) -> int:
        return self._slow_threshold_ms

    def enable(self, conn: Any) -> Any:
        """返回连接包装器（不影响原有提交/回滚/关闭语义）"""
        if not self.enabled:
            return conn
        return _TracedConnection(conn, tracer=self)

    @contextmanager
    def trace_query(self, query: str, params: Optional[Tuple[Any, ...]] = None):
        """
        手动追踪查询（用于无法使用 enable(conn) 的场景）

        用法：
            with tracer.trace_query(sql, params):
                cursor.execute(sql, params)
        """
        if not self.enabled:
            yield
            return

        start = time.perf_counter()
        try:
            yield
        finally:
            duration_ms = (time.perf_counter() - start) * 1000.0
            self._record(query=query, duration_ms=duration_ms, rows_affected=0)

    def _record(self, *, query: str, duration_ms: float, rows_affected: int) -> None:
        query_type = _classify_query(query)
        is_slow = duration_ms >= self._slow_threshold_ms

        metric = DatabaseMetric(
            name="db.query.duration_ms",
            value=duration_ms,
            metric_type=MetricType.TIMER,
            query=query,
            duration_ms=duration_ms,
            rows_affected=rows_affected,
            is_slow=is_slow,
            tags={"query_type": query_type, "is_slow": str(is_slow).lower()},
        )
        self._collector.collect(metric)

        if not is_slow:
            return

        if self._log_query:
            logger.warning("慢查询: %.2fms >= %dms (%s) SQL=%s", duration_ms, self._slow_threshold_ms, query_type, query)
        else:
            logger.warning("慢查询: %.2fms >= %dms (%s)", duration_ms, self._slow_threshold_ms, query_type)

        if self._alert_enabled:
            _try_send_alert(
                level="warning",
                title="慢查询检测",
                message=f"查询耗时 {duration_ms:.2f}ms (>= {self._slow_threshold_ms}ms)",
                details={"query_type": query_type, "duration_ms": duration_ms, "threshold_ms": self._slow_threshold_ms, "query": query},
            )


class _TracedCursor:
    def __init__(self, cursor: Any, *, tracer: DatabaseTracer) -> None:
        self._cursor = cursor
        self._tracer = tracer

    def execute(self, query: str, params: Any = None):  # type: ignore[no-untyped-def]
        start = time.perf_counter()
        try:
            if params is None:
                return self._cursor.execute(query)
            return self._cursor.execute(query, params)
        finally:
            duration_ms = (time.perf_counter() - start) * 1000.0
            rows_affected = int(getattr(self._cursor, "rowcount", 0) or 0)
            self._tracer._record(query=query, duration_ms=duration_ms, rows_affected=rows_affected)

    def executemany(self, query: str, seq_of_params: Iterable[Any]):  # type: ignore[no-untyped-def]
        start = time.perf_counter()
        try:
            return self._cursor.executemany(query, seq_of_params)
        finally:
            duration_ms = (time.perf_counter() - start) * 1000.0
            rows_affected = int(getattr(self._cursor, "rowcount", 0) or 0)
            self._tracer._record(query=query, duration_ms=duration_ms, rows_affected=rows_affected)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)


class _TracedConnection:
    def __init__(self, conn: Any, *, tracer: DatabaseTracer) -> None:
        self._conn = conn
        self._tracer = tracer

    def cursor(self, *args: Any, **kwargs: Any) -> Any:
        return _TracedCursor(self._conn.cursor(*args, **kwargs), tracer=self._tracer)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)


def get_db_tracer() -> DatabaseTracer:
    global _db_tracer
    if _db_tracer is None:
        _db_tracer = DatabaseTracer()
    return _db_tracer

