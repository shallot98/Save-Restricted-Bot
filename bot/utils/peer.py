"""
Peer caching and management utilities
"""
import logging
import time
from typing import Set, Dict
from pyrogram.errors import FloodWait

logger = logging.getLogger(__name__)

# Cached destination peers
cached_dest_peers: Set[str] = set()

# Failed peers that need delayed loading retry
failed_peers: Dict[str, float] = {}  # peer_id -> last_attempt_timestamp

# Retry cooldown in seconds (wait before retrying failed peer)
RETRY_COOLDOWN = 60


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
    # Remove from failed peers if it was there
    if dest_id in failed_peers:
        del failed_peers[dest_id]


def mark_peer_failed(peer_id: str):
    """Mark peer as failed to cache
    
    Args:
        peer_id: Peer ID that failed to cache
    """
    failed_peers[peer_id] = time.time()
    logger.info(f"📋 已标记失败的Peer: {peer_id} (将在 {RETRY_COOLDOWN}s 后重试)")


def should_retry_peer(peer_id: str) -> bool:
    """Check if we should retry caching a failed peer
    
    Args:
        peer_id: Peer ID to check
        
    Returns:
        True if we should retry, False otherwise
    """
    if peer_id not in failed_peers:
        return True
    
    last_attempt = failed_peers[peer_id]
    elapsed = time.time() - last_attempt
    return elapsed >= RETRY_COOLDOWN


def get_failed_peers() -> Dict[str, float]:
    """Get dictionary of failed peers
    
    Returns:
        Dictionary mapping peer_id to last attempt timestamp
    """
    return failed_peers.copy()


def cache_peer(client, peer_id: str, peer_type: str = "peer", force: bool = False) -> bool:
    """Cache a peer by getting its info
    
    Args:
        client: Pyrogram client
        peer_id: Peer ID to cache
        peer_type: Type description for logging
        force: Force retry even if cooldown hasn't expired
        
    Returns:
        True if cached successfully, False otherwise
    """
    # Check if we should retry this peer
    if not force and not should_retry_peer(peer_id):
        elapsed = time.time() - failed_peers.get(peer_id, 0)
        remaining = RETRY_COOLDOWN - elapsed
        logger.debug(f"⏳ 跳过缓存{peer_type} {peer_id}，等待冷却（还需 {remaining:.0f}秒）")
        return False
    
    try:
        chat = client.get_chat(int(peer_id))
        logger.info(f"✅ 已缓存{peer_type}: {peer_id}")
        mark_dest_cached(peer_id)
        return True
    except FloodWait as e:
        logger.warning(f"⚠️ 限流: {peer_type} {peer_id}，等待 {e.value} 秒")
        mark_peer_failed(peer_id)
        return False
    except Exception as e:
        logger.warning(f"⚠️ 无法缓存{peer_type} {peer_id}: {str(e)}")
        mark_peer_failed(peer_id)
        return False
