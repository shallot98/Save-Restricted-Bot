"""
Utility functions for the bot
"""

from __future__ import annotations

import importlib
from typing import Any, Dict, Tuple

__all__ = [
    'register_processed_media_group',
    'is_media_group_processed',
    'is_message_processed',
    'mark_message_processed',
    'cleanup_old_messages',
    'get_cache_stats',
    'downstatus',
    'upstatus',
    'progress',
    'get_user_state',
    'set_user_state',
    'clear_user_state',
    'update_user_state',
    'user_states',
    'is_dest_cached',
    'mark_dest_cached',
    'cache_peer',
    'cached_dest_peers',
    'mark_peer_failed',
    'get_failed_peers',
    'get_message_type',
]

_LAZY_IMPORTS: Dict[str, Tuple[str, str]] = {
    # dedup
    "register_processed_media_group": ("bot.utils.dedup", "register_processed_media_group"),
    "is_media_group_processed": ("bot.utils.dedup", "is_media_group_processed"),
    "is_message_processed": ("bot.utils.dedup", "is_message_processed"),
    "mark_message_processed": ("bot.utils.dedup", "mark_message_processed"),
    "cleanup_old_messages": ("bot.utils.dedup", "cleanup_old_messages"),
    "get_cache_stats": ("bot.utils.dedup", "get_cache_stats"),
    # progress (依赖 pyrogram，避免在包导入时触发重依赖加载)
    "downstatus": ("bot.utils.progress", "downstatus"),
    "upstatus": ("bot.utils.progress", "upstatus"),
    "progress": ("bot.utils.progress", "progress"),
    # status
    "get_user_state": ("bot.utils.status", "get_user_state"),
    "set_user_state": ("bot.utils.status", "set_user_state"),
    "clear_user_state": ("bot.utils.status", "clear_user_state"),
    "update_user_state": ("bot.utils.status", "update_user_state"),
    "user_states": ("bot.utils.status", "user_states"),
    # peer
    "is_dest_cached": ("bot.utils.peer", "is_dest_cached"),
    "mark_dest_cached": ("bot.utils.peer", "mark_dest_cached"),
    "cache_peer": ("bot.utils.peer", "cache_peer"),
    "cached_dest_peers": ("bot.utils.peer", "cached_dest_peers"),
    "mark_peer_failed": ("bot.utils.peer", "mark_peer_failed"),
    "get_failed_peers": ("bot.utils.peer", "get_failed_peers"),
    # helpers
    "get_message_type": ("bot.utils.helpers", "get_message_type"),
}


def __getattr__(name: str) -> Any:
    """按需加载子模块符号，避免 import bot.utils 时引入重依赖。"""
    target = _LAZY_IMPORTS.get(name)
    if not target:
        raise AttributeError(f"module 'bot.utils' has no attribute '{name}'")

    module_name, attr_name = target
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(__all__))
