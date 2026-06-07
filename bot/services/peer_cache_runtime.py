"""Lazy peer cache loading used during message processing."""

import time
from dataclasses import dataclass

from pyrogram.errors import FloodWait

from bot.utils.logger import get_logger
from bot.utils.peer import failed_peers, mark_dest_cached, mark_peer_failed, should_retry_peer
from bot.services.peer_cache_common import (
    BOT_CONNECTION_WAIT_SECONDS,
    chat_display_name,
    bot_suffix,
    dialog_search_limit,
    is_peer_invalid_error,
    peer_display_name,
)

logger = get_logger(__name__)


@dataclass(frozen=True)
class PeerCacheContext:
    client: object
    peer_id: object
    peer_type: str
    peer_id_str: str
    peer_id_int: int


def cache_peer_if_needed(acc, peer_id, peer_type="频道"):
    """Cache a Telegram peer if Pyrogram has not loaded it into the session."""
    context = PeerCacheContext(acc, peer_id, peer_type, str(peer_id), int(peer_id))
    if _cooldown_blocks_retry(context):
        return False
    return _try_cached_chat(context)


def _cooldown_blocks_retry(context):
    if should_retry_peer(context.peer_id_str):
        return False

    elapsed = time.time() - failed_peers.get(context.peer_id_str, 0)
    remaining = 60 - elapsed
    logger.debug(f"⏳ {context.peer_type} {context.peer_id} 在冷却期，还需 {remaining:.0f}秒")
    return True


def _try_cached_chat(context):
    try:
        chat = context.client.get_chat(context.peer_id_int)
        _log_cache_success(context, chat)
        return True
    except FloodWait as error:
        logger.warning(f"⚠️ 限流: {context.peer_type} {context.peer_id}，等待 {error.value} 秒")
        mark_peer_failed(context.peer_id_str)
        return False
    except Exception as error:
        return _handle_cache_failure(context, str(error))


def _log_cache_success(context, chat):
    name = chat_display_name(chat)
    logger.info(f"✅ {context.peer_type}缓存成功: {context.peer_id} ({name}{bot_suffix(chat)})")
    mark_dest_cached(context.peer_id_str)


def _handle_cache_failure(context, error_msg):
    logger.error(f"❌ 延迟加载{context.peer_type}失败: {context.peer_id} - {error_msg}")
    if is_peer_invalid_error(error_msg) and _recover_invalid_peer(context):
        return True

    mark_peer_failed(context.peer_id_str)
    return False


def _recover_invalid_peer(context):
    if context.peer_id_int > 0 and _try_positive_peer_recovery(context):
        return True
    return _try_dialog_recovery(context)


def _try_positive_peer_recovery(context):
    logger.info(f"🤖 检测到用户/Bot ID: {context.peer_id}，尝试建立连接...")
    if _try_resolve_peer(context):
        return True
    return _try_start_bot(context)


def _try_resolve_peer(context):
    try:
        logger.debug("   方法1: 尝试resolve_peer...")
        context.client.resolve_peer(context.peer_id_int)
        logger.info(f"✅ resolve_peer成功: {context.peer_id}")
        chat = context.client.get_chat(context.peer_id_int)
        _log_peer_connection(context, chat, "✅ Peer连接已建立")
        return True
    except Exception as error:
        logger.debug(f"   方法1失败: {error}")
        return False


def _try_start_bot(context):
    try:
        logger.debug("   方法2: 尝试发送/start命令...")
        context.client.send_message(context.peer_id_int, "/start")
        logger.info(f"✅ 已向Bot发送/start命令: {context.peer_id}")
        time.sleep(BOT_CONNECTION_WAIT_SECONDS)
        chat = context.client.get_chat(context.peer_id_int)
        _log_peer_connection(context, chat, "✅ Bot Peer连接已建立")
        return True
    except Exception as error:
        logger.debug(f"   方法2失败: {error}")
        return False


def _log_peer_connection(context, chat, prefix):
    logger.info(f"{prefix}: {context.peer_id} ({peer_display_name(chat)}{bot_suffix(chat)})")
    mark_dest_cached(context.peer_id_str)


def _try_dialog_recovery(context):
    logger.info(f"🔄 尝试通过对话列表建立Peer连接: {context.peer_id}")
    try:
        return _recover_from_dialogs(context)
    except Exception as error:
        logger.error(f"❌ 通过对话列表建立连接失败: {error}")
        return False


def _recover_from_dialogs(context):
    search_limit = dialog_search_limit(context.peer_type)
    logger.debug(f"   方法3: 搜索对话列表（前 {search_limit} 个）...")
    for dialog in context.client.get_dialogs(limit=search_limit):
        if dialog.chat.id != context.peer_id_int:
            continue
        return _confirm_dialog_peer(context, dialog.chat)

    _log_dialog_peer_missing(context)
    return False


def _confirm_dialog_peer(context, dialog_chat):
    name = chat_display_name(dialog_chat)
    logger.info(f"✅ 在对话列表中找到Peer: {context.peer_id} ({name})")
    try:
        context.client.get_chat(context.peer_id_int)
        logger.info("✅ Peer连接已建立")
        mark_dest_cached(context.peer_id_str)
        return True
    except Exception as error:
        logger.warning(f"⚠️ 获取chat信息失败: {error}")
        return False


def _log_dialog_peer_missing(context):
    logger.warning(f"⚠️ 在对话列表中未找到Peer: {context.peer_id}")
    if context.peer_id_int > 0:
        logger.warning("💡 对于Bot用户，请确保Bot已启动且可访问")
        logger.warning("💡 或者手动向Bot发送一条消息后重启")
        return
    if context.peer_type in ["下一级目标", "目标频道"]:
        logger.warning("💡 对于私聊用户，请确保该用户已与账号建立过对话")
        return
    logger.warning("💡 请确保账号已加入该频道/群组")
