"""
Utility functions for the bot
"""
from .dedup import (
    register_processed_media_group,
    is_media_group_processed,
    is_message_processed,
    mark_message_processed,
    cleanup_old_messages
)
from .progress import downstatus, upstatus, progress
from .status import get_user_state, set_user_state, clear_user_state, update_user_state, user_states
from .peer import is_dest_cached, mark_dest_cached, cache_peer, cached_dest_peers

__all__ = [
    'register_processed_media_group',
    'is_media_group_processed',
    'is_message_processed',
    'mark_message_processed',
    'cleanup_old_messages',
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
]
