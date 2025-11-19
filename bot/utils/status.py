"""
User state management for multi-step interactions
Optimized with TTL-based cleanup to minimize memory usage
"""
import time
import logging
from typing import Dict, Any
from constants import USER_STATE_TTL

logger = logging.getLogger(__name__)

# User state storage with last_access timestamp
# Format: {user_id: {"data": {...}, "last_access": timestamp}}
user_states: Dict[str, Dict[str, Any]] = {}


def get_user_state(user_id: str) -> Dict[str, Any]:
    """Get user state and update last access time
    
    Args:
        user_id: User ID
        
    Returns:
        User state dictionary
    """
    if user_id in user_states:
        # Update last access timestamp
        user_states[user_id]["last_access"] = time.time()
        return user_states[user_id].get("data", {})
    return {}


def set_user_state(user_id: str, state: Dict[str, Any]):
    """Set user state with timestamp
    
    Args:
        user_id: User ID
        state: State dictionary
    """
    user_states[user_id] = {
        "data": state,
        "last_access": time.time()
    }


def clear_user_state(user_id: str):
    """Clear user state
    
    Args:
        user_id: User ID
    """
    if user_id in user_states:
        del user_states[user_id]


def update_user_state(user_id: str, **kwargs):
    """Update user state with new values
    
    Args:
        user_id: User ID
        **kwargs: Key-value pairs to update
    """
    if user_id not in user_states:
        user_states[user_id] = {
            "data": {},
            "last_access": time.time()
        }
    user_states[user_id]["data"].update(kwargs)
    user_states[user_id]["last_access"] = time.time()


def cleanup_expired_states():
    """Clean up expired user states to free memory
    Removes states that haven't been accessed for USER_STATE_TTL seconds
    """
    current_time = time.time()
    expired_users = [
        user_id for user_id, state_data in user_states.items()
        if current_time - state_data.get("last_access", 0) > USER_STATE_TTL
    ]
    
    for user_id in expired_users:
        del user_states[user_id]
    
    if expired_users:
        logger.debug(f"🧹 用户状态清理: 移除{len(expired_users)}个过期状态，当前大小={len(user_states)}")


def get_state_stats() -> dict:
    """Get user state statistics (for monitoring)
    
    Returns:
        Dictionary with state statistics
    """
    return {
        'active_users': len(user_states),
        'ttl_seconds': USER_STATE_TTL
    }
