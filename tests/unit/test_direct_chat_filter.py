from __future__ import annotations

from types import SimpleNamespace

from pyrogram.enums import ChatType

from bot.handlers import _is_supported_direct_chat


def _message(chat_type: ChatType):
    return SimpleNamespace(chat=SimpleNamespace(type=chat_type))


def test_direct_chat_filter_accepts_private_and_bot() -> None:
    assert _is_supported_direct_chat(None, None, _message(ChatType.PRIVATE)) is True
    assert _is_supported_direct_chat(None, None, _message(ChatType.BOT)) is True


def test_direct_chat_filter_rejects_non_direct_chats() -> None:
    assert _is_supported_direct_chat(None, None, _message(ChatType.GROUP)) is False
    assert _is_supported_direct_chat(None, None, _message(ChatType.SUPERGROUP)) is False
    assert _is_supported_direct_chat(None, None, _message(ChatType.CHANNEL)) is False
