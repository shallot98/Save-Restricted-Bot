"""Media cleanup helpers for database compatibility functions."""

from __future__ import annotations

import json
import sqlite3
from typing import Any


def collect_note_media_files(cursor: sqlite3.Cursor, note_id: int) -> set[str]:
    cursor.execute("SELECT media_path, media_paths FROM notes WHERE id = ?", (note_id,))
    result = cursor.fetchone()
    if not result:
        return set()

    single_path, media_paths_json = result
    media_files = _media_paths_from_json(media_paths_json)
    if single_path:
        media_files.add(single_path)
    return media_files


def cleanup_media_files(media_files: set[str], *, settings: Any, logger: Any) -> None:
    try:
        storage_manager = _build_storage_manager(settings=settings, logger=logger)
    except Exception as e:
        logger.warning(f"Failed to init storage manager for media cleanup: {e}")
        return

    for media_path in media_files:
        try:
            if not storage_manager.delete_file(media_path):
                logger.warning(f"Failed to delete media file: {media_path}")
        except Exception as e:
            logger.warning(f"Failed to delete media file: {media_path}, err={e}")


def _media_paths_from_json(media_paths_json: Any) -> set[str]:
    if not media_paths_json:
        return set()
    try:
        return {path for path in json.loads(media_paths_json) if path}
    except (json.JSONDecodeError, TypeError):
        return set()


def _build_storage_manager(*, settings: Any, logger: Any):
    from bot.storage.webdav_client import StorageManager, WebDAVClient

    webdav_client = None
    webdav_config = settings.webdav_config
    if webdav_config.get("enabled", False):
        webdav_client = _build_webdav_client(webdav_config, logger)
    return StorageManager(str(settings.paths.media_dir), webdav_client)


def _build_webdav_client(webdav_config: dict[str, Any], logger: Any):
    from bot.storage.webdav_client import WebDAVClient

    url = (webdav_config.get("url") or "").strip()
    username = (webdav_config.get("username") or "").strip()
    password = (webdav_config.get("password") or "").strip()
    base_path = webdav_config.get("base_path") or "/telegram_media"
    if not url or not username or not password:
        return None
    try:
        return WebDAVClient(url, username, password, base_path)
    except Exception as e:
        logger.warning(f"WebDAV storage init failed, fallback to local: {e}")
        return None
