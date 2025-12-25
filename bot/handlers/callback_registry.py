"""
Callback registry - 回调处理器注册表

管理所有回调处理器的注册和分发
"""

import logging
from typing import List, Optional
from pyrogram import Client
from pyrogram.types import CallbackQuery

from .callback_handlers import (
    CallbackHandler,
    MenuCallbackHandler,
    WatchCallbackHandler,
    FilterCallbackHandler,
    EditCallbackHandler,
    ModeCallbackHandler
)
from .instances import get_bot_instance, get_acc_instance

logger = logging.getLogger(__name__)


class CallbackRegistry:
    """回调处理器注册表"""

    def __init__(self):
        """初始化注册表"""
        self.handlers: List[CallbackHandler] = []
        self._initialized = False

    def initialize(self) -> None:
        """初始化所有处理器"""
        if self._initialized:
            return

        bot = get_bot_instance()
        acc = get_acc_instance()

        # 注册所有处理器（顺序很重要，优先级从高到低）
        self.handlers = [
            MenuCallbackHandler(bot, acc),
            WatchCallbackHandler(bot, acc),
            FilterCallbackHandler(bot, acc),
            EditCallbackHandler(bot, acc),
            ModeCallbackHandler(bot, acc),
        ]

        self._initialized = True

    def find_handler(self, data: str) -> Optional[CallbackHandler]:
        """
        查找能够处理该回调数据的处理器

        Args:
            data: 回调数据字符串

        Returns:
            CallbackHandler: 找到的处理器，如果没有则返回 None
        """
        for handler in self.handlers:
            if handler.can_handle(data):
                return handler
        return None

    def dispatch(self, client: Client, callback_query: CallbackQuery) -> bool:
        """
        分发回调查询到相应的处理器

        Args:
            client: Pyrogram客户端
            callback_query: 回调查询对象

        Returns:
            bool: 是否成功处理
        """
        if not self._initialized:
            self.initialize()

        data = callback_query.data
        handler = self.find_handler(data)

        if handler:
            try:
                handler.handle(client, callback_query)
                return True
            except Exception as e:
                logger.error(f"Handler error for '{data}': {e}", exc_info=True)
                try:
                    callback_query.answer(f"❌ 错误: {str(e)}", show_alert=True)
                except:
                    pass
                return False
        else:
            logger.warning(f"No handler found for callback data: {data}")
            try:
                callback_query.answer("❌ 未知的回调操作", show_alert=True)
            except:
                pass
            return False


# 全局注册表实例
_registry = CallbackRegistry()


def get_callback_registry() -> CallbackRegistry:
    """获取全局回调注册表实例"""
    return _registry
