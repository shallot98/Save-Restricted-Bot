"""Auto-forward message processing pipeline (orchestration only).

Validates an incoming Telegram message, matches it against the watch tasks of
its source chat, and fans it out into the worker queue.

All "already handled" bookkeeping — dedup marks, media-group registry, cursor
gaps, the durable catch-up cursor and the :class:`MessageProgress` contract
read by ``WatchCatchupScanner`` — belongs to
``bot/handlers/auto_forward_progress.py``. ``MessageProgress`` and
``EnqueueOutcome`` are re-exported here as part of this pipeline's published
return contract.
"""

import queue
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from bot.services.pt_pay_manager import get_pt_pay_monitor_manager
from bot.handlers.auto_forward_progress import (
    EnqueueOutcome,
    MessageProgress,
    finalize_message_progress,
    is_media_group_already_handled,
    is_recently_processed,
    mark_message_handled,
    register_media_group,
)
from bot.handlers.auto_forward_reporting import (
    auto_forward_perf_context,
    get_auto_forward_metrics,
    is_peer_lookup_error,
    report_auto_forward_error,
    track_queue_full,
)
from bot.utils.logger import get_logger
from bot.workers import Message

if TYPE_CHECKING:
    from src.application.services import WatchService

logger = get_logger(__name__)

__all__ = ["EnqueueOutcome", "MessageProgress", "process_auto_forward_message"]


@dataclass(frozen=True, kw_only=True)
class AutoForwardContext:
    message: object
    message_queue: object
    metrics: Optional[object]
    watch_service: object


@dataclass(frozen=True, kw_only=True)
class SourceContext:
    watch_service: object
    source_chat_id: str
    message_text: str


@dataclass(frozen=True, kw_only=True)
class TaskCandidate:
    user_id: object
    watch_key: str
    watch_data: dict
    dest_chat_id: object
    record_mode: bool


def process_auto_forward_message(
    message,
    message_queue,
    *,
    watch_service: "WatchService",
) -> MessageProgress:
    """Validate, match, and enqueue a monitored Telegram message.

    Returns the progress made, so that callers driving a durable cursor (the
    catch-up scanner) can tell «handled» from «dropped». Failures resolve to
    ``BLOCKED``: an unhandled message must stay behind the cursor.

    ``watch_service`` 由调用方传入（自动转发 handler 的闭包 / catch-up 扫描器），
    本模块不再从组合根就地取服务。
    """
    context = AutoForwardContext(
        message=message,
        message_queue=message_queue,
        metrics=get_auto_forward_metrics(),
        watch_service=watch_service,
    )

    try:
        return _process_auto_forward_context(context)
    except (ValueError, KeyError) as e:
        if not is_peer_lookup_error(e):
            report_auto_forward_error("⚠️ auto_forward 错误", e)
        return MessageProgress.BLOCKED
    except Exception as e:
        report_auto_forward_error("⚠️ auto_forward 意外错误", e)
        return MessageProgress.BLOCKED


def _process_auto_forward_context(context: AutoForwardContext) -> MessageProgress:
    message = context.message
    logger.info(
        f"🔔 收到消息: chat_id={message.chat.id if message and message.chat else 'Unknown'}, "
        f"message_id={message.id if message else 'Unknown'}"
    )

    if not _is_valid_message(message):
        return MessageProgress.SKIPPED
    if is_recently_processed(message):
        return MessageProgress.SKIPPED

    _log_message_direction(message)
    _dispatch_pt_monitor(message)
    source_context = _load_source_context(message, context.watch_service)
    if source_context is None:
        # 非监控源：没有待入队的工作，可以直接标记已处理（无 catch-up 游标）。
        mark_message_handled(message)
        return MessageProgress.SKIPPED

    outcome = _enqueue_tasks_with_monitoring(context, source_context)
    return finalize_message_progress(message, source_context.source_chat_id, outcome)


def _is_valid_message(message) -> bool:
    if not message or not hasattr(message, "chat") or not message.chat:
        logger.debug("跳过：消息对象无效或缺少 chat 属性")
        return False
    if not hasattr(message.chat, "id") or message.chat.id is None:
        logger.debug("跳过：消息缺少有效的 chat ID")
        return False
    if not hasattr(message, "id") or message.id is None:
        logger.debug("跳过：消息缺少有效的 message ID")
        return False
    return True


def _log_message_direction(message) -> None:
    if message.outgoing:
        logger.debug(f"📤 outgoing消息（由Bot转发）: chat_id={message.chat.id}, message_id={message.id}")
    else:
        logger.debug(f"📥 incoming消息（外部来源）: chat_id={message.chat.id}, message_id={message.id}")


def _dispatch_pt_monitor(message) -> None:
    try:
        get_pt_pay_monitor_manager().dispatch_message(message)
    except Exception as pt_err:
        logger.error(f"❌ PT 联动脚本分发失败: {type(pt_err).__name__}: {pt_err}", exc_info=True)


def _load_source_context(message, watch_service) -> Optional[SourceContext]:
    source_chat_id = str(message.chat.id)
    monitored_sources = watch_service.get_monitored_sources()
    if source_chat_id not in monitored_sources:
        logger.debug(f"⏭️ 消息来自非监控源，已跳过: chat_id={source_chat_id}, message_id={message.id}")
        logger.debug(f"   当前监控源列表: {monitored_sources if monitored_sources else '空'}")
        return None

    logger.info(f"🔔 监控源消息: chat_id={source_chat_id}, message_id={message.id}")
    return SourceContext(
        watch_service=watch_service,
        source_chat_id=source_chat_id,
        message_text=message.text or message.caption or "",
    )


def _enqueue_tasks_with_monitoring(
    context: AutoForwardContext,
    source_context: SourceContext,
) -> EnqueueOutcome:
    with auto_forward_perf_context():
        outcome = _enqueue_matching_tasks(context, source_context)

    if outcome.enqueued > 0:
        logger.info(f"✅ 本次共入队 {outcome.enqueued} 条消息")
        if context.metrics is not None:
            context.metrics.record_message_processed(success=True, category="auto_forward", error_type=None)
    return outcome


def _enqueue_matching_tasks(context: AutoForwardContext, source_context: SourceContext) -> EnqueueOutcome:
    enqueued_count = 0
    dropped_count = 0
    tasks_for_source = source_context.watch_service.get_tasks_for_source(source_context.source_chat_id)
    for entry in tasks_for_source:
        candidate = _build_task_candidate(entry, source_context.source_chat_id)
        if candidate is None:
            continue

        media_group_key = _build_media_group_key(context, candidate)
        if is_media_group_already_handled(media_group_key):
            continue

        msg_obj = _build_worker_message(context, source_context, candidate)
        if not _enqueue_worker_message(context, msg_obj, candidate):
            dropped_count += 1
            continue

        # 入队成功后才登记媒体组，丢弃时保持未登记以便补扫重投。
        register_media_group(media_group_key)
        enqueued_count += 1

    return EnqueueOutcome(enqueued=enqueued_count, dropped=dropped_count)


def _build_task_candidate(entry, source_chat_id: str) -> Optional[TaskCandidate]:
    if len(entry) == 3:
        user_id, watch_key, task = entry
    else:
        user_id, task = entry
        watch_key = source_chat_id

    watch_data = _task_to_watch_data(task)
    if watch_data is None:
        return None

    record_mode = bool(watch_data.get("record_mode", False))
    dest_chat_id = None if record_mode else watch_data.get("dest")
    logger.info(f"✅ 匹配到监控任务: user={user_id}, source={source_chat_id}")
    return TaskCandidate(
        user_id=user_id,
        watch_key=watch_key,
        watch_data=watch_data,
        dest_chat_id=dest_chat_id,
        record_mode=record_mode,
    )


def _task_to_watch_data(task) -> Optional[dict]:
    if hasattr(task, "to_dict"):
        return task.to_dict()
    if isinstance(task, dict):
        return task
    return None


def _build_media_group_key(context: AutoForwardContext, candidate: TaskCandidate) -> Optional[str]:
    media_group_id = context.message.media_group_id
    if not media_group_id:
        return None

    mode_suffix = "record" if candidate.record_mode else "forward"
    return f"{candidate.user_id}_{candidate.watch_key}_{candidate.dest_chat_id}_{mode_suffix}_{media_group_id}"


def _build_worker_message(
    context: AutoForwardContext,
    source_context: SourceContext,
    candidate: TaskCandidate,
) -> Message:
    media_group_id = context.message.media_group_id
    return Message(
        user_id=candidate.user_id,
        watch_key=candidate.watch_key,
        source_chat_id=source_context.source_chat_id,
        message_id=context.message.id,
        watch_data=candidate.watch_data,
        dest_chat_id=candidate.dest_chat_id,
        message_text=source_context.message_text,
        message=None,
        media_group_key=f"{candidate.user_id}_{candidate.watch_key}_{media_group_id}" if media_group_id else None,
    )


def _enqueue_worker_message(context: AutoForwardContext, msg_obj: Message, candidate: TaskCandidate) -> bool:
    try:
        context.message_queue.put_nowait(msg_obj)
    except queue.Full:
        _handle_queue_full(context, msg_obj, candidate)
        return False

    logger.info(
        f"📬 消息已入队: user={candidate.user_id}, "
        f"source={msg_obj.source_chat_id}, 队列大小={context.message_queue.qsize()}"
    )
    return True


def _handle_queue_full(context: AutoForwardContext, msg_obj: Message, candidate: TaskCandidate) -> None:
    logger.warning(
        f"🚨 队列已满，丢弃消息: user={candidate.user_id}, "
        f"source={msg_obj.source_chat_id}, message_id={msg_obj.message_id}"
    )
    if context.metrics is not None:
        context.metrics.record_message_processed(
            success=False,
            category="auto_forward",
            error_type="queue_full",
        )
    track_queue_full(context, msg_obj, candidate)
