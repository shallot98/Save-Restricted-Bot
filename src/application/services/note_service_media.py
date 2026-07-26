"""Media cleanup helpers for NoteService."""

from __future__ import annotations

import logging
from typing import Optional, Set

from src.core.interfaces import MediaStorage, MediaStorageProvider
from src.domain.entities.note import Note

logger = logging.getLogger(__name__)


class NoteServiceMediaMixin:
    # 由 NoteService.__init__ 注入（组合根装配），此处仅声明契约供类型检查使用。
    _media_storage_provider: Optional[MediaStorageProvider]
    _storage_manager: Optional[MediaStorage]

    def _get_storage_manager(self) -> Optional[MediaStorage]:
        """Resolve the injected media storage once and cache it."""
        if self._storage_manager is None:
            if self._media_storage_provider is not None:
                self._storage_manager = self._media_storage_provider()
            if self._storage_manager is None:
                logger.warning(
                    "Media storage unavailable (composition root not wired); "
                    "note media cleanup is skipped"
                )
        return self._storage_manager

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

    def _try_get_storage_manager(self) -> Optional[MediaStorage]:
        try:
            return self._get_storage_manager()
        except Exception as exc:
            logger.warning(f"Storage manager unavailable, skip media cleanup: {exc}")
            return None

    @staticmethod
    def _delete_media_location(storage_manager: MediaStorage, note_id: Optional[int], location: str) -> None:
        try:
            if not storage_manager.delete_file(location):
                logger.warning(f"Failed to delete media: note={note_id}, path={location}")
        except Exception as exc:
            logger.warning(f"Failed to delete media: note={note_id}, path={location}, err={exc}")
