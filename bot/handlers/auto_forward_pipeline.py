"""Auto-forward message processing pipeline."""

import queue
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Optional

from bot.services.pt_pay_manager import get_pt_pay_monitor_manager
from bot.handlers.auto_forward_reporting import (
    get_auto_forward_metrics,
    is_peer_lookup_error,
    report_auto_forward_error,
    track_queue_full,
)
from bot.utils import cleanup_old_messages, is_message_processed, mark_message_processed
from bot.utils.dedup import is_media_group_processed, processed_messages, register_processed_media_group
from bot.utils.logger import get_logger
from bot.workers import Message
from constants import MESSAGE_CACHE_CLEANUP_THRESHOLD
from src.core.container import get_watch_service

logger = get_logger(__name__)


@dataclass(frozen=True, kw_only=True)
class AutoForwardContext:
    message: object
    message_queue: object
    metrics: Optional[object]


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


def process_auto_forward_message(message, message_queue) -> None:
    """Validate, match, and enqueue a monitored Telegram message."""
    context = AutoForwardContext(
        message=message,
        message_queue=message_queue,
        metrics=get_auto_forward_metrics(),
    )

    try:
        _process_auto_forward_context(context)
    except (ValueError, KeyError) as e:
        if not is_peer_lookup_error(e):
            report_auto_forward_error("⚠️ auto_forward 错误", e)
    except Exception as e:
        report_auto_forward_error("⚠️ auto_forward 意外错误", e)


def _process_auto_forward_context(context: AutoForwardContext) -> None:
    message = context.message
    logger.info(
        f"🔔 收到消息: chat_id={message.chat.id if message and message.chat else 'Unknown'}, "
        f"message_id={message.id if message else 'Unknown'}"
    )

    if not _is_valid_message(message):
        return
    if _is_duplicate_message(message):
        return

    _log_message_direction(message)
    _dispatch_pt_monitor(message)
    source_context = _load_source_context(message)
    if source_context is None:
        return

    _enqueue_tasks_with_monitoring(context, source_context)


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


def _is_duplicate_message(message) -> bool:
    if is_message_processed(message.id, message.chat.id):
        logger.debug(f"⏭️ 跳过已处理的消息: chat_id={message.chat.id}, message_id={message.id}")
        return True

    mark_message_processed(message.id, message.chat.id)
    if len(processed_messages) > MESSAGE_CACHE_CLEANUP_THRESHOLD:
        cleanup_old_messages()
    return False


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


def _load_source_context(message) -> Optional[SourceContext]:
    source_chat_id = str(message.chat.id)
    watch_service = get_watch_service()
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


def _enqueue_tasks_with_monitoring(context: AutoForwardContext, source_context: SourceContext) -> None:
    with _auto_forward_perf_context():
        enqueued_count = _enqueue_matching_tasks(context, source_context)

    if enqueued_count > 0:
        logger.info(f"✅ 本次共入队 {enqueued_count} 条消息")
        if context.metrics is not None:
            context.metrics.record_message_processed(success=True, category="auto_forward", error_type=None)


def _auto_forward_perf_context():
    try:
        from src.infrastructure.monitoring.performance.decorators import performance_context
    except Exception:
        return nullcontext()

    return performance_context("bot.auto_forward.enqueue", tags={"component": "auto_forward"})


def _enqueue_matching_tasks(context: AutoForwardContext, source_context: SourceContext) -> int:
    enqueued_count = 0
    tasks_for_source = source_context.watch_service.get_tasks_for_source(source_context.source_chat_id)
    for entry in tasks_for_source:
        candidate = _build_task_candidate(entry, source_context.source_chat_id)
        if candidate is None:
            continue
        if _should_skip_media_group(context, candidate):
            continue

        msg_obj = _build_worker_message(context, source_context, candidate)
        if _enqueue_worker_message(context, msg_obj, candidate):
            enqueued_count += 1

    return enqueued_count


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


def _should_skip_media_group(context: AutoForwardContext, candidate: TaskCandidate) -> bool:
    media_group_id = context.message.media_group_id
    if not media_group_id:
        return False

    mode_suffix = "record" if candidate.record_mode else "forward"
    media_group_key = (
        f"{candidate.user_id}_{candidate.watch_key}_{candidate.dest_chat_id}_{mode_suffix}_{media_group_id}"
    )
    if is_media_group_processed(media_group_key):
        logger.debug(f"⏭️ 跳过已处理的媒体组: {media_group_key}")
        return True

    register_processed_media_group(media_group_key)
    logger.info(f"📸 首次处理媒体组: {media_group_key}")
    return False


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
