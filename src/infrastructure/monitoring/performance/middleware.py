"""
Flask 性能监控中间件

自动监控所有 HTTP 请求响应时间，并在响应头中写入：
- X-Response-Time: ms
- X-Request-ID: request id
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Optional

from flask import Flask, g, request

from src.infrastructure.monitoring import get_metric_collector, is_monitoring_enabled
from src.infrastructure.monitoring.core.metrics import MetricType, PerformanceMetric

logger = logging.getLogger(__name__)


def _env_int(key: str, default: int) -> int:
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


class PerformanceMiddleware:
    """Flask 请求性能监控"""

    def __init__(self, app: Flask, *, threshold_ms: Optional[int] = None) -> None:
        self._app = app
        self._threshold_ms = threshold_ms if threshold_ms is not None else _env_int("SLOW_API_THRESHOLD_MS", 1000)
        self._collector = get_metric_collector()
        self._register()

    def _register(self) -> None:
        @self._app.before_request
        def _before_request() -> None:
            if not is_monitoring_enabled():
                return
            g._perf_start = time.perf_counter()
            incoming_request_id = request.headers.get("X-Request-ID")
            g.request_id = incoming_request_id or uuid.uuid4().hex
            g._perf_recorded = False

        @self._app.after_request
        def _after_request(response):  # type: ignore[no-untyped-def]
            if not is_monitoring_enabled():
                return response

            start = getattr(g, "_perf_start", None)
            if start is None:
                return response

            duration_ms = (time.perf_counter() - start) * 1000.0
            request_id = getattr(g, "request_id", uuid.uuid4().hex)

            response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
            response.headers["X-Request-ID"] = request_id

            metric = PerformanceMetric(
                name="api.response_time_ms",
                value=duration_ms,
                metric_type=MetricType.TIMER,
                duration_ms=duration_ms,
                endpoint=request.path,
                method=request.method,
                status_code=response.status_code,
                tags={
                    "endpoint": request.path,
                    "method": request.method,
                    "status_code": str(response.status_code),
                },
                metadata={"request_id": request_id},
            )
            self._collector.collect(metric)
            g._perf_recorded = True

            if duration_ms >= self._threshold_ms:
                logger.warning(
                    "慢请求: %s %s (%d) %.2fms >= %dms (request_id=%s)",
                    request.method,
                    request.path,
                    response.status_code,
                    duration_ms,
                    self._threshold_ms,
                    request_id,
                )

            return response

        @self._app.teardown_request
        def _teardown_request(exc):  # type: ignore[no-untyped-def]
            if not is_monitoring_enabled():
                return
            if getattr(g, "_perf_recorded", False):
                return
            start = getattr(g, "_perf_start", None)
            if start is None:
                return
            duration_ms = (time.perf_counter() - start) * 1000.0
            request_id = getattr(g, "request_id", uuid.uuid4().hex)
            status_code = 500 if exc else 200

            metric = PerformanceMetric(
                name="api.response_time_ms",
                value=duration_ms,
                metric_type=MetricType.TIMER,
                duration_ms=duration_ms,
                endpoint=request.path if request else None,
                method=request.method if request else None,
                status_code=status_code,
                tags={
                    "endpoint": request.path if request else "unknown",
                    "method": request.method if request else "unknown",
                    "status_code": str(status_code),
                },
                metadata={"request_id": request_id, "exception": str(exc) if exc else None},
            )
            self._collector.collect(metric)

            if exc is not None:
                try:
                    from src.infrastructure.monitoring.errors.tracker import get_error_tracker

                    get_error_tracker().track_error(
                        error=exc,
                        context={
                            "component": "flask",
                            "endpoint": request.path if request else "unknown",
                            "method": request.method if request else "unknown",
                            "request_id": request_id,
                        },
                    )
                except Exception as e:
                    logger.debug("错误追踪上报失败，已忽略: %s", e, exc_info=True)
