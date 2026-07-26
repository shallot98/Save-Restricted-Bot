"""
Watch configuration and setup handlers.

Architecture: Uses new layered architecture
- composition/container for service access
"""
from __future__ import annotations

from typing import Tuple

from pyrogram.errors import ChannelPrivate, UsernameInvalid
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.handlers.instances import get_acc_instance, get_bot_instance
from bot.handlers.watch_setup_completion import complete_watch_setup, complete_watch_setup_single
from bot.handlers.watch_setup_models import (
    ForwardModeChoiceOptions,
    ForwardWatchSetupOptions,
    WatchFilterOptions,
    WatchSetupTarget,
)
from bot.handlers.watch_setup_ui import (
    show_dn_append_options,
    show_filter_options,
    show_filter_options_single,
    show_forward_mode_options,
    show_preserve_source_options,
)
from bot.utils.status import user_states


def _resolve_chat_reference(
    message: Message,
    *,
    allow_saved_messages: bool,
    saved_messages_label: str,
) -> Tuple[str, str]:
    acc = get_acc_instance()
    if message.forward_from_chat:
        chat = message.forward_from_chat
        return str(chat.id), chat.title or chat.username or str(chat.id)

    text = (message.text or "").strip()
    if allow_saved_messages and text.lower() == "me":
        return str(message.from_user.id), saved_messages_label
    if not allow_saved_messages and text.lower() == "me":
        return "me", "个人收藏"
    if text.startswith("@"):
        chat = acc.get_chat(text)
        return str(chat.id), chat.title or chat.username or str(chat.id)

    try:
        chat_id = int(text)
    except ValueError as exc:
        raise ValueError("**❌ 无效的频道/群组ID**\n\n请输入正确的格式") from exc

    chat = acc.get_chat(chat_id)
    return str(chat.id), chat.title or chat.username or str(chat.id)


def handle_add_source(message: Message, user_id: str) -> None:
    """Handle add source step."""
    bot = get_bot_instance()
    try:
        source_id, source_name = _resolve_chat_reference(
            message,
            allow_saved_messages=True,
            saved_messages_label="我的收藏夹 (Saved Messages)",
        )
        user_states[user_id]["source_id"] = source_id
        user_states[user_id]["source_name"] = source_name
        user_states[user_id]["action"] = "choose_mode"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 记录模式", callback_data="watch_mode_record")],
            [InlineKeyboardButton("➡️ 转发模式", callback_data="watch_mode_forward")],
            [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")],
        ])
        text = (
            "**➕ 添加监控任务**\n\n"
            f"✅ 来源已设置：`{source_name}`\n\n"
            "**步骤 2：** 选择监控模式\n\n"
            "📝 **记录模式** - 只监控这一个频道，消息保存到网页笔记\n"
            "➡️ **转发模式** - 从这个频道转发消息到另一个频道/群组"
        )
        bot.send_message(message.chat.id, text, reply_markup=keyboard)
    except ChannelPrivate:
        bot.send_message(message.chat.id, "**❌ 无法访问该频道/群组**\n\n请确保账号已加入")
    except UsernameInvalid:
        bot.send_message(message.chat.id, "**❌ 频道/群组用户名无效**\n\n请检查输入")
    except ValueError as exc:
        bot.send_message(message.chat.id, str(exc))
    except Exception as e:
        bot.send_message(message.chat.id, f"**❌ 错误：** `{str(e)}`")


def handle_add_dest(message: Message, user_id: str) -> None:
    """Handle add destination step."""
    bot = get_bot_instance()
    try:
        dest_id, dest_name = _resolve_chat_reference(
            message,
            allow_saved_messages=False,
            saved_messages_label="个人收藏",
        )
        user_states[user_id]["dest_id"] = dest_id
        user_states[user_id]["dest_name"] = dest_name

        msg = bot.send_message(message.chat.id, "⏳ 正在设置...")
        show_filter_options(message.chat.id, msg.id, user_id)
    except ChannelPrivate:
        bot.send_message(message.chat.id, "**❌ 无法访问该频道/群组**\n\n请确保机器人有发送权限")
    except UsernameInvalid:
        bot.send_message(message.chat.id, "**❌ 频道/群组用户名无效**\n\n请检查输入")
    except ValueError as exc:
        bot.send_message(message.chat.id, str(exc))
    except Exception as e:
        bot.send_message(message.chat.id, f"**❌ 错误：** `{str(e)}`")
