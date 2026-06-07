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
from dataclasses import dataclass
from typing import Optional

from flask import Flask, g, request

from src.infrastructure.monitoring import get_metric_collector, is_monitoring_enabled
from src.infrastructure.monitoring.core.metrics import MetricType, PerformanceMetric

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RequestMetricData:
    duration_ms: float
    request_id: str
    status_code: int
    endpoint: Optional[str]
    method: Optional[str]
    tag_endpoint: str
    tag_method: str
    exception: Optional[str] = None


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
        self._app.before_request(self._before_request)
        self._app.after_request(self._after_request)
        self._app.teardown_request(self._teardown_request)

    def _before_request(self) -> None:
        if not is_monitoring_enabled():
            return
        g._perf_start = time.perf_counter()
        incoming_request_id = request.headers.get("X-Request-ID")
        g.request_id = incoming_request_id or uuid.uuid4().hex
        g._perf_recorded = False

    def _after_request(self, response):  # type: ignore[no-untyped-def]
        if not is_monitoring_enabled():
            return response
        start = getattr(g, "_perf_start", None)
        if start is None:
            return response

        duration_ms = _duration_ms(start)
        request_id = getattr(g, "request_id", uuid.uuid4().hex)
        self._apply_response_headers(response, duration_ms, request_id)
        self._collect_metric(self._response_metric_data(duration_ms, request_id, response.status_code))
        g._perf_recorded = True
        self._log_slow_request(duration_ms, request_id, response.status_code)
        return response

    @staticmethod
    def _apply_response_headers(response, duration_ms: float, request_id: str) -> None:  # type: ignore[no-untyped-def]
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
        response.headers["X-Request-ID"] = request_id

    def _response_metric_data(
        self,
        duration_ms: float,
        request_id: str,
        status_code: int,
    ) -> RequestMetricData:
        return RequestMetricData(
            duration_ms=duration_ms,
            request_id=request_id,
            status_code=status_code,
            endpoint=request.path,
            method=request.method,
            tag_endpoint=request.path,
            tag_method=request.method,
        )

    def _collect_metric(self, data: RequestMetricData) -> None:
        self._collector.collect(_build_metric(data))

    def _log_slow_request(
        self,
        duration_ms: float,
        request_id: str,
        status_code: int,
    ) -> None:
        if duration_ms < self._threshold_ms:
            return
        logger.warning(
            "慢请求: %s %s (%d) %.2fms >= %dms (request_id=%s)",
            request.method,
            request.path,
            status_code,
            duration_ms,
            self._threshold_ms,
            request_id,
        )

    def _teardown_request(self, exc):  # type: ignore[no-untyped-def]
        if not self._should_record_teardown():
            return
        start = getattr(g, "_perf_start", None)
        if start is None:
            return

        duration_ms = _duration_ms(start)
        request_id = getattr(g, "request_id", uuid.uuid4().hex)
        status_code = 500 if exc else 200
        data = self._teardown_metric_data(duration_ms, request_id, status_code, exc=exc)
        self._collect_metric(data)
        self._track_teardown_error(exc, request_id)

    @staticmethod
    def _should_record_teardown() -> bool:
        if not is_monitoring_enabled():
            return False
        return not getattr(g, "_perf_recorded", False)

    def _teardown_metric_data(
        self,
        duration_ms: float,
        request_id: str,
        status_code: int,
        *,
        exc,
    ) -> RequestMetricData:
        endpoint = request.path if request else None
        method = request.method if request else None
        tag_endpoint = request.path if request else "unknown"
        tag_method = request.method if request else "unknown"
        return RequestMetricData(
            duration_ms=duration_ms,
            request_id=request_id,
            status_code=status_code,
            endpoint=endpoint,
            method=method,
            tag_endpoint=tag_endpoint,
            tag_method=tag_method,
            exception=str(exc) if exc else None,
        )

    def _track_teardown_error(self, exc, request_id: str) -> None:  # type: ignore[no-untyped-def]
        if exc is None:
            return
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


def _duration_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000.0


def _build_metric(data: RequestMetricData) -> PerformanceMetric:
    metadata = {"request_id": data.request_id}
    if data.exception is not None:
        metadata["exception"] = data.exception
    return PerformanceMetric(
        name="api.response_time_ms",
        value=data.duration_ms,
        metric_type=MetricType.TIMER,
        duration_ms=data.duration_ms,
        endpoint=data.endpoint,
        method=data.method,
        status_code=data.status_code,
        tags={
            "endpoint": data.tag_endpoint,
            "method": data.tag_method,
            "status_code": str(data.status_code),
        },
        metadata=metadata,
    )
