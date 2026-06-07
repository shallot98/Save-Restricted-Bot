"""PT 联动脚本全局消息监听。"""

from __future__ import annotations

import pyrogram
from pyrogram import filters

from bot.services.pt_pay_manager import get_pt_pay_monitor_manager
from bot.utils.logger import get_logger


logger = get_logger(__name__)


def create_pt_pay_monitor_handler(acc):
    @acc.on_message(filters.incoming & (filters.group | filters.channel | filters.private))
    def _handle(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
        try:
            get_pt_pay_monitor_manager().dispatch_message(message)
        except Exception as exc:
            logger.error(f"❌ PT 联动全局分发失败: {type(exc).__name__}: {exc}", exc_info=True)
