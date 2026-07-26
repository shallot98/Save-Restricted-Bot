"""Cache helpers for NoteService."""

from __future__ import annotations

import logging
from typing import Optional

from src.application.services.cache_fallback import resolve_cache
from src.core.interfaces import NoteCache, NoteCacheProvider

logger = logging.getLogger(__name__)


class NoteServiceCacheMixin:
    # 由 `NoteService.__init__` 赋值；在 Mixin 上声明类型，供类型检查看到。
    _cache: Optional[NoteCache]
    _cache_provider: Optional[NoteCacheProvider]

    def _get_cache(self) -> NoteCache:
        cache = self._cache
        if cache is None:
            cache = resolve_cache(self._cache_provider, label="Note")
            self._cache = cache
        return cache

    def _invalidate_note_caches(self, user_id: Optional[int] = None) -> None:
        deleted = self._get_cache().invalidate_all()
        logger.debug(f"Cache invalidated for notes (user={user_id or 'all'}), deleted={deleted}")

    def invalidate_cache(self, user_id: Optional[int] = None) -> int:
        if user_id is not None:
            return self._get_cache().invalidate_user_notes(user_id)
        return self._get_cache().invalidate_all()
