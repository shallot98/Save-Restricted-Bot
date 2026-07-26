"""
Cache Ports
===========

Narrow ports for the two cache managers `src.application` actually uses.

`src.application` 过去用函数内延迟 import 直接抓 `src.infrastructure.cache.
managers` 的全局工厂（报告 §5.2「application 只认识 domain 与 core.interfaces」
的最后 5 处违例之一）。这里只声明被真实调用到的方法，不搬运
`BaseCacheManager` 的完整方法面。

实现是 `src/infrastructure/cache/note_cache_manager.py:NoteCacheManager` 与
`config_cache_manager.py:ConfigCacheManager`，由组合根
`composition/container.py` 以 provider 形式注入。
"""

from __future__ import annotations

from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    runtime_checkable,
)


@runtime_checkable
class NoteCache(Protocol):
    """Port for the note query/list cache."""

    def get(self, key: str) -> Optional[Any]:
        """Read a cached value. Returns None on miss."""
        ...

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Write a value with an optional TTL (seconds)."""
        ...

    def invalidate_all(self) -> int:
        """Drop every note entry. Returns the number of removed entries."""
        ...

    def invalidate_user_notes(self, user_id: int) -> int:
        """Drop one user's note entries. Returns the number of removed entries."""
        ...

    def get_sources(self, user_id: int) -> Optional[List[Any]]:
        """Read the cached source list for a user (0 = all users)."""
        ...

    def cache_sources(
        self,
        user_id: int,
        sources: List[Any],
        ttl: Optional[float] = None,
    ) -> None:
        """Cache the source list for a user (0 = all users)."""
        ...


@runtime_checkable
class ConfigCache(Protocol):
    """Port for the watch-configuration cache."""

    def get_watch_config(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Read a cached watch config. Returns None on miss."""
        ...

    def cache_watch_config(
        self,
        user_id: int,
        config: Dict[str, Any],
        ttl: Optional[float] = None,
    ) -> None:
        """Cache a user's watch config."""
        ...

    def get_monitored_sources(self) -> Optional[List[Dict[str, Any]]]:
        """Read the cached monitored-source list. Returns None on miss."""
        ...

    def cache_monitored_sources(
        self,
        sources: List[Dict[str, Any]],
        ttl: Optional[float] = None,
    ) -> None:
        """Cache the monitored-source list."""
        ...

    def invalidate_watch_config(self, user_id: Optional[int] = None) -> int:
        """Drop watch config entries (all users when user_id is None)."""
        ...


#: 组合根注入的惰性提供者：未装配时返回 None，调用方必须显式处理。
NoteCacheProvider = Callable[[], Optional[NoteCache]]
ConfigCacheProvider = Callable[[], Optional[ConfigCache]]
