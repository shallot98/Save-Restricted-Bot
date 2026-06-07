"""
Message handlers for the bot

Architecture: Uses new layered architecture
- src/core/container for service access
"""
import pyrogram
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.handlers.instances import get_bot_instance, get_acc_instance
from bot.handlers.message_link_forwarding import (
    LinkForwardContext,
    handle_telegram_link_input,
)
from bot.handlers.message_state_input import handle_user_state_input
from bot.handlers.private_message_forwarding import PrivateMessageContext, forward_private_message
from bot.utils.logger import get_logger

try:
    from src.infrastructure.monitoring.performance.business_metrics import get_business_metrics
except Exception:
    get_business_metrics = None

logger = get_logger(__name__)


def _send_unknown_message_help(message: pyrogram.types.messages_and_media.message.Message) -> None:
    """给未识别的私聊文本返回明确指引，避免静默无响应。"""
    bot = get_bot_instance()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 脚本管理", callback_data="menu_script")],
        [InlineKeyboardButton("❓ 使用帮助", callback_data="menu_help")],
    ])

    text = "**❌ 未识别的消息内容**\n\n"
    text += "当前支持的主要用法：\n"
    text += "• 发送 Telegram 消息链接进行转发/下载\n"
    text += "• 点击“脚本管理”配置 PT 联动或定时签到\n"
    text += "• 输入 `/start` 或 `/help` 查看菜单和说明"
    bot.send_message(message.chat.id, text, reply_markup=keyboard, reply_to_message_id=message.id)


def save(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    """Handle user text input during multi-step interactions"""
    metrics = get_business_metrics() if get_business_metrics else None
    category = "unknown"
    success = True
    error_type = None

    bot = get_bot_instance()
    acc = get_acc_instance()

    user_id = str(message.from_user.id)

    try:
        handled, state_category = handle_user_state_input(message, user_id, bot)
        category = state_category or category
        if handled:
            return

        handled, link_category = handle_telegram_link_input(
            LinkForwardContext(
                message=message,
                bot=bot,
                acc=acc,
                metrics=metrics,
                private_forward=handle_private,
            )
        )
        category = link_category or category
        if handled:
            return

        category = "other"
        _send_unknown_message_help(message)

    except Exception as e:
        success = False
        error_type = type(e).__name__
        raise
    finally:
        if metrics is not None:
            metrics.record_message_processed(success=success, category=category, error_type=error_type)


def handle_private(message: pyrogram.types.messages_and_media.message.Message, chatid: int, msgid: int):
    """Handle private message download and forward"""
    bot = get_bot_instance()
    acc = get_acc_instance()
    forward_private_message(
        PrivateMessageContext(message=message, chatid=chatid, msgid=msgid, bot=bot, acc=acc)
    )
