"""
Peer resolution utilities and session persistence helpers
"""

import logging
from typing import Optional, Tuple
from pyrogram import Client
from pyrogram.errors import (
    PeerIdInvalid, 
    ChannelPrivate, 
    UsernameNotOccupied,
    UsernameInvalid,
    FloodWait
)
import time

logger = logging.getLogger(__name__)


def ensure_peer(app: Client, watch_data: dict) -> Tuple[bool, Optional[str], Optional[object]]:
    """
    Safely resolve peer for a watch, returning success status and error message.
    
    Args:
        app: Pyrogram client (user session or bot)
        watch_data: Watch configuration dictionary
        
    Returns:
        (success, error_msg, chat_object)
        - success: True if peer resolved successfully
        - error_msg: User-friendly error message if failed
        - chat_object: Resolved chat object if successful
    """
    source = watch_data.get("source", {})
    
    # Extract source ID
    if isinstance(source, dict):
        source_id = source.get("id", "")
        source_title = source.get("title", "Unknown")
    else:
        source_id = source
        source_title = "Unknown"
    
    # Skip empty sources
    if not source_id:
        return False, "来源ID为空", None
    
    try:
        # Try to resolve the peer
        if isinstance(source_id, str) and source_id.startswith('@'):
            # Username
            chat = app.get_chat(source_id)
        else:
            # Numeric ID
            chat_id = int(source_id) if isinstance(source_id, str) else source_id
            chat = app.get_chat(chat_id)
        
        return True, None, chat
        
    except ChannelPrivate:
        return False, f"无法访问 {source_title}：频道或群组为私有，请确保机器人已加入", None
    except PeerIdInvalid:
        return False, f"无法访问 {source_title}：ID无效或机器人未加入该频道/群组", None
    except UsernameNotOccupied:
        return False, f"无法访问 {source_title}：用户名不存在", None
    except UsernameInvalid:
        return False, f"无法访问 {source_title}：用户名格式无效", None
    except FloodWait as e:
        return False, f"访问受限，请等待 {e.value} 秒后重试", None
    except Exception as e:
        logger.error(f"Error resolving peer for {source_title}: {e}")
        return False, f"无法访问 {source_title}：{str(e)}", None


def warm_up_peers(app: Client, watch_config: dict) -> None:
    """
    Warm up peer cache by attempting to resolve all watch sources.
    Called on startup. Failures are logged but don't prevent bot from starting.
    
    Args:
        app: Pyrogram client (user session)
        watch_config: Full watch configuration
    """
    if app is None:
        logger.info("No user session available, skipping peer warm-up")
        return
    
    logger.info("Starting peer warm-up...")
    
    users = watch_config.get("users", {})
    total_watches = 0
    resolved = 0
    failed = 0
    
    for user_id, watches in users.items():
        for watch_id, watch_data in watches.items():
            total_watches += 1
            
            source = watch_data.get("source", {})
            if isinstance(source, dict):
                source_id = source.get("id", "")
                source_title = source.get("title", "Unknown")
            else:
                source_id = source
                source_title = "Unknown"
            
            if not source_id:
                logger.warning(f"Watch {watch_id}: empty source ID")
                failed += 1
                continue
            
            try:
                # Attempt to resolve
                if isinstance(source_id, str) and source_id.startswith('@'):
                    chat = app.get_chat(source_id)
                else:
                    chat_id = int(source_id) if isinstance(source_id, str) else source_id
                    chat = app.get_chat(chat_id)
                
                logger.info(f"✓ Resolved: {source_title} ({source_id})")
                resolved += 1
                
                # Small delay to avoid rate limits
                time.sleep(0.1)
                
            except FloodWait as e:
                logger.warning(f"FloodWait during warm-up: {e.value}s for {source_title}")
                failed += 1
                time.sleep(min(e.value, 10))  # Wait but cap at 10s during startup
                
            except (ChannelPrivate, PeerIdInvalid) as e:
                logger.warning(f"✗ Cannot access {source_title} ({source_id}): {type(e).__name__}")
                failed += 1
                
            except Exception as e:
                logger.warning(f"✗ Failed to resolve {source_title} ({source_id}): {e}")
                failed += 1
    
    logger.info(f"Peer warm-up complete: {resolved}/{total_watches} resolved, {failed} failed")
