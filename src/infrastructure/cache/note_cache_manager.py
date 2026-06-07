"""Cache manager for note queries."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .cache_manager_base import BaseCacheManager
from .unified import UnifiedCache

logger = logging.getLogger(__name__)
_UNSET = object()


@dataclass(frozen=True)
class NoteListCacheQuery:
    user_id: int
    source: Optional[str]
    search: Optional[str]
    page: int


@dataclass(frozen=True)
class NoteCountCacheQuery:
    user_id: int
    source: Optional[str]
    search: Optional[str]


class NoteCacheManager(BaseCacheManager):
    """Cache manager for note lists, counts, sources, and individual notes."""

    def __init__(self, cache: Optional[UnifiedCache] = None):
        super().__init__(
            cache=cache,
            key_prefix="notes",
            default_ttl=300.0,
        )

    def cache_note_list(
        self,
        query: NoteListCacheQuery | int | None = None,
        *legacy_args: Any,
        notes: Any = _UNSET,
        ttl: Optional[float] = None,
        **legacy_fields: Any,
    ) -> None:
        query, notes = _note_list_cache_write(
            query,
            legacy_args,
            notes,
            legacy_fields=legacy_fields,
        )
        key = self._build_list_key(query)
        self.set(key, notes, ttl)
        logger.debug(f"Cached note list: user={query.user_id}, page={query.page}")

    def get_note_list(
        self,
        query: NoteListCacheQuery | int | None = None,
        *legacy_args: Any,
        **legacy_fields: Any,
    ) -> Optional[List[Dict[str, Any]]]:
        query = _note_list_cache_query(query, legacy_args, legacy_fields)
        key = self._build_list_key(query)
        return self.get(key)

    def _build_list_key(
        self,
        query: NoteListCacheQuery,
    ) -> str:
        source_part = query.source or "all"
        search_part = query.search[:20] if query.search else "none"
        return f"list:{query.user_id}:{source_part}:{search_part}:{query.page}"

    def cache_note_count(
        self,
        query: NoteCountCacheQuery | int | None = None,
        *legacy_args: Any,
        count: Any = _UNSET,
        ttl: Optional[float] = None,
        **legacy_fields: Any,
    ) -> None:
        query, count = _note_count_cache_write(
            query,
            legacy_args,
            count,
            legacy_fields=legacy_fields,
        )
        key = f"count:{query.user_id}:{query.source or 'all'}:{query.search or 'none'}"
        self.set(key, count, ttl)

    def get_note_count(
        self,
        user_id: int,
        source: Optional[str],
        search: Optional[str],
    ) -> Optional[int]:
        key = f"count:{user_id}:{source or 'all'}:{search or 'none'}"
        return self.get(key)

    def cache_sources(
        self,
        user_id: int,
        sources: List[str],
        ttl: Optional[float] = None,
    ) -> None:
        key = f"sources:{user_id}"
        self.set(key, sources, ttl or 600.0)

    def get_sources(self, user_id: int) -> Optional[List[str]]:
        key = f"sources:{user_id}"
        return self.get(key)

    def invalidate_user_notes(self, user_id: int) -> int:
        pattern = f"{self._key_prefix}:*:{user_id}:*"
        deleted = self._cache.delete_pattern(pattern)
        deleted += self._cache.delete_pattern(f"{self._key_prefix}:list:{user_id}:*")
        deleted += self._cache.delete_pattern(f"{self._key_prefix}:count:{user_id}:*")
        deleted += self._cache.delete(self._make_key(f"sources:{user_id}"))
        logger.info(f"Invalidated {deleted} cache entries for user {user_id}")
        return deleted

    def invalidate_note(self, note_id: int, user_id: int) -> int:
        deleted = self._cache.delete(self._make_key(f"note:{note_id}"))
        deleted += self._cache.delete_pattern(f"{self._key_prefix}:list:{user_id}:*")
        deleted += self._cache.delete_pattern(f"{self._key_prefix}:count:{user_id}:*")
        return deleted


def _note_list_cache_query(
    query: NoteListCacheQuery | int | None,
    legacy_args: tuple[Any, ...],
    legacy_fields: dict[str, Any] | None = None,
) -> NoteListCacheQuery:
    fields = dict(legacy_fields or {})
    if isinstance(query, NoteListCacheQuery):
        if legacy_args or fields:
            raise TypeError("note list cache methods received both query object and legacy arguments")
        return query
    if query is None:
        if "user_id" not in fields:
            raise TypeError("note list cache methods require user_id")
        query = fields.pop("user_id")
    if len(legacy_args) != 3:
        source = fields.pop("source")
        search = fields.pop("search")
        page = fields.pop("page")
        _reject_extra_cache_fields("note list cache methods", fields)
        return NoteListCacheQuery(int(query), source, search, int(page))
    source, search, page = legacy_args
    _reject_extra_cache_fields("note list cache methods", fields)
    return NoteListCacheQuery(int(query), source, search, int(page))


def _note_list_cache_write(
    query: NoteListCacheQuery | int | None,
    legacy_args: tuple[Any, ...],
    notes: Any,
    *,
    legacy_fields: dict[str, Any],
) -> tuple[NoteListCacheQuery, List[Dict[str, Any]]]:
    fields = dict(legacy_fields)
    if notes is not _UNSET:
        return _note_list_cache_query(query, legacy_args, fields), notes
    if isinstance(query, NoteListCacheQuery):
        raise TypeError("cache_note_list requires notes")
    if len(legacy_args) != 4:
        if "notes" not in fields:
            raise TypeError("cache_note_list requires notes")
        legacy_notes = fields.pop("notes")
        return _note_list_cache_query(query, legacy_args, fields), legacy_notes
    source, search, page, legacy_notes = legacy_args
    _reject_extra_cache_fields("cache_note_list", fields)
    return NoteListCacheQuery(int(query), source, search, int(page)), legacy_notes


def _note_count_cache_query(
    query: NoteCountCacheQuery | int | None,
    legacy_args: tuple[Any, ...],
    legacy_fields: dict[str, Any] | None = None,
) -> NoteCountCacheQuery:
    fields = dict(legacy_fields or {})
    if isinstance(query, NoteCountCacheQuery):
        if legacy_args or fields:
            raise TypeError("note count cache methods received both query object and legacy arguments")
        return query
    if query is None:
        if "user_id" not in fields:
            raise TypeError("note count cache methods require user_id")
        query = fields.pop("user_id")
    if len(legacy_args) != 2:
        source = fields.pop("source")
        search = fields.pop("search")
        _reject_extra_cache_fields("note count cache methods", fields)
        return NoteCountCacheQuery(int(query), source, search)
    source, search = legacy_args
    _reject_extra_cache_fields("note count cache methods", fields)
    return NoteCountCacheQuery(int(query), source, search)


def _note_count_cache_write(
    query: NoteCountCacheQuery | int | None,
    legacy_args: tuple[Any, ...],
    count: Any,
    *,
    legacy_fields: dict[str, Any],
) -> tuple[NoteCountCacheQuery, int]:
    fields = dict(legacy_fields)
    if count is not _UNSET:
        return _note_count_cache_query(query, legacy_args, fields), count
    if isinstance(query, NoteCountCacheQuery):
        raise TypeError("cache_note_count requires count")
    if len(legacy_args) != 3:
        if "count" not in fields:
            raise TypeError("cache_note_count requires count")
        legacy_count = fields.pop("count")
        return _note_count_cache_query(query, legacy_args, fields), legacy_count
    source, search, legacy_count = legacy_args
    _reject_extra_cache_fields("cache_note_count", fields)
    return NoteCountCacheQuery(int(query), source, search), legacy_count


def _reject_extra_cache_fields(function_name: str, fields: dict[str, Any]) -> None:
    if fields:
        unknown = ", ".join(sorted(fields))
        raise TypeError(f"{function_name} got unexpected keyword argument(s): {unknown}")
