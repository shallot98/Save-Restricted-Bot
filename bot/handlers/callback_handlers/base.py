"""
Base callback handler - 回调处理器基类

定义所有回调处理器的通用接口和共享功能
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional
from pyrogram import Client
from pyrogram.types import CallbackQuery

logger = logging.getLogger(__name__)


class CallbackHandler(ABC):
    """回调处理器基类"""

    def __init__(self, bot: Client, acc: Optional[Client] = None):
        """
        初始化处理器

        Args:
            bot: Bot客户端实例
            acc: User客户端实例（可选）
        """
        self.bot = bot
        self.acc = acc

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
