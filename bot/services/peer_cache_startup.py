"""Startup peer cache initialization."""

import time
from dataclasses import dataclass

from bot.utils.logger import get_logger
from bot.utils.peer import mark_dest_cached, mark_peer_failed
from bot.services.peer_cache_common import (
    BOT_CONNECTION_WAIT_SECONDS,
    FAILED_ERROR_MAX_LENGTH,
    RETRY_WAIT_SECONDS,
    bot_suffix,
    chat_display_name,
    is_peer_invalid_error,
    peer_display_name,
)
from config import load_watch_config

logger = get_logger(__name__)


@dataclass(frozen=True)
class StartupPeerResult:
    success: bool
    error_msg: str = ""


@dataclass(frozen=True)
class StartupAttemptResult:
    success_count: int
    failed_peers: tuple[tuple[int, str], ...]


def initialize_peer_cache_on_startup_with_retry(acc, max_retries=3):
    """Initialize configured Telegram peers with retry."""
    try:
        all_peers, user_peers = _collect_configured_peers(load_watch_config())
        if not all_peers:
            logger.info("📭 没有配置的Peer需要初始化")
            return True

        _log_configured_users(user_peers)
        return _retry_startup_initialization(acc, all_peers, max_retries)
    except Exception as error:
        logger.error(f"❌ Peer缓存初始化失败: {error}", exc_info=True)
        return False


def _collect_configured_peers(watch_config):
    all_peers = set()
    user_peers = set()
    for peer_id in _iter_configured_peer_ids(watch_config):
        all_peers.add(peer_id)
        if peer_id > 0:
            user_peers.add(peer_id)
    return all_peers, user_peers


def _iter_configured_peer_ids(watch_config):
    for watch_data in _iter_configured_watch_data(watch_config):
        for raw_peer_id in _configured_peer_values(watch_data):
            peer_id = _parse_peer_id(raw_peer_id)
            if peer_id is not None:
                yield peer_id


def _iter_configured_watch_data(watch_config):
    for watches in watch_config.values():
        for watch_data in watches.values():
            if isinstance(watch_data, dict):
                yield watch_data


def _configured_peer_values(watch_data):
    source_id = watch_data.get("source")
    dest_id = watch_data.get("dest")
    if source_id:
        yield source_id
    if dest_id and dest_id != "me":
        yield dest_id


def _parse_peer_id(raw_peer_id):
    try:
        return int(raw_peer_id)
    except (ValueError, TypeError):
        return None


def _log_configured_users(user_peers):
    if not user_peers:
        return
    logger.info(f"💡 检测到 {len(user_peers)} 个私聊用户配置")
    logger.info(f"   私聊用户ID: {sorted(user_peers)}")


def _retry_startup_initialization(acc, all_peers, max_retries):
    for attempt in range(max_retries):
        if _run_startup_attempt(acc, all_peers, attempt, max_retries=max_retries):
            return True

    logger.warning(f"⚠️ 达到最大重试次数 ({max_retries})，Peer缓存初始化未能完全完成")
    logger.info("")
    return False


def _run_startup_attempt(acc, all_peers, attempt, *, max_retries):
    try:
        _log_startup_attempt_header(attempt, max_retries, len(all_peers))
        result = _initialize_peer_cache_attempt(acc, all_peers)
        return _handle_startup_attempt_result(result, len(all_peers), attempt, max_retries=max_retries)
    except Exception as error:
        _handle_startup_attempt_exception(error, attempt, max_retries)
        return False


def _log_startup_attempt_header(attempt, max_retries, peer_count):
    logger.info("=" * 60)
    logger.info(f"⚡ 第 {attempt + 1}/{max_retries} 次初始化 {peer_count} 个Peer缓存...")
    logger.info("=" * 60)


def _initialize_peer_cache_attempt(acc, all_peers):
    success_count = 0
    failed_peers = []
    for peer_id in sorted(all_peers):
        result = _try_startup_peer_cache(acc, peer_id)
        if result.success:
            success_count += 1
            continue
        failed_peers.append((peer_id, result.error_msg[:FAILED_ERROR_MAX_LENGTH]))
        logger.warning(f"   ⚠️ {peer_id}: {result.error_msg[:FAILED_ERROR_MAX_LENGTH]}")
    return StartupAttemptResult(success_count, tuple(failed_peers))


def _try_startup_peer_cache(acc, peer_id):
    try:
        chat = acc.get_chat(peer_id)
        _log_startup_peer_cached(peer_id, chat)
        return StartupPeerResult(True)
    except Exception as error:
        error_msg = str(error)
        if is_peer_invalid_error(error_msg) and _recover_startup_invalid_peer(acc, peer_id):
            return StartupPeerResult(True)
        return StartupPeerResult(False, error_msg)


def _log_startup_peer_cached(peer_id, chat):
    logger.info(f"   ✅ {peer_id}: {chat_display_name(chat)}{bot_suffix(chat)}")
    mark_dest_cached(str(peer_id))


def _recover_startup_invalid_peer(acc, peer_id):
    logger.info(f"   🔍 尝试通过对话列表查找: {peer_id}")
    try:
        if _try_startup_peer_from_dialogs(acc, peer_id):
            return True
        return peer_id > 0 and _try_startup_bot_connection(acc, peer_id)
    except Exception as error:
        logger.debug(f"   对话列表查找失败: {error}")
        return False


def _try_startup_peer_from_dialogs(acc, peer_id):
    for dialog in acc.get_dialogs():
        if dialog.chat.id != peer_id:
            continue
        _log_startup_dialog_peer(peer_id, dialog.chat)
        return True
    return False


def _log_startup_dialog_peer(peer_id, chat):
    logger.info(f"   ✅ {peer_id}: {chat_display_name(chat)}{bot_suffix(chat)} (通过对话列表)")
    mark_dest_cached(str(peer_id))


def _try_startup_bot_connection(acc, peer_id):
    logger.info(f"   🤖 尝试自动建立Bot连接: {peer_id}")
    try:
        acc.send_message(peer_id, "/start")
        time.sleep(BOT_CONNECTION_WAIT_SECONDS)
        chat = acc.get_chat(peer_id)
        logger.info(f"   ✅ {peer_id}: {peer_display_name(chat)}{bot_suffix(chat)} (自动建立)")
        mark_dest_cached(str(peer_id))
        return True
    except Exception as error:
        logger.debug(f"   自动建立失败: {error}")
        return False


def _handle_startup_attempt_result(result, peer_count, attempt, *, max_retries):
    logger.info("=" * 60)
    logger.info(f"✅ Peer缓存初始化完成: {result.success_count}/{peer_count} 成功")
    if result.success_count == peer_count:
        logger.info("=" * 60)
        logger.info("")
        return True

    _log_failed_startup_peers(result.failed_peers)
    _wait_or_log_startup_exhausted(attempt, max_retries)
    return False


def _log_failed_startup_peers(failed_peers):
    if not failed_peers:
        return
    logger.warning(f"⚠️ 失败的Peer (共{len(failed_peers)}个):")
    failed_users = []
    for peer_id, error in failed_peers:
        logger.warning(f"   - {peer_id}: {error}")
        mark_peer_failed(str(peer_id))
        if peer_id > 0:
            failed_users.append(peer_id)
    _log_failed_user_hints(failed_users)


def _log_failed_user_hints(failed_users):
    if not failed_users:
        return
    logger.warning("")
    logger.warning(f"💡 私聊用户缓存失败 ({len(failed_users)}个):")
    logger.warning(f"   用户ID: {failed_users}")
    logger.warning("   解决方法：")
    logger.warning("   1. 让这些用户向账号发送一条消息")
    logger.warning("   2. 或者账号主动向这些用户发送一条消息")
    logger.warning("   3. 然后重启Bot")


def _wait_or_log_startup_exhausted(attempt, max_retries):
    if attempt < max_retries - 1:
        wait_time = (attempt + 1) * RETRY_WAIT_SECONDS
        logger.info(f"⏳ 等待 {wait_time} 秒后重试（还有 {max_retries - attempt - 1} 次机会）...")
        logger.info("=" * 60)
        logger.info("")
        time.sleep(wait_time)
        return
    logger.info("💡 失败的Peer将在接收到第一条消息时自动重试延迟加载")
    logger.info("=" * 60)
    logger.info("")


def _handle_startup_attempt_exception(error, attempt, max_retries):
    logger.error(f"❌ 初始化异常: {error}", exc_info=True)
    if attempt >= max_retries - 1:
        return
    wait_time = (attempt + 1) * RETRY_WAIT_SECONDS
    logger.info(f"⏳ 异常后等待 {wait_time} 秒再试...")
    logger.info("=" * 60)
    logger.info("")
    time.sleep(wait_time)
