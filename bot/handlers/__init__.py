"""
Message and callback handlers for the bot
"""
from pyrogram import filters
from pyrogram.enums import ChatType
from bot.utils.logger import get_logger
from .authorization import build_owner_filter, resolve_owner_ids
from .commands import register_command_handlers
from .callbacks import callback_handler
from .messages import save
from .auto_forward import create_auto_forward_handler
from bot.services.history_copy_task_manager import get_history_copy_task_manager
from bot.services.pt_pay_manager import get_pt_pay_monitor_manager
from bot.services.signin_manager import get_scheduled_signin_manager
from bot.runtime_services import BotServices
from .callback_registry import get_callback_registry
from .instances import (
    set_bot_instance, set_acc_instance,
    get_bot_instance, get_acc_instance
)

logger = get_logger(__name__)
SUPPORTED_DIRECT_CHAT_TYPES = frozenset({ChatType.PRIVATE, ChatType.BOT})


def _is_supported_direct_chat(_, __, message) -> bool:
    """Allow bot direct chats in addition to classic private chats."""
    chat = getattr(message, "chat", None)
    return getattr(chat, "type", None) in SUPPORTED_DIRECT_CHAT_TYPES


DIRECT_CHAT_FILTER = filters.create(_is_supported_direct_chat, name="DirectChatFilter")


def register_all_handlers(bot, acc, message_queue, *, services: BotServices):
    """
    统一注册所有处理器

    Args:
        bot: Bot客户端实例
        acc: User客户端实例（可能为None）
        message_queue: 消息队列实例（可能为None）
        services: 组合根（``composition.bot_runtime.build_bot_services``）装配的
            服务集合。这里是 Bot 表现层唯一的服务入口——注册期把它分发给命令
            处理器、回调注册表、消息处理器与自动转发闭包，各处理器因此不再
            ``from composition.container import get_xxx()``（报告 §5.3 规则 3）。
    """
    logger.info("📝 正在注册所有处理器...")

    # 设置全局实例
    set_bot_instance(bot)
    set_acc_instance(acc)

    # Bot 侧处理器可被任何知道 @username 的人触达，但它们驱动的是机主的个人
    # 账号，因此全部注册在所有者白名单之后。
    owner_filter = build_owner_filter(resolve_owner_ids(acc))

    # 注册命令处理器
    register_command_handlers(
        bot, acc, owner_filter=owner_filter, watch_service=services.watch_service
    )
    logger.info("✅ 命令处理器已注册")

    # 回调处理器的装配点：注册表在构造每个 CallbackHandler 时把服务传进去
    get_callback_registry().bind_services(services)

    # 注册回调处理器
    @bot.on_callback_query(owner_filter)
    def handle_callback(client, callback_query):
        callback_handler(client, callback_query)

    logger.info("✅ 回调处理器已注册")

    # 注册私聊消息处理器
    @bot.on_message(
        owner_filter
        & filters.text
        & DIRECT_CHAT_FILTER
        & ~filters.command(["start", "help", "watch"])
    )
    def handle_save(client, message):
        save(client, message, services=services)

    logger.info("✅ 直接对话消息处理器已注册")

    if acc is not None:
        get_history_copy_task_manager().bind_client(acc)
        logger.info("✅ 历史复制任务管理器已绑定 User 客户端")
        get_pt_pay_monitor_manager().bind_client(acc)
        logger.info("✅ PT 联动脚本管理器已绑定 User 客户端")
        get_scheduled_signin_manager().bind_client(acc)
        logger.info("✅ 定时签到脚本管理器已绑定 User 客户端")

    # 注册自动转发处理器（如果acc可用）
    if acc is not None and message_queue is not None:
        create_auto_forward_handler(acc, message_queue, watch_service=services.watch_service)
        logger.info("✅ 自动转发处理器已注册")
    else:
        logger.warning("⚠️ 自动转发处理器未注册（User客户端或消息队列不可用）")

    logger.info("🎉 所有处理器注册完成！")
