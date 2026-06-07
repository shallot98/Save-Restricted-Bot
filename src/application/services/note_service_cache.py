"""Cache helpers for NoteService."""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class NoteServiceCacheMixin:
    def _get_cache(self):
        if self._cache is None:
            from src.infrastructure.cache.managers import get_note_cache_manager

            self._cache = get_note_cache_manager()
        return self._cache

    def _invalidate_note_caches(self, user_id: Optional[int] = None) -> None:
        deleted = self._get_cache().invalidate_all()
        logger.debug(f"Cache invalidated for notes (user={user_id or 'all'}), deleted={deleted}")

    def invalidate_cache(self, user_id: Optional[int] = None) -> int:
        if user_id is not None:
            return self._get_cache().invalidate_user_notes(user_id)
        return self._get_cache().invalidate_all()
