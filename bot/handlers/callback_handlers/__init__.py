"""
Callback handlers package - 回调处理器包

重构后的回调处理器架构，采用策略模式 + 处理器注册表
"""

from .base import CallbackHandler
from .menu_handler import MenuCallbackHandler
from .watch_handler import WatchCallbackHandler
from .filter_handler import FilterCallbackHandler
from .edit_handler import EditCallbackHandler
from .mode_handler import ModeCallbackHandler

__all__ = [
    'CallbackHandler',
    'MenuCallbackHandler',
    'WatchCallbackHandler',
    'FilterCallbackHandler',
    'EditCallbackHandler',
    'ModeCallbackHandler',
]
