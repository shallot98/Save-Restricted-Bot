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
    ScriptCallbackHandler,
    SigninCallbackHandler,
    HistoryCopyCallbackHandler,
    FilterCallbackHandler,
    EditCallbackHandler,
    ModeCallbackHandler
)
from .instances import get_bot_instance, get_acc_instance
from bot.runtime_services import BotServices

logger = logging.getLogger(__name__)


class CallbackRegistry:
    """回调处理器注册表

    同时充当 Bot 侧回调处理器的**装配点**：`register_all_handlers` 通过
    `bind_services()` 把组合根构造好的 `BotServices` 交给注册表，注册表再以构造
    参数的形式传给每个处理器。处理器因此不再自行 `from composition.container
    import get_watch_service`（报告 §5.3 规则 3）。
    """

    def __init__(self):
        """初始化注册表"""
        self.handlers: List[CallbackHandler] = []
        self._initialized = False
        self._bound_bot = None
        self._bound_acc = None
        self._services: Optional[BotServices] = None
        self._bound_services: Optional[BotServices] = None

    def bind_services(self, services: BotServices) -> None:
        """注入组合根装配的服务集合（幂等；变更时下次分发重建处理器）。"""
        self._services = services

    def _should_reinitialize(self, bot, acc) -> bool:
        """当 Bot/Acc/服务实例变化时强制重建处理器，避免持有旧实例。"""
        if not self._initialized:
            return True
        return (
            bot is not self._bound_bot
            or acc is not self._bound_acc
            or self._services is not self._bound_services
        )

    def initialize(self, force: bool = False) -> None:
        """初始化所有处理器"""
        if self._initialized and not force:
            return

        bot = get_bot_instance()
        acc = get_acc_instance()
        services = self._services

        # 注册所有处理器（顺序很重要，优先级从高到低）
        self.handlers = [
            MenuCallbackHandler(bot, acc, services=services),
            WatchCallbackHandler(bot, acc, services=services),
            ScriptCallbackHandler(bot, acc, services=services),
            SigninCallbackHandler(bot, acc, services=services),
            HistoryCopyCallbackHandler(bot, acc, services=services),
            FilterCallbackHandler(bot, acc, services=services),
            EditCallbackHandler(bot, acc, services=services),
            ModeCallbackHandler(bot, acc, services=services),
        ]

        self._initialized = True
        self._bound_bot = bot
        self._bound_acc = acc
        self._bound_services = services

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
        current_bot = get_bot_instance()
        current_acc = get_acc_instance()
        if self._should_reinitialize(current_bot, current_acc):
            self.initialize(force=True)

        data = callback_query.data
        handler = self.find_handler(data)

        if handler:
            try:
                handler.handle(client, callback_query)
                return True
            except Exception as e:
                logger.error(f"Handler error for '{data}': {e}", exc_info=True)
                # 只回一句通用文案：异常原文含文件路径/chat id/SQL 片段，不得外发
                _safe_answer(callback_query, "❌ 操作失败，请稍后重试")
                return False
        else:
            logger.warning(f"No handler found for callback data: {data}")
            _safe_answer(callback_query, "❌ 未知的回调操作")
            return False


def _safe_answer(callback_query: CallbackQuery, text: str) -> None:
    """回应回调查询；失败只记录日志，不影响主流程。

    使用 `except Exception` 而非裸 except，避免吞掉 KeyboardInterrupt/SystemExit。
    """
    try:
        callback_query.answer(text, show_alert=True)
    except Exception as answer_error:
        logger.warning(f"callback_query.answer 失败: {answer_error}")


# 全局注册表实例
_registry = CallbackRegistry()


def get_callback_registry() -> CallbackRegistry:
    """获取全局回调注册表实例"""
    return _registry
