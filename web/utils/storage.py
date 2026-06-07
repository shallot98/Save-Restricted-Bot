"""
存储管理器初始化模块

遵循 SRP 原则：仅负责存储管理器的初始化逻辑
"""
import os
import logging
from database import DATA_DIR
from config import load_webdav_config
from bot.storage.webdav_client import WebDAVClient, StorageManager

logger = logging.getLogger(__name__)


def init_storage_manager() -> StorageManager:
    """初始化存储管理器

    优先尝试 WebDAV 存储，失败时回退到本地存储

    Returns:
        StorageManager: 存储管理器实例
    """
    try:
        webdav_config = load_webdav_config()
        media_dir = os.path.join(DATA_DIR, 'media')
        webdav_storage = _init_webdav_storage(webdav_config, media_dir)
        if webdav_storage is not None:
            return webdav_storage

        logger.info("📁 使用本地存储")
        return StorageManager(media_dir)

    except Exception as e:
        logger.error(f"❌ 存储管理器初始化失败: {e}")
        # 回退到默认本地存储
        return StorageManager(os.path.join(DATA_DIR, 'media'))


def _init_webdav_storage(webdav_config: dict, media_dir: str) -> StorageManager | None:
    if not webdav_config.get('enabled', False):
        return None

    url = webdav_config.get('url', '').strip()
    username = webdav_config.get('username', '').strip()
    password = webdav_config.get('password', '').strip()
    base_path = webdav_config.get('base_path', '/telegram_media')
    if not (url and username and password):
        return None

    try:
        webdav_client = WebDAVClient(url, username, password, base_path)
        if webdav_client.test_connection():
            logger.info("✅ WebDAV存储已启用")
            return StorageManager(media_dir, webdav_client)
    except ConnectionError as e:
        logger.warning(f"⚠️ WebDAV连接失败: {e}")
    except Exception as e:
        logger.warning(f"⚠️ WebDAV初始化失败: {e}")
    return None
