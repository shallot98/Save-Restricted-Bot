"""
Peer caching and management utilities
"""
import logging
from typing import Set
from pyrogram.errors import FloodWait

logger = logging.getLogger(__name__)

# Cached destination peers
cached_dest_peers: Set[str] = set()


def is_dest_cached(dest_id: str) -> bool:
    """Check if destination peer is cached
    
    Args:
        dest_id: Destination chat ID
        
    Returns:
        True if cached, False otherwise
    """
    return dest_id in cached_dest_peers


def mark_dest_cached(dest_id: str):
    """Mark destination peer as cached
    
    Args:
        dest_id: Destination chat ID
    """
    cached_dest_peers.add(dest_id)


def cache_peer(client, peer_id: str, peer_type: str = "peer") -> bool:
    """Cache a peer by getting its info
    
    Args:
        client: Pyrogram client
        peer_id: Peer ID to cache
        peer_type: Type description for logging
        
    Returns:
        True if cached successfully, False otherwise
    """
    try:
        chat = client.get_chat(int(peer_id))
        logger.info(f"✅ 已缓存{peer_type}: {peer_id}")
        return True
    except FloodWait as e:
        logger.warning(f"⚠️ 限流: {peer_type} {peer_id}，等待 {e.value} 秒")
        return False
    except Exception as e:
        logger.warning(f"⚠️ 无法缓存{peer_type} {peer_id}: {str(e)}")
        return False
