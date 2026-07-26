"""Explicit degradation for unwired cache ports.

缓存端口由组合根注入（`composition/container.py`）。装配缺失时不能静默地
「好像有缓存」，也不能让服务崩掉——读路径本来就允许 miss。这里给出一个
显式的空实现：每次读都 miss、每次写都丢弃，并在解析时打一条 WARNING，
让「缓存没装上」在日志里可见（§5.3 规则 5：禁止静默 fallback）。
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, TypeVar, cast

logger = logging.getLogger(__name__)

CacheT = TypeVar("CacheT")


class NullCache:
    """No-op cache satisfying both `NoteCache` and `ConfigCache`."""

    # --- NoteCache ---------------------------------------------------
    def get(self, key: str) -> Optional[Any]:
        return None

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        return None

    def invalidate_all(self) -> int:
        return 0

    def invalidate_user_notes(self, user_id: int) -> int:
        return 0

    def get_sources(self, user_id: int) -> Optional[List[Any]]:
        return None

    def cache_sources(
        self,
        user_id: int,
        sources: List[Any],
        ttl: Optional[float] = None,
    ) -> None:
        return None

    # --- ConfigCache -------------------------------------------------
    def get_watch_config(self, user_id: int) -> Optional[Dict[str, Any]]:
        return None

    def cache_watch_config(
        self,
        user_id: int,
        config: Dict[str, Any],
        ttl: Optional[float] = None,
    ) -> None:
        return None

    def get_monitored_sources(self) -> Optional[List[Dict[str, Any]]]:
        return None

    def cache_monitored_sources(
        self,
        sources: List[Dict[str, Any]],
        ttl: Optional[float] = None,
    ) -> None:
        return None

    def invalidate_watch_config(self, user_id: Optional[int] = None) -> int:
        return 0


def resolve_cache(
    provider: Optional[Callable[[], Optional[CacheT]]],
    *,
    label: str,
) -> CacheT:
    """Resolve a cache provider, degrading to `NullCache` with a warning.

    `cast` 是安全的：`NullCache` 同时满足 `NoteCache` 与 `ConfigCache`
    两个端口的全部方法（见本模块顶部），而 CacheT 只会被实例化为这两者之一。
    """
    cache = provider() if provider is not None else None
    if cache is None:
        logger.warning(
            "%s cache unavailable (provider not wired); running without cache. "
            "Wire it in composition/container.py.",
            label,
        )
        return cast(CacheT, NullCache())
    return cache
