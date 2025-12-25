"""
User state management for multi-step interactions

向后兼容模块：导出新的状态管理器接口
"""
from typing import Dict, Any

# 导入新的状态管理器
from bot.utils.state_manager import (
    UserStateManager,
    get_state_manager,
    user_states  # 向后兼容的代理对象
)

# 导出向后兼容的函数接口
__all__ = [
    'user_states',
    'get_user_state',
    'set_user_state',
    'clear_user_state',
    'update_user_state',
    'UserStateManager',
    'get_state_manager'
]


def get_user_state(user_id: str) -> Dict[str, Any]:
    """Get user state

    Args:
        user_id: User ID

    Returns:
        User state dictionary
    """
    return get_state_manager().get(user_id)


def set_user_state(user_id: str, state: Dict[str, Any]):
    """Set user state

    Args:
        user_id: User ID
        state: State dictionary
    """
    get_state_manager().set(user_id, state)


def clear_user_state(user_id: str):
    """Clear user state

    Args:
        user_id: User ID
    """
    get_state_manager().clear(user_id)


def update_user_state(user_id: str, **kwargs):
    """Update user state with new values

    Args:
        user_id: User ID
        **kwargs: Key-value pairs to update
    """
    get_state_manager().update(user_id, **kwargs)
