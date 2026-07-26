"""
Base callback handler - 回调处理器基类

定义所有回调处理器的通用接口和共享功能
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional
from pyrogram import Client
from pyrogram.types import CallbackQuery

from bot.runtime_services import BotServices

if TYPE_CHECKING:
    from src.application.services import WatchService, WatchSetupService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CallbackContext:
    client: Client
    callback_query: CallbackQuery
    data: str
    chat_id: int
    message_id: int
    user_id: str


CallbackRoute = Callable[[CallbackContext], None]


class CallbackHandler(ABC):
    """回调处理器基类"""

    def __init__(
        self,
        bot: Client,
        acc: Optional[Client] = None,
        *,
        services: Optional[BotServices] = None,
    ):
        """
        初始化处理器

        Args:
            bot: Bot客户端实例
            acc: User客户端实例（可选）
            services: 组合根装配的服务集合，由 ``CallbackRegistry`` 传入。

        ``services`` 允许为 None 是为了让只验证键盘/文案的单测能直接
        ``Handler(bot, acc)`` 构造。真正取用服务时走下面的属性，未注入会立刻抛
        ``RuntimeError``——不做静默回落到全局容器（§5.3 规则 5）。
        """
        self.bot = bot
        self.acc = acc
        self._services = services

    def _require_services(self) -> BotServices:
        if self._services is None:
            raise RuntimeError(
                f"{type(self).__name__} 未注入 BotServices；"
                "请检查 register_all_handlers → CallbackRegistry.bind_services 的装配路径"
            )
        return self._services

    @property
    def watch_service(self) -> "WatchService":
        """监控配置服务（构造期注入，缺失即失败）。"""
        return self._require_services().watch_service

    @property
    def watch_setup_service(self) -> "WatchSetupService":
        """监控任务创建编排服务（构造期注入，缺失即失败）。"""
        return self._require_services().watch_setup_service

    @abstractmethod
    def can_handle(self, data: str) -> bool:
        """
        判断是否可以处理该回调数据

        Args:
            data: 回调数据字符串

        Returns:
            bool: 是否可以处理
        """
        pass

    @abstractmethod
    def handle(self, client: Client, callback_query: CallbackQuery) -> None:
        """
        处理回调查询

        Args:
            client: Pyrogram客户端
            callback_query: 回调查询对象
        """
        pass

    def get_common_params(self, callback_query: CallbackQuery) -> dict:
        """
        提取通用参数

        Args:
            callback_query: 回调查询对象

        Returns:
            dict: 包含通用参数的字典
        """
        return {
            'data': callback_query.data,
            'chat_id': callback_query.message.chat.id,
            'message_id': callback_query.message.id,
            'user_id': str(callback_query.from_user.id),
            'callback_query': callback_query
        }

    def get_common_context(self, client: Client, callback_query: CallbackQuery) -> CallbackContext:
        """Build the shared callback context used by internal handlers."""
        return CallbackContext(
            client=client,
            callback_query=callback_query,
            data=callback_query.data,
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.id,
            user_id=str(callback_query.from_user.id),
        )

    def dispatch_context(
        self,
        context: CallbackContext,
        exact: Mapping[str, CallbackRoute] | None = None,
        prefixes: Sequence[tuple[str, CallbackRoute]] = (),
    ) -> bool:
        """Dispatch a callback context by exact callback data or prefix.

        未命中任何路由时必须回应 callback_query：Telegram 客户端在收不到 answer 时
        按钮会永久转圈，若同时不打日志则线上完全无迹可寻。can_handle 的前缀比 exact
        表宽（如 `filter_` 前缀覆盖了已删除的 filter_none），这条兜底就是该缺口的闸门。
        """
        if exact and context.data in exact:
            exact[context.data](context)
            return True

        for prefix, handler in prefixes:
            if context.data.startswith(prefix):
                handler(context)
                return True

        logger.warning(
            "%s 接受了回调 '%s' 但没有匹配的路由", type(self).__name__, context.data
        )
        self.answer_and_log(context.callback_query, "❌ 该操作已下线", show_alert=True)
        return False

    def answer_and_log(self, callback_query: CallbackQuery, text: str = "", show_alert: bool = False) -> None:
        """
        回答回调查询并记录日志

        Args:
            callback_query: 回调查询对象
            text: 提示文本
            show_alert: 是否显示警告框
        """
        try:
            callback_query.answer(text, show_alert=show_alert)
        except Exception as e:
            logger.debug(f"Answer callback error: {e}")
