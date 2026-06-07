"""Retry and progress helpers for Telegram history copy."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from bot.utils.logger import get_logger
from .history_copy_models import HistoryCopyFatalError, HistoryCopyStats
from .history_copy_utils import is_fatal_error

try:
    from pyrogram.errors import FloodWait
except ModuleNotFoundError:  # pragma: no cover - used only when runtime deps are absent
    class FloodWait(Exception):
        """Fallback FloodWait stub for local tests without pyrogram installed."""

        def __init__(self, value: int = 0) -> None:
            super().__init__(value)
            self.value = value


logger = get_logger(__name__)


@dataclass(frozen=True)
class HistoryCopyOperationContext:
    name: str
    is_outbound: bool
    success_units: int
    skip_failure_record: Callable[[Exception], bool] | None


@dataclass(frozen=True)
class HistoryCopyFloodWaitContext:
    operation: HistoryCopyOperationContext
    wait_seconds: int
    attempt_number: int
    has_retry: bool


class HistoryCopyRetryMixin:
    def _execute_with_retry(
        self,
        operation_name: str,
        operation: Callable[[], Any],
        *,
        is_outbound: bool = False,
        success_units: int = 1,
        skip_failure_record: Callable[[Exception], bool] | None = None,
    ):
        context = HistoryCopyOperationContext(
            operation_name,
            is_outbound,
            success_units,
            skip_failure_record,
        )
        for attempt in range(self._settings.max_flood_retries):
            if context.is_outbound:
                self._risk_controller.wait_for_outbound_slot(context.name, context.success_units)
            try:
                result = operation()
            except FloodWait as exc:
                if not self._retry_after_flood_wait(context, exc, attempt):
                    raise
                continue
            except Exception as exc:
                self._record_outbound_failure(context, exc)
                raise
            self._record_outbound_success(context)
            return result
        raise RuntimeError(f"{operation_name} reached an unexpected retry state")

    def _retry_after_flood_wait(self, context, exc, attempt):
        wait_seconds = max(int(getattr(exc, "value", 0) or 0), 1)
        has_retry = attempt + 1 < self._settings.max_flood_retries
        self._handle_flood_wait(
            HistoryCopyFloodWaitContext(context, wait_seconds, attempt + 1, has_retry)
        )
        return has_retry

    def _record_outbound_failure(self, context, exc: Exception) -> None:
        if not context.is_outbound:
            return
        if self._should_skip_failure_record(exc, context.skip_failure_record):
            return
        self._risk_controller.record_failure(context.name, exc)

    def _record_outbound_success(self, context):
        if context.is_outbound:
            self._risk_controller.record_success(context.name, context.success_units)

    @staticmethod
    def _should_skip_failure_record(
        exc: Exception,
        predicate: Callable[[Exception], bool] | None,
    ) -> bool:
        if predicate is None:
            return False
        return predicate(exc)

    @staticmethod
    def _skip_failure_record(_exc: Exception) -> bool:
        return True

    def _handle_flood_wait(self, context: HistoryCopyFloodWaitContext) -> None:
        if context.operation.is_outbound:
            self._risk_controller.record_flood_wait(context.operation.name, context.wait_seconds)
            return
        if not context.has_retry:
            return
        logger.warning(
            "⏳ %s 遇到 FloodWait，等待 %s 秒后重试 (%s/%s)",
            context.operation.name,
            context.wait_seconds + 1,
            context.attempt_number,
            self._settings.max_flood_retries,
        )
        time.sleep(context.wait_seconds + 1)

    def _raise_if_fatal(self, exc: Exception, message_id: int) -> None:
        if not is_fatal_error(exc):
            return
        raise HistoryCopyFatalError(
            f"复制过程中遇到致命错误，message_id={message_id}: {type(exc).__name__}: {exc}"
        ) from exc

    def _report_progress(self, stats: HistoryCopyStats) -> None:
        if self._progress_callback is None:
            return
        self._progress_callback(stats)
