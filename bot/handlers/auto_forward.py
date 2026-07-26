"""
自动转发处理器模块
职责：处理频道/群组消息的自动转发

Architecture: Uses new layered architecture
- WatchService 由 register_all_handlers 注入并被闭包捕获
- src/infrastructure/cache for message deduplication
"""
from typing import TYPE_CHECKING

import pyrogram
from pyrogram import filters
from bot.handlers.auto_forward_pipeline import process_auto_forward_message
from bot.utils.logger import get_logger

if TYPE_CHECKING:
    from src.application.services import WatchService

logger = get_logger(__name__)


def create_auto_forward_handler(acc, message_queue, *, watch_service: "WatchService"):
    """
    创建自动转发处理器

    Args:
        acc: User客户端实例
        message_queue: 消息队列实例
        watch_service: 组合根装配的监控配置服务（由闭包捕获，不在处理器内定位）

    Returns:
        function: 自动转发处理器函数
    """

    @acc.on_message((filters.channel | filters.group | filters.private) & (filters.incoming | filters.outgoing))
    def auto_forward(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
        """处理频道/群组/私聊消息，包括转发的消息"""
        process_auto_forward_message(message, message_queue, watch_service=watch_service)

    return auto_forward
