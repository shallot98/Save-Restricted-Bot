"""Telegram link forwarding handlers for direct bot messages."""

import time
from dataclasses import dataclass, field
from typing import Callable, Optional

import pyrogram
from pyrogram.errors import InviteHashExpired, UserAlreadyParticipant, UsernameNotOccupied

from bot.utils.logger import get_logger

logger = get_logger(__name__)
PrivateForwardFunc = Callable[[pyrogram.types.messages_and_media.message.Message, object, int], None]


@dataclass
class BulkForwardStats:
    total: int
    success_count: int = 0
    failed_ids: list[int] = field(default_factory=list)

    @property
    def failed_count(self) -> int:
        return len(self.failed_ids)


@dataclass(frozen=True, kw_only=True)
class LinkForwardContext:
    message: object
    bot: object
    acc: object
    metrics: object
    private_forward: PrivateForwardFunc


@dataclass(frozen=True, kw_only=True)
class ForwardOutcome:
    msgid: int
    status: str
    error: Optional[Exception] = None


def handle_telegram_link_input(context: LinkForwardContext) -> tuple[bool, Optional[str]]:
    """Handle Telegram invite and message links."""
    if _is_join_link(context.message.text):
        _handle_join_link(context)
        return True, "join_chat"

    if "https://t.me/" in context.message.text:
        _handle_bulk_forward_link(context)
        return True, "bulk_forward"

    return False, None


def _is_join_link(text: str) -> bool:
    return "https://t.me/+" in text or "https://t.me/joinchat/" in text


def _handle_join_link(context: LinkForwardContext) -> None:
    if context.acc is None:
        context.bot.send_message(
            context.message.chat.id,
            "**❌ 未设置 String Session**",
            reply_to_message_id=context.message.id,
        )
        return

    try:
        try:
            context.acc.join_chat(context.message.text)
        except Exception as e:
            context.bot.send_message(
                context.message.chat.id,
                f"**❌ 错误** : __{e}__",
                reply_to_message_id=context.message.id,
            )
            return
        context.bot.send_message(
            context.message.chat.id,
            "**✅ 已加入频道**",
            reply_to_message_id=context.message.id,
        )
    except UserAlreadyParticipant:
        context.bot.send_message(
            context.message.chat.id,
            "**✅ 已经加入该频道**",
            reply_to_message_id=context.message.id,
        )
    except InviteHashExpired:
        context.bot.send_message(
            context.message.chat.id,
            "**❌ 无效链接**",
            reply_to_message_id=context.message.id,
        )


def _handle_bulk_forward_link(context: LinkForwardContext) -> None:
    datas, from_id, to_id = _parse_message_range(context.message.text)
    stats = BulkForwardStats(total=to_id - from_id + 1)
    logger.info(f"📤 开始批量转发: 共 {stats.total} 条消息 (ID: {from_id}-{to_id})")

    for msgid in range(from_id, to_id + 1):
        outcome = _forward_single_link_message(context, datas, msgid)
        if outcome.status == "abort":
            return
        _record_forward_result(context, stats, outcome)
        time.sleep(1)

    _send_bulk_forward_summary(context, stats)


def _parse_message_range(text: str) -> tuple[list[str], int, int]:
    datas = text.split("/")
    temp = datas[-1].replace("?single", "").split("-")
    from_id = int(temp[0].strip())
    try:
        to_id = int(temp[1].strip())
    except Exception:
        to_id = from_id
    return datas, from_id, to_id


def _forward_single_link_message(
    context: LinkForwardContext,
    datas: list[str],
    msgid: int,
) -> ForwardOutcome:
    if "https://t.me/c/" in context.message.text:
        chatid = int("-100" + datas[4])
        return _forward_via_user_client(context, chatid, msgid)
    if "https://t.me/b/" in context.message.text:
        return _forward_via_user_client(context, datas[4], msgid)
    return _forward_public_message(context, datas[3], msgid)


def _forward_via_user_client(context: LinkForwardContext, chatid, msgid: int) -> ForwardOutcome:
    if context.acc is None:
        context.bot.send_message(
            context.message.chat.id,
            "**❌ 未设置 String Session**",
            reply_to_message_id=context.message.id,
        )
        return ForwardOutcome(msgid=msgid, status="abort")
    try:
        context.private_forward(context.message, chatid, msgid)
        return ForwardOutcome(msgid=msgid, status="success")
    except Exception as e:
        return ForwardOutcome(msgid=msgid, status="failed", error=e)


def _forward_public_message(context: LinkForwardContext, username: str, msgid: int) -> ForwardOutcome:
    try:
        msg = context.bot.get_messages(username, msgid)
    except UsernameNotOccupied:
        context.bot.send_message(
            context.message.chat.id,
            "**❌ 该用户名未被占用**",
            reply_to_message_id=context.message.id,
        )
        return ForwardOutcome(msgid=msgid, status="abort")

    try:
        _copy_public_message(context, msg)
        return ForwardOutcome(msgid=msgid, status="success")
    except Exception:
        return _forward_via_user_client(context, username, msgid)


def _copy_public_message(context: LinkForwardContext, msg) -> None:
    if "?single" not in context.message.text:
        context.bot.copy_message(context.message.chat.id, msg.chat.id, msg.id)
    else:
        context.bot.copy_media_group(context.message.chat.id, msg.chat.id, msg.id)


def _record_forward_result(context: LinkForwardContext, stats: BulkForwardStats, outcome: ForwardOutcome) -> None:
    if outcome.status == "success":
        stats.success_count += 1
        if context.metrics is not None:
            context.metrics.record_forward(success=True, preserve_source=False)
        logger.debug(f"✅ 消息 {outcome.msgid} 转发成功 ({stats.success_count}/{stats.total})")
        return

    stats.failed_ids.append(outcome.msgid)
    if context.metrics is not None and outcome.error is not None:
        context.metrics.record_forward(
            success=False,
            preserve_source=False,
            error_type=type(outcome.error).__name__,
        )
    logger.warning(f"⚠️ 消息 {outcome.msgid} 转发失败: {type(outcome.error).__name__}: {outcome.error}")


def _send_bulk_forward_summary(context: LinkForwardContext, stats: BulkForwardStats) -> None:
    if stats.failed_count > 0:
        failed_ids_str = ", ".join(map(str, stats.failed_ids))
        summary = (
            "📊 **批量转发完成**\n\n"
            f"✅ 成功: {stats.success_count}/{stats.total}\n"
            f"❌ 失败: {stats.failed_count}\n\n失败的消息ID: {failed_ids_str}"
        )
        logger.warning(
            f"批量转发完成: 成功 {stats.success_count}, 失败 {stats.failed_count}, 失败ID: {failed_ids_str}"
        )
    else:
        summary = f"✅ **批量转发完成**\n\n成功转发 {stats.success_count}/{stats.total} 条消息"
        logger.info(f"批量转发完成: 全部成功 ({stats.success_count}/{stats.total})")

    context.bot.send_message(context.message.chat.id, summary, reply_to_message_id=context.message.id)
