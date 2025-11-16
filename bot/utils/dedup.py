"""
Message deduplication utilities
Prevents duplicate processing of messages and media groups
"""
import time
import logging
from typing import Dict, Set

logger = logging.getLogger(__name__)

# Message deduplication cache
MESSAGE_CACHE_TTL = 1  # seconds
processed_messages: Dict[str, float] = {}

# Media group deduplication cache (LRU with max 300 entries)
MAX_MEDIA_GROUP_CACHE = 300
processed_media_groups: Set[str] = set()


def register_processed_media_group(key: str):
    """Register a media group as processed
    
    Args:
        key: Media group key in format "user_id_watch_key_dest_chat_id_mode_suffix_media_group_id"
    """
    global processed_media_groups
    
    processed_media_groups.add(key)
    
    # LRU cleanup: keep only last 300 entries
    if len(processed_media_groups) > MAX_MEDIA_GROUP_CACHE:
        # Convert to list, remove first 50 items (oldest), convert back to set
        items = list(processed_media_groups)
        processed_media_groups = set(items[50:])
        logger.debug(f"🧹 媒体组缓存清理: 移除最旧的50个条目，当前大小={len(processed_media_groups)}")


def is_media_group_processed(key: str) -> bool:
    """Check if a media group has been processed
    
    Args:
        key: Media group key
        
    Returns:
        True if already processed, False otherwise
    """
    return key in processed_media_groups


def is_message_processed(message_id: int, chat_id: int) -> bool:
    """Check if a message has been recently processed
    
    Args:
        message_id: Telegram message ID
        chat_id: Telegram chat ID
        
    Returns:
        True if message was processed within MESSAGE_CACHE_TTL seconds
    """
    key = f"{chat_id}_{message_id}"
    if key in processed_messages:
        timestamp = processed_messages[key]
        if time.time() - timestamp < MESSAGE_CACHE_TTL:
            return True
        # Expired, remove it
        del processed_messages[key]
    return False


def mark_message_processed(message_id: int, chat_id: int):
    """Mark a message as processed
    
    Args:
        message_id: Telegram message ID
        chat_id: Telegram chat ID
    """
    key = f"{chat_id}_{message_id}"
    processed_messages[key] = time.time()


def cleanup_old_messages():
    """Clean up expired message records"""
    current_time = time.time()
    expired_keys = [key for key, timestamp in processed_messages.items() 
                    if current_time - timestamp > MESSAGE_CACHE_TTL]
    for key in expired_keys:
        del processed_messages[key]
