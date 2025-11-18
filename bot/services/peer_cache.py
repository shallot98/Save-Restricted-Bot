"""
Peer缓存管理模块
职责：管理Telegram Peer缓存，避免"Peer id invalid"错误
"""
import time
from pyrogram.errors import FloodWait
from bot.utils.logger import get_logger
from bot.utils.peer import mark_dest_cached, mark_peer_failed, is_dest_cached
from config import load_watch_config

logger = get_logger(__name__)


def cache_peer_if_needed(acc, peer_id, peer_type="频道"):
    """
    智能Peer缓存：利用Session文件的原生缓存机制

    策略：
    1. 直接尝试get_chat()，Session文件中有缓存就会成功
    2. 如果失败，说明Session中没有，需要重新缓存
    3. 使用内存标记避免频繁重试失败的Peer

    Args:
        acc: User客户端实例
        peer_id: Peer ID（字符串或整数）
        peer_type: Peer类型描述（用于日志）

    Returns:
        bool: 缓存成功返回True，失败返回False
    """
    peer_id_str = str(peer_id)

    # 检查是否在冷却期（避免频繁重试失败的Peer）
    from bot.utils.peer import should_retry_peer, mark_peer_failed, failed_peers
    if not should_retry_peer(peer_id_str):
        elapsed = time.time() - failed_peers.get(peer_id_str, 0)
        remaining = 60 - elapsed
        logger.debug(f"⏳ {peer_type} {peer_id} 在冷却期，还需 {remaining:.0f}秒")
        return False

    # 直接尝试获取chat信息（利用Session缓存）
    try:
        chat = acc.get_chat(int(peer_id))

        # 提取聊天名称
        if hasattr(chat, 'title') and chat.title:
            chat_name = chat.title
        elif hasattr(chat, 'first_name') and chat.first_name:
            chat_name = chat.first_name
        elif hasattr(chat, 'username') and chat.username:
            chat_name = f"@{chat.username}"
        else:
            chat_name = "Unknown"

        is_bot = " 🤖" if hasattr(chat, 'is_bot') and chat.is_bot else ""

        logger.info(f"✅ {peer_type}缓存成功: {peer_id} ({chat_name}{is_bot})")
        mark_dest_cached(peer_id_str)
        return True

    except FloodWait as e:
        logger.warning(f"⚠️ 限流: {peer_type} {peer_id}，等待 {e.value} 秒")
        mark_peer_failed(peer_id_str)
        return False

    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ 延迟加载{peer_type}失败: {peer_id} - {error_msg}")

        # 如果是PEER_ID_INVALID错误，尝试通过用户名建立连接
        if "PEER_ID_INVALID" in error_msg:
            logger.info(f"🔄 尝试通过用户名建立Peer连接: {peer_id}")
            try:
                # 尝试通过对话列表查找
                for dialog in acc.get_dialogs(limit=100):
                    if dialog.chat.id == int(peer_id):
                        logger.info(f"✅ 在对话列表中找到Peer: {peer_id}")
                        # 发送一条消息来建立连接
                        acc.send_message(int(peer_id), "🔗 建立Peer连接")
                        logger.info(f"✅ 已发送连接消息，Peer应该已缓存")
                        mark_dest_cached(peer_id_str)
                        return True

                logger.warning(f"⚠️ 在对话列表中未找到Peer: {peer_id}")
            except Exception as e2:
                logger.error(f"❌ 通过用户名建立连接失败: {e2}")

        mark_peer_failed(peer_id_str)
        return False


def initialize_peer_cache_on_startup_with_retry(acc, max_retries=3):
    """
    带重试的Peer缓存初始化

    确保acc完全连接后再初始化缓存，如果失败自动重试

    Args:
        acc: User客户端实例
        max_retries: 最大重试次数（默认: 3）

    Returns:
        bool: 全部缓存成功返回True，否则返回False
    """
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
                logger.info("=" * 60)
                logger.info(f"⚡ 第 {attempt+1}/{max_retries} 次初始化 {len(all_peers)} 个Peer缓存...")
                logger.info("=" * 60)

                success_count = 0
                failed_peers = []

                for peer_id in sorted(all_peers):
                    try:
                        # 关键：get_chat() 会初始化Peer缓存
                        chat = acc.get_chat(peer_id)
                        success_count += 1

                        # 提取聊天名称
                        if hasattr(chat, 'title') and chat.title:
                            chat_name = chat.title
                        elif hasattr(chat, 'first_name') and chat.first_name:
                            chat_name = chat.first_name
                        elif hasattr(chat, 'username') and chat.username:
                            chat_name = f"@{chat.username}"
                        else:
                            chat_name = "Unknown"

                        # 检查是否是Bot
                        is_bot = " 🤖" if hasattr(chat, 'is_bot') and chat.is_bot else ""

                        logger.info(f"   ✅ {peer_id}: {chat_name}{is_bot}")

                        # 标记为已缓存
                        mark_dest_cached(str(peer_id))

                    except Exception as e:
                        error_msg = str(e)[:60]
                        failed_peers.append((peer_id, error_msg))
                        logger.warning(f"   ⚠️ {peer_id}: {error_msg}")

                logger.info("=" * 60)
                logger.info(f"✅ Peer缓存初始化完成: {success_count}/{len(all_peers)} 成功")

                # 如果全部成功，返回
                if success_count == len(all_peers):
                    logger.info("=" * 60)
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
                    logger.info("=" * 60)
                    logger.info("")
                    time.sleep(wait_time)
                else:
                    logger.info(f"💡 失败的Peer将在接收到第一条消息时自动重试延迟加载")
                    logger.info("=" * 60)
                    logger.info("")

            except Exception as e:
                logger.error(f"❌ 初始化异常: {e}", exc_info=True)

                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logger.info(f"⏳ 异常后等待 {wait_time} 秒再试...")
                    logger.info("=" * 60)
                    logger.info("")
                    time.sleep(wait_time)

        logger.warning(f"⚠️ 达到最大重试次数 ({max_retries})，Peer缓存初始化未能完全完成")
        logger.info("")
        return False

    except Exception as e:
        logger.error(f"❌ Peer缓存初始化失败: {e}", exc_info=True)
        return False
