"""Source-list helpers for NoteService."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class NoteServiceSourcesMixin:
    def get_sources(self, user_id: int) -> list[dict]:
        cached_sources = self._get_cache().get_sources(user_id)
        if cached_sources is not None:
            logger.debug(f"Cache hit: sources for user={user_id}")
            return cached_sources

        result = _format_sources(self._repository.get_sources(user_id))
        self._get_cache().cache_sources(user_id, result, ttl=600.0)
        logger.debug(f"Cache set: sources for user={user_id}")
        return result

    def get_all_sources(self) -> list[dict]:
        cached_sources = self._get_cache().get_sources(0)
        if cached_sources is not None:
            logger.debug("Cache hit: all sources")
            return cached_sources

        result = _format_sources(self._repository.get_all_sources())
        self._get_cache().cache_sources(0, result, ttl=600.0)
        logger.debug("Cache set: all sources")
        return result


def _format_sources(sources) -> list[dict]:
    return [
        {
            "source_chat_id": source_id,
            "source_name": source_name,
            "count": count,
        }
        for source_id, source_name, count in sources
    ]
