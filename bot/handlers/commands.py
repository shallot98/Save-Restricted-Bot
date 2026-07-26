"""
Command handlers for /start, /help, /watch commands

Architecture: Uses new layered architecture
- ``WatchService`` 由 ``register_all_handlers`` 注入，逐层传给 ``show_watch_menu``；
  本模块不认识组合根（报告 §5.3 规则 3）。
"""
import pyrogram
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging
from typing import TYPE_CHECKING, Optional

from bot.services.history_copy_task_manager import get_history_copy_task_manager
from bot.services.pt_pay_manager import get_pt_pay_monitor_manager
from bot.services.signin_manager import get_scheduled_signin_manager

if TYPE_CHECKING:
    from src.application.services import WatchService

logger = logging.getLogger(__name__)


def register_command_handlers(
    bot,
    acc,
    owner_filter=None,
    *,
    watch_service: Optional["WatchService"] = None,
):
    """Register all command handlers.

    ``owner_filter`` restricts the commands to the bot owner. It is resolved
    from configuration when the caller does not supply one, so there is no
    call path that registers these commands unprotected.

    ``watch_service`` 由 ``register_all_handlers`` 注入。允许为 None 仅是为了让
    只验证 /start、/help 键盘的单测能免装配构造；``/watch`` 真正取用时未注入会
    立刻抛错，不做静默回落。
    """
    if owner_filter is None:
        from bot.handlers.authorization import build_owner_filter, resolve_owner_ids
        owner_filter = build_owner_filter(resolve_owner_ids(acc))

    @bot.on_message(owner_filter & filters.command(["start"]))
    def send_start(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
        bot.send_message(
            message.chat.id,
            _welcome_text(message),
            reply_markup=_start_keyboard(),
            reply_to_message_id=message.id,
        )

    @bot.on_message(owner_filter & filters.command(["help"]))
    def send_help(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
        bot.send_message(
            message.chat.id,
            _help_text(),
            reply_markup=_help_keyboard(),
            reply_to_message_id=message.id,
        )

    @bot.on_message(owner_filter & filters.command(["watch"]))
    def watch_command(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
        if acc is None:
            bot.send_message(
                message.chat.id,
                "**❌ 需要配置 String Session 才能使用监控功能**",
                reply_markup=_main_menu_keyboard(),
                reply_to_message_id=message.id,
            )
            return

        if watch_service is None:
            raise RuntimeError(
                "register_command_handlers 未注入 WatchService，/watch 无法工作；"
                "请检查 main.py → register_all_handlers 的装配路径"
            )
        show_watch_menu(message.chat.id, message.id, watch_service=watch_service)


def _start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 脚本管理", callback_data="menu_script")],
        [InlineKeyboardButton("❓ 帮助说明", callback_data="menu_help")],
        [InlineKeyboardButton("🌐 源代码", url="https://github.com/bipinkrish/Save-Restricted-Bot")],
    ])


def _welcome_text(message) -> str:
    text = f"👋 你好 **{message.from_user.mention}**！\n\n"
    text += "我是受限内容保存机器人，可以帮你：\n\n"
    text += "📥 **转发消息** - 直接发送 Telegram 链接\n"
    text += "🤖 **脚本模式** - 管理 PT 联动、定时签到和历史复制任务\n\n"
    text += "点击下方按钮开始使用 👇"
    return text


def _help_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 脚本管理", callback_data="menu_script")],
        [InlineKeyboardButton("🏠 返回主菜单", callback_data="menu_main")],
    ])


def _main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 返回主菜单", callback_data="menu_main")]])


def _help_text() -> str:
    return """**📖 使用帮助**

**📥 转发消息**
直接发送 Telegram 消息链接即可转发内容

**🤖 脚本联动**
• 监控指定群聊中至少两行 `PT-xx`
• 自动按顺序向目标对象发送 `/pay`
• 命中“成功”关键字后自动停止
• 支持在菜单中手动启停

**🕒 定时签到**
• 向指定群聊/频道定时发送固定消息
• 支持自定义消息内容和发送间隔
• 适合给群内用户（如“司机人”）周期发送签到提醒

**📚 历史复制**
• 按来源 chat 历史顺序复制到目标群聊/频道
• 支持全部历史或最近 N 条
• 内置断点续传与风控保护

**🔗 链接格式**

公开频道/群组：
`https://t.me/username/123`

私有频道/群组（需要先加入）：
`https://t.me/c/123456789/123`

批量下载（范围）：
`https://t.me/username/100-120`

机器人消息：
`https://t.me/b/botusername/123`

**💡 提示**
• 私有频道需要配置 String Session
• 转发功能保持不变，直接发送 Telegram 链接即可
• 所有操作都可通过按钮完成，无需记忆复杂命令
"""


def show_watch_menu(chat_id, reply_to_message_id=None, *, watch_service: "WatchService"):
    """Show watch menu using the injected WatchService."""
    from bot.handlers import get_bot_instance
    bot = get_bot_instance()

    watch_config = watch_service.get_all_configs_dict()
    user_id = str(chat_id)

    watch_count = len(watch_config.get(user_id, {}))

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ 添加监控", callback_data="watch_add_start")],
        [InlineKeyboardButton(f"📋 查看列表 ({watch_count})", callback_data="watch_list")],
        [InlineKeyboardButton("🗑 删除监控", callback_data="watch_remove_start")],
        [InlineKeyboardButton("🤖 脚本管理", callback_data="menu_script")],
        [InlineKeyboardButton("🏠 返回主菜单", callback_data="menu_main")]
    ])

    text = "**📋 监控管理**\n\n"
    text += "选择操作：\n\n"
    text += "➕ **添加监控** - 设置新的自动转发任务\n"
    text += "📋 **查看列表** - 查看所有监控任务\n"
    text += "🗑 **删除监控** - 移除现有监控任务\n\n"
    text += f"当前监控任务数：**{watch_count}** 个"

    bot.send_message(chat_id, text, reply_markup=keyboard, reply_to_message_id=reply_to_message_id)


def show_script_menu(chat_id, reply_to_message_id=None):
    """Show script type overview menu."""
    from bot.handlers import get_bot_instance
    bot = get_bot_instance()

    user_id = str(chat_id)
    pt_manager = get_pt_pay_monitor_manager()
    signin_manager = get_scheduled_signin_manager()
    history_copy_manager = get_history_copy_task_manager()
    pt_total = pt_manager.count_user_tasks(user_id)
    pt_enabled = pt_manager.count_enabled_user_tasks(user_id)
    signin_total = signin_manager.count_user_tasks(user_id)
    signin_enabled = signin_manager.count_enabled_user_tasks(user_id)
    history_total = history_copy_manager.count_user_tasks(user_id)
    history_running = history_copy_manager.count_running_user_tasks(user_id)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🤖 PT 联动脚本 ({pt_enabled}/{pt_total} 运行中)", callback_data="menu_script_pt")],
        [InlineKeyboardButton(f"🕒 定时签到脚本 ({signin_enabled}/{signin_total} 运行中)", callback_data="menu_script_signin")],
        [InlineKeyboardButton(f"📚 历史复制 ({history_running}/{history_total} 运行中)", callback_data="menu_script_history_copy")],
        [InlineKeyboardButton("🏠 返回主菜单", callback_data="menu_main")],
    ])

    text = "**🤖 脚本管理**\n\n"
    text += "先选择脚本类型，再进入对应页面添加或管理脚本。\n\n"
    text += f"PT 脚本：**{pt_total}** 个，其中运行中 **{pt_enabled}** 个\n"
    text += f"签到脚本：**{signin_total}** 个，其中运行中 **{signin_enabled}** 个\n"
    text += f"历史复制：**{history_total}** 个，其中运行中 **{history_running}** 个"

    bot.send_message(chat_id, text, reply_markup=keyboard, reply_to_message_id=reply_to_message_id)
