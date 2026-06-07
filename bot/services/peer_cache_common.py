"""Shared helpers for Telegram peer cache recovery."""

EXPANDED_DIALOG_PEER_TYPES = {"下一级目标", "目标频道", "脚本源群"}
EXPANDED_DIALOG_LIMIT = 100
DEFAULT_DIALOG_LIMIT = 30
BOT_CONNECTION_WAIT_SECONDS = 0.5
FAILED_ERROR_MAX_LENGTH = 60
RETRY_WAIT_SECONDS = 2
PEER_INVALID_MARKERS = ("PEER_ID_INVALID", "Peer id invalid")


def chat_display_name(chat):
    if hasattr(chat, "title") and chat.title:
        return chat.title
    if hasattr(chat, "first_name") and chat.first_name:
        return chat.first_name
    if hasattr(chat, "username") and chat.username:
        return f"@{chat.username}"
    return "Unknown"


def peer_display_name(chat):
    return getattr(chat, "first_name", None) or getattr(chat, "username", None) or "Unknown"


def bot_suffix(chat):
    return " 🤖" if hasattr(chat, "is_bot") and chat.is_bot else ""


def is_peer_invalid_error(error_msg):
    return any(marker in error_msg for marker in PEER_INVALID_MARKERS)


def dialog_search_limit(peer_type):
    if peer_type in EXPANDED_DIALOG_PEER_TYPES:
        return EXPANDED_DIALOG_LIMIT
    return DEFAULT_DIALOG_LIMIT
