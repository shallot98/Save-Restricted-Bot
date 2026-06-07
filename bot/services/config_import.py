"""
配置导入模块
职责：在启动时导入监控配置
"""
from dataclasses import dataclass
import time
from typing import Any

from bot.utils.logger import get_logger
from config import load_watch_config
from bot.services.peer_cache import initialize_peer_cache_on_startup_with_retry

logger = get_logger(__name__)

IMPORT_DELAY_SECONDS = 0.2
PEER_CACHE_MAX_RETRIES = 3


@dataclass(frozen=True)
class WatchImportEntry:
    source_id: Any
    dest_id: Any
    record_mode: bool


@dataclass(frozen=True)
class WatchImportSummary:
    total: int
    success: int
    failed: int


def import_watch_config_on_startup(acc):
    """
    在启动时导入配置，并初始化Peer缓存

    该函数会：
    1. 加载监控配置
    2. 自动初始化所有配置的Peer（包括Bot）
    3. 对于Bot用户，自动发送/start命令建立连接

    Args:
        acc: User客户端实例

    Returns:
        bool: 成功导入至少一个配置返回True，否则返回False
    """
    _log_import_start()
    try:
        watch_config = load_watch_config()
        if not watch_config:
            logger.info("📭 没有监控配置需要导入")
            return True

        summary = _import_watch_config_entries(watch_config)
        _log_import_summary(summary)
        _initialize_peer_cache(acc)
        return summary.success > 0
    except Exception as e:
        logger.error(f"❌ 导入配置时发生错误: {e}", exc_info=True)
        return False


def _log_import_start() -> None:
    logger.info("=" * 60)
    logger.info("🔄 开始导入监控配置...")
    logger.info("=" * 60)


def _import_watch_config_entries(watch_config: dict) -> WatchImportSummary:
    total_configs = sum(len(watches) for watches in watch_config.values())
    logger.info(f"📋 找到 {total_configs} 个监控配置")

    success_count = 0
    failed_count = 0
    for user_id, watches in watch_config.items():
        result = _import_user_watch_entries(user_id, watches)
        success_count += result.success
        failed_count += result.failed
    return WatchImportSummary(total_configs, success_count, failed_count)


def _import_user_watch_entries(user_id: str, watches: dict) -> WatchImportSummary:
    logger.info(f"\n👤 用户 {user_id} 的配置:")
    success_count = 0
    failed_count = 0
    for watch_key, watch_data in watches.items():
        if _log_watch_entry(watch_key, watch_data):
            success_count += 1
        else:
            failed_count += 1
        time.sleep(IMPORT_DELAY_SECONDS)
    return WatchImportSummary(len(watches), success_count, failed_count)


def _log_watch_entry(watch_key: str, watch_data: Any) -> bool:
    try:
        entry = _parse_watch_entry(watch_key, watch_data)
        _log_watch_entry_channels(entry)
        return True
    except Exception as e:
        logger.error(f"   ❌ 配置导入失败 {watch_key}: {str(e)}")
        return False


def _parse_watch_entry(watch_key: str, watch_data: Any) -> WatchImportEntry:
    if isinstance(watch_data, dict):
        return WatchImportEntry(
            source_id=watch_data.get("source"),
            dest_id=watch_data.get("dest"),
            record_mode=watch_data.get("record_mode", False),
        )
    return WatchImportEntry(source_id=watch_key, dest_id=watch_data, record_mode=False)


def _log_watch_entry_channels(entry: WatchImportEntry) -> None:
    if entry.source_id and entry.source_id != "me":
        logger.info(f"   📌 源频道: {entry.source_id}")

    if not entry.record_mode and entry.dest_id and entry.dest_id != "me":
        logger.info(f"   📌 目标频道: {entry.dest_id}")
    elif entry.record_mode:
        logger.info("   📝 目标: 记录模式")


def _log_import_summary(summary: WatchImportSummary) -> None:
    logger.info("")
    logger.info("=" * 60)
    logger.info(f"✅ 配置导入完成: {summary.success}/{summary.total} 成功")
    if summary.failed > 0:
        logger.warning(f"⚠️ {summary.failed} 个配置初始化失败")
    logger.info("=" * 60)
    logger.info("")


def _initialize_peer_cache(acc) -> None:
    logger.info("🔧 开始初始化Peer缓存...")
    initialize_peer_cache_on_startup_with_retry(acc, max_retries=PEER_CACHE_MAX_RETRIES)
