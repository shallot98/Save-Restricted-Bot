"""Metrics and error reporting helpers for auto-forward handling.

Every touch point with ``src.infrastructure.monitoring`` lives here, behind a
lazy import: the monitoring subsystem is optional and must never be able to
break message handling.
"""

from contextlib import nullcontext

from bot.utils.logger import get_logger

logger = get_logger(__name__)


def auto_forward_perf_context():
    """Time the enqueue step, degrading to a no-op when monitoring is absent."""
    try:
        from src.infrastructure.monitoring.performance.decorators import performance_context
    except Exception:
        return nullcontext()

    return performance_context("bot.auto_forward.enqueue", tags={"component": "auto_forward"})


def get_auto_forward_metrics():
    try:
        from src.infrastructure.monitoring.performance.business_metrics import get_business_metrics

        return get_business_metrics()
    except Exception:
        return None


def is_peer_lookup_error(error: Exception) -> bool:
    error_msg = str(error)
    return "Peer id invalid" in error_msg or "ID not found" in error_msg


def report_auto_forward_error(prefix: str, error: Exception) -> None:
    logger.error(f"{prefix}: {type(error).__name__}: {error}", exc_info=True)
    record_auto_forward_failure(error)
    track_auto_forward_error(error)


def record_auto_forward_failure(error: Exception) -> None:
    metrics = get_auto_forward_metrics()
    if metrics is None:
        return
    try:
        metrics.record_message_processed(
            success=False,
            category="auto_forward",
            error_type=type(error).__name__,
        )
    except Exception as metrics_err:
        logger.debug(f"业务指标上报失败（忽略，不影响主流程）: {metrics_err}")


def track_auto_forward_error(error: Exception) -> None:
    try:
        from src.infrastructure.monitoring.errors.tracker import get_error_tracker

        get_error_tracker().track_error(
            error=error,
            context={"component": "auto_forward", "error_kind": type(error).__name__},
        )
    except Exception as track_err:
        logger.debug(f"错误追踪上报失败（忽略，不影响主流程）: {track_err}")


def track_queue_full(context, msg_obj, candidate) -> None:
    try:
        from src.infrastructure.monitoring.errors.tracker import get_error_tracker

        get_error_tracker().track_error(
            error=RuntimeError("queue_full"),
            context={
                "component": "auto_forward",
                "error_kind": "queue_full",
                "source_chat_id": msg_obj.source_chat_id,
                "message_id": msg_obj.message_id,
                "queue_size": context.message_queue.qsize(),
                "queue_maxsize": context.message_queue.maxsize,
                "user_id": str(candidate.user_id),
            },
        )
    except Exception as track_err:
        logger.debug(f"队列满载错误追踪上报失败（忽略，不影响主流程）: {track_err}")
