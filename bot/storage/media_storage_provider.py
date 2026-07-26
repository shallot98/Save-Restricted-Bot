"""Bot-side construction of the `MediaStorage` port.

组合根 `composition/wiring.py` 用它把具体存储实现注入 `src.application`。
逻辑原先内联在 `src/application/services/note_service_media.py`，是 `src/` →
`bot/` 反向依赖的来源之一（报告 §3 P1-1），现按依赖方向搬到 bot 侧。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from bot.storage.storage_manager import StorageManager
from bot.storage.webdav_remote import WebDAVClient
from src.core.config import settings
from src.core.interfaces import MediaStorage

logger = logging.getLogger(__name__)

DEFAULT_WEBDAV_BASE_PATH = "/telegram_media"


def build_media_storage() -> Optional[MediaStorage]:
    """Build the media storage backend (local dir, optionally WebDAV-backed)."""
    media_dir = str(settings.paths.media_dir)
    return StorageManager(media_dir, build_webdav_client(settings.webdav_config))


def build_webdav_client(webdav_config: Dict[str, Any]) -> Optional[WebDAVClient]:
    """Build a WebDAV client, or None when disabled/incomplete."""
    if not webdav_config.get("enabled", False):
        return None
    url = (webdav_config.get("url") or "").strip()
    username = (webdav_config.get("username") or "").strip()
    password = (webdav_config.get("password") or "").strip()
    base_path = webdav_config.get("base_path") or DEFAULT_WEBDAV_BASE_PATH
    if not url or not username or not password:
        return None
    try:
        return WebDAVClient(url, username, password, base_path)
    except Exception as exc:
        logger.warning(f"WebDAV storage init failed, fallback to local: {exc}")
        return None
