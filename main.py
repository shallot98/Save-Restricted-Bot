"""
Save-Restricted-Bot - Telegram Bot for Saving Restricted Content
Main entry point - coordinates all modules
"""
import pyrogram
from pyrogram import Client, filters
from pyrogram.errors import UserAlreadyParticipant, InviteHashExpired, UsernameNotOccupied, ChannelPrivate, UsernameInvalid, FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

import threading
import queue
import logging

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Import configuration management
from config import (
    load_config, getenv, load_watch_config, save_watch_config,
    build_monitored_sources, reload_monitored_sources, get_monitored_sources,
    DATA_DIR, CONFIG_DIR, MEDIA_DIR
)

# Import database
from database import init_database

# Import bot utilities
from bot.utils import (
    is_message_processed, mark_message_processed, cleanup_old_messages,
    user_states, cached_dest_peers
)
from bot.utils.peer import cache_peer, is_dest_cached, mark_dest_cached, mark_peer_failed, get_failed_peers
from bot.utils.progress import progress, downstatus, upstatus

# Import workers
from bot.workers import MessageWorker, Message

# Import handlers
from bot.handlers import set_bot_instance, set_acc_instance
from bot.handlers.commands import register_command_handlers, show_watch_menu

# Load main configuration
DATA = load_config()

# Get configuration values
bot_token = getenv("TOKEN", DATA)
api_hash = getenv("HASH", DATA)
api_id = getenv("ID", DATA)

# Create bot client
bot = Client("mybot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

# Create user client if session string available
ss = getenv("STRING", DATA)
if ss is not None:
    if DATA.get("STRING"):
        logger.info("✅ 使用 config.json 中的 session string")
    else:
        logger.info("✅ 使用环境变量 STRING 中的 session string")

    # 先尝试使用已有的 session 文件（包含 Peer 缓存）
    import os
    os.makedirs("sessions", exist_ok=True)
    session_file = "sessions/myacc"
    if os.path.exists(f"{session_file}.session"):
        logger.info("📂 发现已有 Session 文件，将保留 Peer 缓存")
        acc = Client(session_file, api_id=api_id, api_hash=api_hash)
    else:
        logger.info("📝 首次启动，使用 Session String 创建 Session 文件")
        acc = Client(session_file, api_id=api_id, api_hash=api_hash, session_string=ss)

    acc.start()
else:
    logger.warning("⚠️ 未找到 session string，acc 客户端未初始化")
    acc = None

# Set handler instances for use by modules
set_bot_instance(bot)
set_acc_instance(acc)

# Initialize message queue and worker thread
from constants import MAX_RETRIES

message_queue = queue.Queue()
message_worker = None
worker_thread = None

if acc is not None:
    message_worker = MessageWorker(message_queue, acc, max_retries=MAX_RETRIES)
    worker_thread = threading.Thread(target=message_worker.run, daemon=True, name="MessageWorker")
    worker_thread.start()
    logger.info("✅ 消息队列和工作线程已初始化")

# Register command handlers
register_command_handlers(bot, acc)

# Import handlers from new modular structure
from bot.handlers.callbacks import callback_handler
from bot.handlers.messages import save, handle_private
from bot.handlers.watch_setup import (
    show_filter_options, show_filter_options_single,
    show_preserve_source_options, show_forward_mode_options,
    complete_watch_setup, complete_watch_setup_single,
    handle_add_source, handle_add_dest
)
from bot.utils.helpers import get_message_type
from constants import USAGE

# Register callback handler
@bot.on_callback_query()
def handle_callback(client, callback_query):
    callback_handler(client, callback_query)

# Register message handler for private messages
@bot.on_message(filters.text & filters.private & ~filters.command(["start", "help", "watch"]))
def handle_save(client, message):
    save(client, message)

# Register auto-forward handler (monitor)
if acc is not None:
    @acc.on_message((filters.channel | filters.group | filters.private) & (filters.incoming | filters.outgoing))
    def auto_forward(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
        """处理频道/群组/私聊消息，包括转发的消息"""
        try:
            # Validate message object and its attributes
            if not message or not hasattr(message, 'chat') or not message.chat:
                logger.debug("跳过：消息对象无效或缺少 chat 属性")
                return
            
            # Validate chat ID
            if not hasattr(message.chat, 'id') or message.chat.id is None:
                logger.debug("跳过：消息缺少有效的 chat ID")
                return
            
            # Check for duplicate messages
            if not hasattr(message, 'id') or message.id is None:
                logger.debug("跳过：消息缺少有效的 message ID")
                return
            
            if is_message_processed(message.id, message.chat.id):
                logger.debug(f"⏭️ 跳过已处理的消息: chat_id={message.chat.id}, message_id={message.id}")
                return
            
            # Mark message as processed immediately to prevent duplicate processing
            mark_message_processed(message.id, message.chat.id)
            
            # Periodically clean up old message records
            from bot.utils.dedup import processed_messages
            from constants import MESSAGE_CACHE_CLEANUP_THRESHOLD
            if len(processed_messages) > MESSAGE_CACHE_CLEANUP_THRESHOLD:
                cleanup_old_messages()
            
            # Log message type
            if message.outgoing:
                logger.debug(f"📤 outgoing消息（由Bot转发）: chat_id={message.chat.id}, message_id={message.id}")
            else:
                logger.debug(f"📥 incoming消息（外部来源）: chat_id={message.chat.id}, message_id={message.id}")
            
            # Get source chat ID
            source_chat_id = str(message.chat.id)
            
            # Early filter: check if this source is monitored
            monitored_sources = get_monitored_sources()
            if source_chat_id not in monitored_sources:
                return
            
            logger.info(f"🔔 监控源消息: chat_id={source_chat_id}, message_id={message.id}")
            
            # Cache source peer to avoid "Peer id invalid" errors
            if not is_dest_cached(source_chat_id):
                logger.info(f"🔄 源频道未缓存，尝试延迟加载: {source_chat_id}")
                success = cache_peer(acc, source_chat_id, "源频道")
                if not success:
                    logger.warning(f"⚠️ 延迟加载源频道失败，继续处理（记录模式不受影响）")
                else:
                    logger.info(f"✅ 延迟加载源频道成功: {source_chat_id}")
            
            # Get message text
            message_text = message.text or message.caption or ""
            
            # Find all matching watch configs
            watch_config = load_watch_config()
            enqueued_count = 0
            
            for user_id, watches in watch_config.items():
                for watch_key, watch_data in watches.items():
                    if isinstance(watch_data, dict):
                        watch_source = str(watch_data.get("source", ""))
                        dest = watch_data.get("dest")
                        record_mode = watch_data.get("record_mode", False)
                        
                        # Match source
                        if watch_source != source_chat_id:
                            continue
                        
                        logger.info(f"✅ 匹配到监控任务: user={user_id}, source={source_chat_id}")
                        
                        # Cache destination peer if in forward mode
                        dest_chat_id = dest if not record_mode else None
                        dest_peer_ready = True  # Assume ready for record mode
                        
                        if dest_chat_id and dest_chat_id != "me":
                            # Forward mode - must have destination peer cached
                            if not is_dest_cached(dest_chat_id):
                                logger.info(f"🔄 目标频道未缓存，尝试延迟加载: {dest_chat_id}")
                                success = cache_peer(acc, dest_chat_id, "目标频道")
                                if success:
                                    logger.info(f"✅ 延迟加载目标频道成功: {dest_chat_id}")
                                    dest_peer_ready = True
                                else:
                                    logger.error(f"❌ 延迟加载目标频道失败: {dest_chat_id}")
                                    logger.error(f"   消息将被跳过，等待下次重试（60秒后）")
                                    dest_peer_ready = False
                            else:
                                logger.debug(f"✓ 目标频道已缓存: {dest_chat_id}")
                        
                        # Skip enqueuing if destination peer is not ready for forward mode
                        if not dest_peer_ready:
                            logger.warning(f"⏭️ 跳过消息（目标频道未就绪）: user={user_id}, dest={dest_chat_id}")
                            continue
                        
                        # Media group deduplication
                        from bot.utils.dedup import is_media_group_processed, register_processed_media_group
                        
                        if message.media_group_id:
                            mode_suffix = "record" if record_mode else "forward"
                            media_group_key = f"{user_id}_{watch_key}_{dest_chat_id}_{mode_suffix}_{message.media_group_id}"
                            
                            if is_media_group_processed(media_group_key):
                                logger.debug(f"⏭️ 跳过已处理的媒体组: {media_group_key}")
                                continue
                            
                            # Register as processed
                            register_processed_media_group(media_group_key)
                            logger.info(f"📸 首次处理媒体组: {media_group_key}")
                        
                        # Create message object
                        msg_obj = Message(
                            user_id=user_id,
                            watch_key=watch_key,
                            message=message,
                            watch_data=watch_data,
                            source_chat_id=source_chat_id,
                            dest_chat_id=dest_chat_id,
                            message_text=message_text,
                            media_group_key=f"{user_id}_{watch_key}_{message.media_group_id}" if message.media_group_id else None
                        )
                        
                        # Enqueue message for processing
                        message_queue.put(msg_obj)
                        enqueued_count += 1
                        logger.info(f"📬 消息已入队: user={user_id}, source={source_chat_id}, 队列大小={message_queue.qsize()}")
            
            if enqueued_count > 0:
                logger.info(f"✅ 本次共入队 {enqueued_count} 条消息")
        
        except (ValueError, KeyError) as e:
            error_msg = str(e)
            if "Peer id invalid" not in error_msg and "ID not found" not in error_msg:
                logger.error(f"⚠️ auto_forward 错误: {type(e).__name__}: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"⚠️ auto_forward 意外错误: {type(e).__name__}: {e}", exc_info=True)


def _collect_source_ids(watch_config):
    """Collect source channel IDs that need to be cached"""
    source_ids = set()
    
    for user_id, watches in watch_config.items():
        for watch_key, watch_data in watches.items():
            if isinstance(watch_data, dict):
                source_id = watch_data.get("source", watch_key.split("|")[0] if "|" in watch_key else watch_key)
            else:
                source_id = watch_key
            
            # Add valid channel IDs (negative IDs, excluding special values)
            if source_id and source_id not in ["未知来源", "me"]:
                try:
                    if int(source_id) < 0:
                        source_ids.add(source_id)
                except (ValueError, TypeError):
                    pass
    
    return source_ids


def _collect_dest_ids(watch_config):
    """Collect destination channel IDs that need to be cached"""
    dest_ids = set()
    
    for user_id, watches in watch_config.items():
        for watch_key, watch_data in watches.items():
            if isinstance(watch_data, dict):
                dest_id = watch_data.get("dest")
                record_mode = watch_data.get("record_mode", False)
                
                # Only cache forward mode destinations
                if not record_mode and dest_id and dest_id != "me":
                    try:
                        int(dest_id)  # Validate it's a numeric ID
                        dest_ids.add(dest_id)
                    except (ValueError, TypeError):
                        pass
    
    return dest_ids


def _cache_channels(acc, channel_ids, channel_type="频道"):
    """Cache channel IDs to avoid Peer ID errors
    
    Args:
        acc: User client instance
        channel_ids: Set of channel IDs to cache
        channel_type: Type description for logging
        
    Returns:
        Tuple of (cached_count, total_count)
    """
    if not channel_ids:
        return 0, 0
    
    print(f"🔄 预加载{channel_type}信息到缓存...")
    cached_count = 0
    
    for channel_id in channel_ids:
        try:
            acc.get_chat(int(channel_id))
            cached_count += 1
            print(f"   ✅ 已缓存: {channel_id}")
        except Exception as e:
            print(f"   ⚠️ 无法缓存 {channel_id}: {str(e)}")
    
    print(f"📦 成功缓存 {cached_count}/{len(channel_ids)} 个{channel_type}\n")
    return cached_count, len(channel_ids)


def _cache_dest_peers(acc, dest_ids):
    """Cache destination peers with detailed information
    
    Args:
        acc: User client instance
        dest_ids: Set of destination IDs to cache
        
    Returns:
        Tuple of (cached_count, total_count, failed_list)
    """
    if not dest_ids:
        return 0, 0, []
    
    print("🔄 预加载目标Peer信息到缓存...")
    cached_count = 0
    failed_dests = []
    
    for dest_id in dest_ids:
        try:
            dest_chat = acc.get_chat(int(dest_id))
            cached_count += 1
            
            # Extract chat name
            if hasattr(dest_chat, 'first_name') and dest_chat.first_name:
                chat_name = dest_chat.first_name
            elif hasattr(dest_chat, 'title') and dest_chat.title:
                chat_name = dest_chat.title
            elif hasattr(dest_chat, 'username') and dest_chat.username:
                chat_name = dest_chat.username
            else:
                chat_name = "Unknown"
            
            is_bot = " 🤖" if hasattr(dest_chat, 'is_bot') and dest_chat.is_bot else ""
            print(f"   ✅ 已缓存目标: {dest_id} ({chat_name}{is_bot})")
            
            mark_dest_cached(dest_id)
        except FloodWait as e:
            print(f"   ⚠️ 限流: 目标 {dest_id}，等待 {e.value} 秒")
            failed_dests.append(dest_id)
            mark_peer_failed(dest_id)
        except Exception as e:
            print(f"   ⚠️ 无法缓存目标 {dest_id}: {str(e)}")
            failed_dests.append(dest_id)
            mark_peer_failed(dest_id)
    
    print(f"📦 成功缓存 {cached_count}/{len(dest_ids)} 个目标Peer")
    
    if failed_dests:
        print(f"💡 缓存失败的目标（共{len(failed_dests)}个）: {', '.join(failed_dests)}")
        print(f"   这些目标将在接收到第一条消息时自动重试延迟加载\n")
    else:
        print()
    
    return cached_count, len(dest_ids), failed_dests


def initialize_peer_cache_on_startup_with_retry(acc, max_retries=3):
    """带重试的Peer缓存初始化
    
    确保acc完全连接后再初始化缓存，如果失败自动重试
    
    Args:
        acc: User client instance
        max_retries: Maximum number of retry attempts (default: 3)
        
    Returns:
        bool: True if all peers cached successfully, False otherwise
    """
    import time
    
    try:
        watch_config = load_watch_config()
        all_peers = set()
        
        # 第一步：收集所有源和目标频道ID
        for user_id, watches in watch_config.items():
            for watch_key, watch_data in watches.items():
                if isinstance(watch_data, dict):
                    source_id = watch_data.get("source")
                    dest_id = watch_data.get("dest")
                    
                    if source_id:
                        try:
                            all_peers.add(int(source_id))
                        except (ValueError, TypeError):
                            pass
                    
                    if dest_id and dest_id != "me":
                        try:
                            all_peers.add(int(dest_id))
                        except (ValueError, TypeError):
                            pass
        
        if not all_peers:
            logger.info("📭 没有配置的Peer需要初始化")
            return True
        
        # 尝试初始化，最多重试 max_retries 次
        for attempt in range(max_retries):
            try:
                logger.info("="*60)
                logger.info(f"⚡ 第 {attempt+1}/{max_retries} 次初始化 {len(all_peers)} 个Peer缓存...")
                logger.info("="*60)
                
                success_count = 0
                failed_peers = []
                
                for peer_id in sorted(all_peers):
                    try:
                        # 关键：get_chat() 会初始化Peer缓存
                        chat = acc.get_chat(peer_id)
                        success_count += 1
                        
                        # Extract chat name
                        if hasattr(chat, 'title') and chat.title:
                            chat_name = chat.title
                        elif hasattr(chat, 'first_name') and chat.first_name:
                            chat_name = chat.first_name
                        elif hasattr(chat, 'username') and chat.username:
                            chat_name = f"@{chat.username}"
                        else:
                            chat_name = "Unknown"
                        
                        # Check if bot
                        is_bot = " 🤖" if hasattr(chat, 'is_bot') and chat.is_bot else ""
                        
                        logger.info(f"   ✅ {peer_id}: {chat_name}{is_bot}")
                        
                        # Mark as cached in our tracking system
                        mark_dest_cached(str(peer_id))
                        
                    except Exception as e:
                        error_msg = str(e)[:60]
                        failed_peers.append((peer_id, error_msg))
                        logger.warning(f"   ⚠️ {peer_id}: {error_msg}")
                
                logger.info("="*60)
                logger.info(f"✅ Peer缓存初始化完成: {success_count}/{len(all_peers)} 成功")
                
                # 如果全部成功，返回
                if success_count == len(all_peers):
                    logger.info("="*60)
                    logger.info("")
                    return True
                
                # 如果部分失败，显示诊断信息
                if failed_peers:
                    logger.warning(f"⚠️ 失败的Peer (共{len(failed_peers)}个):")
                    for peer_id, error in failed_peers:
                        logger.warning(f"   - {peer_id}: {error}")
                        mark_peer_failed(str(peer_id))
                
                # 如果还有重试机会，等待后重试
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logger.info(f"⏳ 等待 {wait_time} 秒后重试（还有 {max_retries - attempt - 1} 次机会）...")
                    logger.info("="*60)
                    logger.info("")
                    time.sleep(wait_time)
                else:
                    logger.info(f"💡 失败的Peer将在接收到第一条消息时自动重试延迟加载")
                    logger.info("="*60)
                    logger.info("")
                
            except Exception as e:
                logger.error(f"❌ 初始化异常: {e}", exc_info=True)
                
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logger.info(f"⏳ 异常后等待 {wait_time} 秒再试...")
                    logger.info("="*60)
                    logger.info("")
                    time.sleep(wait_time)
        
        logger.warning(f"⚠️ 达到最大重试次数 ({max_retries})，Peer缓存初始化未能完全完成")
        logger.info("")
        return False
        
    except Exception as e:
        logger.error(f"❌ Peer缓存初始化失败: {e}", exc_info=True)
        return False


def import_watch_config_on_startup(acc):
    """在启动时导入配置，复用手动添加的逻辑
    
    该函数模拟手动添加监控时的初始化流程，确保使用相同的代码路径
    """
    import time
    
    logger.info("="*60)
    logger.info("🔄 开始导入监控配置...")
    logger.info("="*60)
    
    try:
        watch_config = load_watch_config()
        
        if not watch_config:
            logger.info("📭 没有监控配置需要导入")
            return True
        
        # 统计配置数量
        total_configs = sum(len(watches) for watches in watch_config.values())
        logger.info(f"📋 找到 {total_configs} 个监控配置")
        
        success_count = 0
        failed_count = 0
        
        for user_id, watches in watch_config.items():
            logger.info(f"\n👤 用户 {user_id} 的配置:")
            
            for watch_key, watch_data in watches.items():
                try:
                    # 解析配置
                    if isinstance(watch_data, dict):
                        source_id = watch_data.get("source")
                        dest_id = watch_data.get("dest")
                        record_mode = watch_data.get("record_mode", False)
                    else:
                        # 旧格式兼容
                        source_id = watch_key
                        dest_id = watch_data
                        record_mode = False
                    
                    # 记录配置信息（不强制初始化，改为延迟加载）
                    if source_id and source_id != "me":
                        logger.info(f"   📌 源频道: {source_id} (将在收到消息时自动初始化)")

                    if not record_mode and dest_id and dest_id != "me":
                        logger.info(f"   📌 目标频道: {dest_id} (将在转发时自动初始化)")
                    elif record_mode:
                        logger.info(f"   📝 目标: 记录模式")
                    
                    
                    success_count += 1
                    
                except Exception as e:
                    logger.error(f"   ❌ 配置导入失败 {watch_key}: {str(e)}")
                    failed_count += 1
                
                # 避免触发限流，添加小延迟
                time.sleep(0.2)
        
        logger.info("")
        logger.info("="*60)
        logger.info(f"✅ 配置导入完成: {success_count}/{total_configs} 成功")
        
        if failed_count > 0:
            logger.warning(f"⚠️ {failed_count} 个配置初始化失败，将在接收消息时自动重试")
        
        logger.info("="*60)
        logger.info("")
        
        return success_count > 0
        
    except Exception as e:
        logger.error(f"❌ 导入配置时发生错误: {e}", exc_info=True)
        return False


def _print_watch_tasks(watch_config):
    """Print configured watch tasks"""
    record_mode_count = sum(
        1 for watches in watch_config.values()
        for watch_data in watches.values()
        if isinstance(watch_data, dict) and watch_data.get("record_mode", False)
    )
    
    if record_mode_count > 0:
        print(f"🔍 配置的记录模式任务: {record_mode_count} 个\n")
    
    for user_id, watches in watch_config.items():
        print(f"👤 用户 {user_id}:")
        for watch_key, watch_data in watches.items():
            if isinstance(watch_data, dict):
                source_id = watch_data.get("source", watch_key.split("|")[0] if "|" in watch_key else watch_key)
                dest_id = watch_data.get("dest", "未知")
                record_mode = watch_data.get("record_mode", False)
                
                source_id = source_id or "未知来源"
                dest_id = dest_id or "未知目标"
                
                if record_mode:
                    print(f"   📝 {source_id} → 记录模式")
                else:
                    print(f"   📤 {source_id} → {dest_id}")
            else:
                source_display = watch_key or "未知来源"
                dest_display = watch_data or "未知目标"
                print(f"   📤 {source_display} → {dest_display}")
        print()


def print_startup_config():
    """Print startup configuration"""
    # ⚡ 启动时强制重新加载监控源，确保使用最新配置
    reload_monitored_sources()
    
    monitored = get_monitored_sources()
    logger.info(f"🔄 启动时已加载 {len(monitored)} 个监控源频道")
    
    print("\n" + "="*60)
    print("🤖 Telegram Save-Restricted Bot 启动成功")
    print("="*60)
    
    if acc is not None:
        print("\n🔧 消息队列系统已启用")
        print("   - 消息处理模式：队列 + 工作线程")
        from constants import MAX_RETRIES
        print(f"   - 最大重试次数：{MAX_RETRIES} 次")
        print("   - 自动故障恢复：是")
    
    watch_config = load_watch_config()
    if not watch_config:
        print("\n📋 当前没有监控任务")
    else:
        total_tasks = sum(len(watches) for watches in watch_config.values())
        print(f"\n📋 已加载 {len(watch_config)} 个用户的 {total_tasks} 个监控任务：\n")
        
        # Print watch tasks
        _print_watch_tasks(watch_config)
        
        # 启动时自动导入配置 - 复用手动添加的逻辑
        if acc is not None:
            import time
            print("")  # 空行分隔
            logger.info("⏳ 等待Session完全建立...")
            time.sleep(8)

            # 使用简化的导入逻辑，复用手动添加的代码路径
            import_watch_config_on_startup(acc)
    
    print("\n" + "="*60)
    print("✅ 机器人已就绪，正在监听消息...")
    print("="*60 + "\n")


# Initialize database
print("\n🔧 初始化数据库系统...")
try:
    init_database()
except Exception as e:
    print(f"⚠️ 数据库初始化时发生错误: {e}")
    print("⚠️ 继续启动，但记录模式可能无法工作")

# Print startup configuration
print_startup_config()

# Start bot
bot.run()
if acc is not None:
    acc.stop()
