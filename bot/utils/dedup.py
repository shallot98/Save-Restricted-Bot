"""
Message deduplication utilities
Prevents duplicate processing of messages and media groups
"""
import time
import logging
import threading
from typing import Dict, Set

logger = logging.getLogger(__name__)

# Message deduplication cache
MESSAGE_CACHE_TTL = 1  # seconds
processed_messages: Dict[str, float] = {}
_message_lock = threading.Lock()

# Media group deduplication cache (LRU with max 300 entries)
MAX_MEDIA_GROUP_CACHE = 300
processed_media_groups: Set[str] = set()
_media_group_lock = threading.Lock()


def register_processed_media_group(key: str):
    """Register a media group as processed (thread-safe)
    
    Args:
        key: Media group key in format "user_id_watch_key_dest_chat_id_mode_suffix_media_group_id"
    """
    if not key:
        logger.warning("⚠️ register_processed_media_group: 空的key")
        return
    
    with _media_group_lock:
        global processed_media_groups
        
        processed_media_groups.add(key)
        
        # LRU cleanup: keep only last 300 entries
        if len(processed_media_groups) > MAX_MEDIA_GROUP_CACHE:
            # Convert to list, remove first 50 items (oldest), convert back to set
            items = list(processed_media_groups)
            processed_media_groups = set(items[50:])
            logger.debug(f"🧹 媒体组缓存清理: 移除最旧的50个条目，当前大小={len(processed_media_groups)}")


def is_media_group_processed(key: str) -> bool:
    """Check if a media group has been processed (thread-safe)
    
    Args:
        key: Media group key
        
    Returns:
        True if already processed, False otherwise
    """
    if not key:
        return False
    
    with _media_group_lock:
        return key in processed_media_groups


def is_message_processed(message_id: int, chat_id: int) -> bool:
    """Check if a message has been recently processed (thread-safe)
    
    Args:
        message_id: Telegram message ID
        chat_id: Telegram chat ID
        
    Returns:
        True if message was processed within MESSAGE_CACHE_TTL seconds
    """
    key = f"{chat_id}_{message_id}"
    
    with _message_lock:
        if key in processed_messages:
            timestamp = processed_messages[key]
            if time.time() - timestamp < MESSAGE_CACHE_TTL:
                return True
            # Expired, remove it
            del processed_messages[key]
        return False


def mark_message_processed(message_id: int, chat_id: int):
    """Mark a message as processed (thread-safe)
    
    Args:
        message_id: Telegram message ID
        chat_id: Telegram chat ID
    """
    key = f"{chat_id}_{message_id}"
    
    with _message_lock:
        processed_messages[key] = time.time()


def cleanup_old_messages():
    """Clean up expired message records (thread-safe)"""
    current_time = time.time()
    
    with _message_lock:
        expired_keys = [key for key, timestamp in processed_messages.items() 
                        if current_time - timestamp > MESSAGE_CACHE_TTL]
        for key in expired_keys:
            del processed_messages[key]
        
        if expired_keys:
            logger.debug(f"🧹 消息缓存清理: 移除{len(expired_keys)}个过期条目")


def get_cache_stats() -> dict:
    """Get cache statistics (for monitoring/debugging)
    
    Returns:
        Dictionary with cache statistics
    """
    with _message_lock:
        message_count = len(processed_messages)
    
    with _media_group_lock:
        media_group_count = len(processed_media_groups)
    
    return {
        'message_cache_size': message_count,
        'media_group_cache_size': media_group_count,
        'message_cache_ttl': MESSAGE_CACHE_TTL,
        'media_group_cache_max': MAX_MEDIA_GROUP_CACHE
    }
