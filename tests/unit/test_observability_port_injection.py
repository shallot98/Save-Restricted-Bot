"""
Narrow-port injection tests for the monitoring entry points.

覆盖报告 §5.2：`MessageWorkerService` 不再函数内 import
`src.infrastructure.monitoring.*`，而是通过 `src.core.interfaces` 的
`BusinessMetricsRecorder` / `ErrorTracker` 端口 + 组合根注入的 provider
取得实现。

另外钉住两条行为约定：
  1. 未装配时不崩、不上报，但也不再像原来那样 `except Exception: return`
     把一切吞掉——记录侧的失败必须留下日志；
  2. 实现自身抛异常时消息处理不受影响（指标不是关键路径），但会打 WARNING。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pytest

from src.application.services.message_worker_service import MessageWorkerService
from src.core.interfaces import BusinessMetricsRecorder, ErrorTracker


@dataclass
class FakeBusinessMetrics:
    """Minimal stand-in satisfying the BusinessMetricsRecorder port."""

    notes: List[Dict[str, Any]] = field(default_factory=list)
    forwards: List[Dict[str, Any]] = field(default_factory=list)

    def record_note_saved(
        self,
        *,
        success: bool,
        has_media: bool,
        error_type: Optional[str] = None,
    ) -> None:
        self.notes.append(
            {"success": success, "has_media": has_media, "error_type": error_type}
        )

    def record_forward(
        self,
        *,
        success: bool,
        preserve_source: bool,
        error_type: Optional[str] = None,
    ) -> None:
        self.forwards.append(
            {
                "success": success,
                "preserve_source": preserve_source,
                "error_type": error_type,
            }
        )


@dataclass
class FakeErrorTracker:
    """Minimal stand-in satisfying the ErrorTracker port."""

    tracked: List[Dict[str, Any]] = field(default_factory=list)

    def track_error(
        self,
        *,
        error: BaseException,
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        self.tracked.append({"error": error, "context": context or {}})
        return None


class ExplodingMetrics:
    def record_note_saved(self, **_kwargs: Any) -> None:
        raise RuntimeError("metrics backend down")

    def record_forward(self, **_kwargs: Any) -> None:
        raise RuntimeError("metrics backend down")


def _build_service(
    metrics: Any = None,
    tracker: Any = None,
    *,
    wire_metrics: bool = True,
    wire_tracker: bool = True,
) -> MessageWorkerService:
    return MessageWorkerService(
        None,  # type: ignore[arg-type]
        metrics_provider=(lambda: metrics) if wire_metrics else None,
        error_tracker_provider=(lambda: tracker) if wire_tracker else None,
    )


class TestPortConformance:
    def test_fakes_satisfy_ports(self) -> None:
        assert isinstance(FakeBusinessMetrics(), BusinessMetricsRecorder)
        assert isinstance(FakeErrorTracker(), ErrorTracker)


class TestBusinessMetricsInjection:
    def test_note_saved_goes_through_injected_recorder(self) -> None:
        metrics = FakeBusinessMetrics()
        service = _build_service(metrics=metrics)

        service.record_note_saved(success=True, has_media=False)

        assert metrics.notes == [
            {"success": True, "has_media": False, "error_type": None}
        ]

    def test_forward_goes_through_injected_recorder(self) -> None:
        metrics = FakeBusinessMetrics()
        service = _build_service(metrics=metrics)

        service.record_forward(success=False, preserve_source=True, error_type="FloodWait")

        assert metrics.forwards == [
            {"success": False, "preserve_source": True, "error_type": "FloodWait"}
        ]

    def test_unwired_provider_is_a_no_op(self) -> None:
        service = _build_service(wire_metrics=False)

        service.record_note_saved(success=True, has_media=True)  # must not raise

    def test_recorder_failure_is_logged_not_swallowed(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        service = _build_service(metrics=ExplodingMetrics())

        with caplog.at_level("WARNING"):
            service.record_note_saved(success=True, has_media=False)

        assert "Failed to record note_saved metric" in caplog.text


class TestErrorTrackerInjection:
    def test_processing_error_goes_through_injected_tracker(self) -> None:
        tracker = FakeErrorTracker()
        service = _build_service(tracker=tracker)
        error = ValueError("boom")

        service.track_processing_error(
            error,
            user_id="1",
            source_chat_id="-100123",
            watch_key="task-1",
        )

        assert len(tracker.tracked) == 1
        assert tracker.tracked[0]["error"] is error
        assert tracker.tracked[0]["context"] == {
            "component": "message_worker",
            "stage": "process_message",
            "user_id": "1",
            "source_chat_id": "-100123",
            "watch_key": "task-1",
        }

    def test_unwired_provider_is_a_no_op(self) -> None:
        service = _build_service(wire_tracker=False)

        service.track_processing_error(  # must not raise
            ValueError("boom"),
            user_id="1",
            source_chat_id="-100123",
            watch_key="task-1",
        )

    def test_provider_failure_is_logged_not_swallowed(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        def broken_provider() -> Any:
            raise RuntimeError("tracker construction failed")

        service = MessageWorkerService(
            None,  # type: ignore[arg-type]
            error_tracker_provider=broken_provider,
        )

        with caplog.at_level("WARNING"):
            service.track_processing_error(
                ValueError("boom"),
                user_id="1",
                source_chat_id="-100123",
                watch_key="task-1",
            )

        assert "Error tracker provider failed" in caplog.text
