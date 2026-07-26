"""Progress bookkeeping for auto-forwarded messages (catch-up cursor contract).

Ownership split with ``bot/handlers/auto_forward_pipeline.py``:

* the pipeline *orchestrates* — validate, match watch tasks, enqueue;
* this module *decides what counts as progress* — it owns every "already
  handled" marker (dedup cache, media-group registry, per-source gap table,
  durable catch-up cursor), so that the rule «a marker may only advance after
  the work actually succeeded» is enforced in one place.

The public contract consumed outside this package is :class:`MessageProgress`.
``WatchCatchupScanner`` reads it duck-typed via ``cursor_may_advance`` and must
never move the durable cursor past a message the pipeline refused to (or could
not) handle — a silently advanced cursor means the dropped message is lost
forever. Keeping that invariant in one module is the point of the split.
"""

import threading
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from bot.utils import cleanup_old_messages, is_message_processed, mark_message_processed
from bot.utils.dedup import (
    is_media_group_processed,
    processed_messages,
    register_processed_media_group,
)
from bot.utils.logger import get_logger
from constants import MESSAGE_CACHE_CLEANUP_THRESHOLD

logger = get_logger(__name__)


@dataclass(frozen=True, kw_only=True)
class EnqueueOutcome:
    """Result of enqueueing one Telegram message into the worker queue."""

    enqueued: int
    dropped: int


class MessageProgress(Enum):
    """How far one message got, from the catch-up cursor's point of view.

    This is the narrow contract consumed by ``WatchCatchupScanner``: the scanner
    must never move the durable cursor past a message that this pipeline refused
    to (or could not) handle, otherwise the dropped message is lost forever.
    """

    ENQUEUED = "enqueued"  # 全部匹配任务入队成功，游标已由本模块推进
    SKIPPED = "skipped"  # 无需入队（消息无效 / 已处理过 / 非监控源）
    BLOCKED = "blocked"  # 有任务被丢弃，或存在更早的未补回消息 → 游标不得推进

    @property
    def cursor_may_advance(self) -> bool:
        return self is not MessageProgress.BLOCKED


# Lowest message_id per source that failed to enqueue and is still unresolved.
# The catch-up cursor must never move past such a gap, otherwise the dropped
# message can never be re-scanned.
_cursor_gaps: dict[str, int] = {}
_cursor_gaps_lock = threading.Lock()


def finalize_message_progress(
    message,
    source_chat_id: str,
    outcome: EnqueueOutcome,
) -> MessageProgress:
    """Advance 'already handled' markers only after enqueue actually succeeded."""
    if outcome.dropped > 0:
        logger.warning(
            "⛔ 有 %s 个任务入队失败，不推进去重标记与 catch-up 游标，等待补扫重投: source=%s message_id=%s",
            outcome.dropped,
            source_chat_id,
            message.id,
        )
        record_cursor_gap(source_chat_id, message.id)
        return MessageProgress.BLOCKED

    mark_message_handled(message)
    if not advance_catchup_cursor(source_chat_id, message.id):
        # 本条消息处理成功，但更早的丢弃消息尚未补回，游标仍需停在原地。
        return MessageProgress.BLOCKED
    return MessageProgress.ENQUEUED


def is_recently_processed(message) -> bool:
    """Check the dedup cache without marking; marking happens after enqueue."""
    if is_message_processed(message.id, message.chat.id):
        logger.debug(f"⏭️ 跳过已处理的消息: chat_id={message.chat.id}, message_id={message.id}")
        return True
    return False


def mark_message_handled(message) -> None:
    mark_message_processed(message.id, message.chat.id)
    if len(processed_messages) > MESSAGE_CACHE_CLEANUP_THRESHOLD:
        cleanup_old_messages()


def is_media_group_already_handled(media_group_key: Optional[str]) -> bool:
    if not media_group_key:
        return False
    if is_media_group_processed(media_group_key):
        logger.debug(f"⏭️ 跳过已处理的媒体组: {media_group_key}")
        return True
    return False


def register_media_group(media_group_key: Optional[str]) -> None:
    """Register only after a successful enqueue, so drops can be re-scanned."""
    if not media_group_key:
        return
    register_processed_media_group(media_group_key)
    logger.info(f"📸 首次处理媒体组: {media_group_key}")


def record_cursor_gap(source_chat_id: str, message_id: int) -> None:
    """Remember the lowest message_id that was dropped and must be re-scanned."""
    with _cursor_gaps_lock:
        current = _cursor_gaps.get(source_chat_id)
        if current is None or message_id < current:
            _cursor_gaps[source_chat_id] = message_id


def cursor_may_advance(source_chat_id: str, message_id: int) -> bool:
    """Allow advancing only up to the oldest unresolved dropped message."""
    with _cursor_gaps_lock:
        gap = _cursor_gaps.get(source_chat_id)
        if gap is None or message_id < gap:
            return True
        if message_id == gap:
            del _cursor_gaps[source_chat_id]
            return True
        return False


def advance_catchup_cursor(source_chat_id: str, message_id: int) -> bool:
    """Advance durable catch-up high-water mark; report whether it actually moved."""
    if not cursor_may_advance(source_chat_id, message_id):
        logger.warning(
            "⏸️ catch-up 游标暂不推进（存在更早的未补扫丢弃消息）: source=%s message_id=%s",
            source_chat_id,
            message_id,
        )
        return False

    try:
        from bot.services.watch_catchup_store import advance_cursor

        advance_cursor(source_chat_id, message_id)
    except Exception as exc:
        logger.warning(
            "⚠️ catch-up 游标推进失败（消息将在下次补扫时重投）: source=%s message_id=%s err=%s",
            source_chat_id,
            message_id,
            exc,
        )
        return False
    return True
