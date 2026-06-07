"""聊天对象输入解析辅助函数。"""

from __future__ import annotations

from typing import Any

from pyrogram.enums import ChatType
from pyrogram.types import Message

from bot.handlers.instances import get_acc_instance


def resolve_chat_input(message: Message, allow_saved_messages: bool, require_bot: bool) -> tuple[str, str, str]:
    """将用户输入解析为 chat_id、显示名和引用。"""
    acc = get_acc_instance()
    if acc is None:
        raise RuntimeError("当前未配置 String Session")

    if message.forward_from_chat is not None:
        chat = acc.get_chat(message.forward_from_chat.id)
        validate_chat_type(chat, require_bot)
        return str(chat.id), chat_name(chat), chat_ref(chat)

    forward_user = getattr(message, "forward_from", None)
    if forward_user is not None:
        chat = acc.get_chat(forward_user.id)
        validate_chat_type(chat, require_bot)
        return str(chat.id), chat_name(chat), chat_ref(chat)

    text = (message.text or "").strip()
    if allow_saved_messages and text.lower() == "me":
        return str(message.from_user.id), "我的收藏夹 (Saved Messages)", str(message.from_user.id)

    ref = text if text.startswith("@") else parse_chat_id(text)
    chat = acc.get_chat(ref)
    validate_chat_type(chat, require_bot)
    return str(chat.id), chat_name(chat), chat_ref(chat)


def validate_chat_type(chat: Any, require_bot: bool) -> None:
    if require_bot and getattr(chat, "type", None) != ChatType.BOT:
        raise ValueError("目标必须是 Bot 对话")


def chat_name(chat: Any) -> str:
    name = getattr(chat, "title", None) or getattr(chat, "username", None) or getattr(chat, "first_name", None)
    return str(name or chat.id)


def chat_ref(chat: Any) -> str:
    username = str(getattr(chat, "username", "") or "").strip()
    if username:
        return username if username.startswith("@") else f"@{username}"
    return str(chat.id)


def parse_chat_id(value: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError("请输入 @用户名、数字 chat_id，或转发一条消息") from exc
