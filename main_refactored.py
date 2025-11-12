"""
重构后的主程序 - 使用模块化架构
遵循 SOLID 原则，代码结构清晰，易于维护和扩展
"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pyrogram
from pyrogram import Client, filters
from pyrogram.errors import UserAlreadyParticipant, InviteHashExpired, UsernameNotOccupied, ChannelPrivate, UsernameInvalid
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import time
import threading
import re

# 导入重构后的模块
from config.config_manager import get_config
from services.record_service import RecordService
from services.filter_service import FilterService
from services.forward_service import ForwardService
import database

# 初始化配置管理器
config = get_config()
print(config)

# 初始化数据库（使用新的路径）
database.DATA_DIR = str(config.data_dir)
database.DATABASE_FILE = str(config.database_file)
database.init_database()

# 初始化Bot客户端
bot_token = config.get_bot_token()
api_hash = config.get_api_hash()
api_id = config.get_api_id()

if not bot_token or not api_id or not api_hash:
    print("❌ 错误：缺少必要的配置信息（TOKEN, ID, HASH）")
    print("请检查配置文件或环境变量")
    sys.exit(1)

bot = Client("mybot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

# 初始化用户账号客户端（如果配置了Session String）
session_string = config.get_session_string()
if session_string:
    acc = Client("myacc", api_id=api_id, api_hash=api_hash, session_string=session_string)
    acc.start()
    print("✅ 用户账号客户端已启动")
else:
    acc = None
    print("⚠️ 未配置 Session String，部分功能将不可用")

# 初始化服务
record_service = RecordService(acc, database, config) if acc else None
filter_service = FilterService()
forward_service = ForwardService(acc) if acc else None

# 用户状态管理
user_states = {}

# download status
def downstatus(statusfile, message):
    while True:
        if os.path.exists(statusfile):
            break
    time.sleep(3)
    while os.path.exists(statusfile):
        with open(statusfile, "r") as downread:
            txt = downread.read()
        try:
            bot.edit_message_text(message.chat.id, message.id, f"__⬇️ 已下载__ : **{txt}**")
            time.sleep(10)
        except:
            time.sleep(5)

# upload status
def upstatus(statusfile, message):
    while True:
        if os.path.exists(statusfile):
            break
    time.sleep(3)
    while os.path.exists(statusfile):
        with open(statusfile, "r") as upread:
            txt = upread.read()
        try:
            bot.edit_message_text(message.chat.id, message.id, f"__⬆️ 已上传__ : **{txt}**")
            time.sleep(10)
        except:
            time.sleep(5)

# progress writter
def progress(current, total, message, type):
    with open(f'{message.id}{type}status.txt', "w") as fileup:
        fileup.write(f"{current * 100 / total:.1f}%")

# start command
@bot.on_message(filters.command(["start"]))
def send_start(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 监控管理", callback_data="menu_watch")],
        [InlineKeyboardButton("❓ 帮助说明", callback_data="menu_help")],
        [InlineKeyboardButton("🌐 源代码", url="https://github.com/bipinkrish/Save-Restricted-Bot")]
    ])

    welcome_text = f"👋 你好 **{message.from_user.mention}**！\n\n"
    welcome_text += "我是受限内容保存机器人，可以帮你：\n\n"
    welcome_text += "📥 **转发消息** - 直接发送 Telegram 链接\n"
    welcome_text += "👁 **监控频道/群组** - 自动转发新消息\n"
    welcome_text += "🔍 **智能过滤** - 关键词、正则表达式过滤\n"
    welcome_text += "🎯 **提取模式** - 提取特定内容转发\n\n"
    welcome_text += "点击下方按钮开始使用 👇"

    bot.send_message(message.chat.id, welcome_text, reply_markup=keyboard, reply_to_message_id=message.id)

# help command
@bot.on_message(filters.command(["help"]))
def send_help(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 监控管理", callback_data="menu_watch")],
        [InlineKeyboardButton("🏠 返回主菜单", callback_data="menu_main")]
    ])

    help_text = """**📖 使用帮助**

**📥 转发消息**
直接发送 Telegram 消息链接即可转发内容

**📋 监控功能**
• 点击"监控管理"按钮设置自动转发或记录
• 支持监控频道、群组和收藏夹
• 输入 `me` 可监控自己的收藏夹
• 支持关键词过滤（白名单/黑名单）
• 支持正则表达式过滤
• 支持提取模式（正则提取特定内容）
• 可选择是否保留转发来源
• 📝 支持记录模式（保存到网页笔记）
• 可随时编辑监控设置

**📝 记录模式**
• 将监控内容保存到网页而非转发
• 记录文字、图片和视频封面
• 包含时间戳信息
• 过滤规则和提取模式仍然生效
• 通过 Web 界面查看记录（端口 5000）
• 默认登录账号：admin/admin
• 搜索功能支持高亮显示

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
• 可以使用 `me` 监控收藏夹或作为目标
• 关键词过滤不区分大小写
• 正则表达式支持完整的 Python re 语法
• 提取模式会将匹配的内容单独发送
• 所有操作都可通过按钮完成，无需记忆复杂命令
• 机器人重启后会自动加载所有配置
"""
    bot.send_message(message.chat.id, help_text, reply_markup=keyboard, reply_to_message_id=message.id)

# watch command
@bot.on_message(filters.command(["watch"]))
def watch_command(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    if acc is None:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 返回主菜单", callback_data="menu_main")]])
        bot.send_message(message.chat.id, "**❌ 需要配置 String Session 才能使用监控功能**", reply_markup=keyboard, reply_to_message_id=message.id)
        return

    show_watch_menu(message.chat.id, message.id)

def show_watch_menu(chat_id, reply_to_message_id=None):
    watch_config = config.load_watch_config()
    user_id = str(chat_id)

    watch_count = len(watch_config.get(user_id, {}))

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ 添加监控", callback_data="watch_add_start")],
        [InlineKeyboardButton(f"📋 查看列表 ({watch_count})", callback_data="watch_list")],
        [InlineKeyboardButton("🗑 删除监控", callback_data="watch_remove_start")],
        [InlineKeyboardButton("🏠 返回主菜单", callback_data="menu_main")]
    ])

    text = "**📋 监控管理**\n\n"
    text += "选择操作：\n\n"
    text += "➕ **添加监控** - 设置新的自动转发任务\n"
    text += "📋 **查看列表** - 查看所有监控任务\n"
    text += "🗑 **删除监控** - 移除现有监控任务\n\n"
    text += f"当前监控任务数：**{watch_count}** 个"

    bot.send_message(chat_id, text, reply_markup=keyboard, reply_to_message_id=reply_to_message_id)

# 导入原有的callback_handler和其他处理函数
# 这里保留原有的UI交互逻辑，只修改自动转发部分
from main import (
    callback_handler,
    show_filter_options,
    show_filter_options_single,
    show_preserve_source_options,
    show_forward_mode_options,
    complete_watch_setup,
    complete_watch_setup_single,
    handle_add_source,
    handle_add_dest,
    save,
    handle_private,
    get_message_type
)

# 注册callback handler
bot.on_callback_query()(callback_handler)

# 注册文本消息handler
bot.on_message(filters.text & filters.private & ~filters.command(["start", "help", "watch"]))(save)

# 自动转发处理器 - 使用重构后的服务
if acc is not None:
    @acc.on_message(filters.channel | filters.group | filters.private)
    def auto_forward(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
        try:
            # 确保peer已解析
            try:
                if message.chat.id:
                    acc.get_chat(message.chat.id)
            except Exception as e:
                print(f"⚠️ 无法解析 peer {message.chat.id}: {e}")
                return

            watch_config_dict = config.load_watch_config()
            source_chat_id = str(message.chat.id)

            print(f"\n{'='*60}")
            print(f"📨 收到新消息")
            print(f"   来源: {message.chat.title or message.chat.username or source_chat_id}")
            print(f"   消息ID: {message.id}")
            print(f"{'='*60}")

            # 遍历所有用户的监控任务
            for user_id, watches in watch_config_dict.items():
                for watch_key, watch_data in watches.items():
                    # 检查是否匹配来源
                    if isinstance(watch_data, dict):
                        task_source = watch_data.get("source", watch_key.split("|")[0] if "|" in watch_key else watch_key)

                        if task_source is None or task_source != source_chat_id:
                            continue

                        record_mode = watch_data.get("record_mode", False)

                        print(f"\n✅ 匹配到监控任务")
                        print(f"   用户ID: {user_id}")
                        print(f"   模式: {'📝 记录模式' if record_mode else '📤 转发模式'}")

                        # 获取消息文本
                        message_text = message.text or message.caption or ""

                        # 应用过滤规则
                        if not filter_service.should_process_message(message_text, watch_data):
                            print(f"   ⏭️ 消息被过滤规则拒绝")
                            continue

                        print(f"   ✅ 消息通过过滤规则")

                        # 根据模式处理消息
                        if record_mode:
                            # 记录模式
                            if record_service:
                                success = record_service.record_message(message, int(user_id), watch_data)
                                if success:
                                    print(f"   ✅ 消息已记录到数据库")
                                else:
                                    print(f"   ❌ 消息记录失败")
                            else:
                                print(f"   ❌ 记录服务未初始化")
                        else:
                            # 转发模式
                            if forward_service:
                                success = forward_service.forward_message(message, watch_data)
                                if success:
                                    print(f"   ✅ 消息已转发")
                                else:
                                    print(f"   ❌ 消息转发失败")
                            else:
                                print(f"   ❌ 转发服务未初始化")
                    else:
                        # 旧格式兼容
                        if watch_key != source_chat_id:
                            continue

                        print(f"\n⚠️ 检测到旧格式配置，建议更新")
                        print(f"   用户ID: {user_id}")

        except Exception as e:
            print(f"\n❌ 自动转发处理器错误:")
            print(f"   错误类型: {type(e).__name__}")
            print(f"   错误信息: {str(e)}")
            import traceback
            traceback.print_exc()

# 启动时打印配置信息
def print_startup_config():
    print("\n" + "="*60)
    print("🤖 Telegram Save-Restricted Bot 启动成功（重构版）")
    print("="*60)

    watch_config_dict = config.load_watch_config()
    if not watch_config_dict:
        print("\n📋 当前没有监控任务")
    else:
        total_tasks = sum(len(watches) for watches in watch_config_dict.values())
        print(f"\n📋 已加载 {len(watch_config_dict)} 个用户的 {total_tasks} 个监控任务：\n")

        # 收集所有需要预缓存的频道ID
        source_ids_to_cache = set()

        for user_id, watches in watch_config_dict.items():
            print(f"👤 用户 {user_id}:")
            for watch_key, watch_data in watches.items():
                if isinstance(watch_data, dict):
                    source_id = watch_data.get("source", watch_key.split("|")[0] if "|" in watch_key else watch_key)
                    dest_id = watch_data.get("dest", "未知")
                    record_mode = watch_data.get("record_mode", False)

                    if source_id is None:
                        source_id = "未知来源"
                    if dest_id is None:
                        dest_id = "未知目标"

                    # 添加到缓存列表
                    if source_id not in ["未知来源", "me"] and source_id:
                        try:
                            chat_id_int = int(source_id)
                            if chat_id_int < 0:
                                source_ids_to_cache.add(source_id)
                        except (ValueError, TypeError):
                            pass

                    if record_mode:
                        print(f"   📝 {source_id} → 记录模式")
                    else:
                        print(f"   📤 {source_id} → {dest_id}")
                else:
                    source_display = watch_key if watch_key is not None else "未知来源"
                    dest_display = watch_data if watch_data is not None else "未知目标"

                    if watch_key not in ["未知来源", "me", None] and watch_key:
                        try:
                            chat_id_int = int(watch_key)
                            if chat_id_int < 0:
                                source_ids_to_cache.add(watch_key)
                        except (ValueError, TypeError):
                            pass

                    print(f"   📤 {source_display} → {dest_display}")
            print()

        # 预缓存频道信息
        if acc is not None and source_ids_to_cache:
            print("🔄 预加载频道信息到缓存...")
            cached_count = 0
            for source_id in source_ids_to_cache:
                try:
                    acc.get_chat(int(source_id))
                    cached_count += 1
                    print(f"   ✅ 已缓存: {source_id}")
                except Exception as e:
                    print(f"   ⚠️ 无法缓存 {source_id}: {str(e)}")
            print(f"📦 成功缓存 {cached_count}/{len(source_ids_to_cache)} 个频道\n")

    print("="*60)
    print("✅ 机器人已就绪，正在监听消息...")
    print("="*60 + "\n")

# 打印启动配置
print_startup_config()

# 启动机器人
print("\n🚀 启动机器人...")
bot.run()

# 停止用户账号客户端
if acc is not None:
    acc.stop()
    print("✅ 用户账号客户端已停止")
