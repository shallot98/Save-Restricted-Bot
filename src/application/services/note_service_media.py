"""Media cleanup helpers for NoteService."""

from __future__ import annotations

import logging
from typing import Set

from src.domain.entities.note import Note

logger = logging.getLogger(__name__)


class NoteServiceMediaMixin:
    def _get_storage_manager(self):
        if self._storage_manager is None:
            self._storage_manager = self._build_storage_manager()
        return self._storage_manager

    @staticmethod
    def _build_storage_manager():
        from bot.storage.webdav_client import StorageManager, WebDAVClient
        from src.core.config import settings

        media_dir = str(settings.paths.media_dir)
        webdav_client = _build_webdav_client(settings.webdav_config)
        return StorageManager(media_dir, webdav_client)

    @staticmethod
    def _collect_media_locations(note: Note) -> Set[str]:
        media_locations: Set[str] = set()
        if note.media_path:
            media_locations.add(note.media_path)
        if note.media_paths:
            media_locations.update(path for path in note.media_paths if path)
        return media_locations

    def _delete_note_media_best_effort(self, note: Note) -> None:
        media_locations = self._collect_media_locations(note)
        if not media_locations:
            return
        storage_manager = self._try_get_storage_manager()
        if storage_manager is None:
            return
        for location in media_locations:
            self._delete_media_location(storage_manager, note.id, location)

    def _try_get_storage_manager(self):
        try:
            return self._get_storage_manager()
        except Exception as exc:
            logger.warning(f"Storage manager unavailable, skip media cleanup: {exc}")
            return None

    @staticmethod
    def _delete_media_location(storage_manager, note_id: int, location: str) -> None:
        try:
            if not storage_manager.delete_file(location):
                logger.warning(f"Failed to delete media: note={note_id}, path={location}")
        except Exception as exc:
            logger.warning(f"Failed to delete media: note={note_id}, path={location}, err={exc}")


def _build_webdav_client(webdav_config):
    from bot.storage.webdav_client import WebDAVClient

    if not webdav_config.get("enabled", False):
        return None
    url = (webdav_config.get("url") or "").strip()
    username = (webdav_config.get("username") or "").strip()
    password = (webdav_config.get("password") or "").strip()
    base_path = webdav_config.get("base_path") or "/telegram_media"
    if not url or not username or not password:
        return None
    try:
        return WebDAVClient(url, username, password, base_path)
    except Exception as exc:
        logger.warning(f"WebDAV storage init failed, fallback to local: {exc}")
        return None
