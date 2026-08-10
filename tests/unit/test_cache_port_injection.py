"""
Narrow-port injection tests for the two cache managers.

覆盖报告 §5.2：`src.application` 不再函数内 import
`src.infrastructure.cache.managers`，而是通过 `src.core.interfaces` 的
`NoteCache` / `ConfigCache` 端口 + 组合根注入的 provider 取得实现。

未装配时的约定是「显式降级」：打一条 WARNING 并走 NullCache（每次 miss），
而不是静默假装有缓存——所以每个服务都配一条 unwired 用例钉住这一点。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pytest

from src.application.services.cache_fallback import NullCache
from src.application.services.note_service import NoteService
from src.application.services.watch_service import WatchService
from src.core.interfaces import ConfigCache, NoteCache
from src.domain.entities.note import Note, NoteFilter
from src.domain.entities.watch import WatchConfig, WatchTask


@dataclass
class FakeNoteCache:
    """Minimal stand-in satisfying the NoteCache port."""

    entries: Dict[str, Any] = field(default_factory=dict)
    reads: List[str] = field(default_factory=list)
    writes: List[Tuple[str, Optional[float]]] = field(default_factory=list)
    invalidate_all_calls: int = 0
    invalidated_users: List[int] = field(default_factory=list)
    sources: Dict[int, List[Any]] = field(default_factory=dict)

    def get(self, key: str) -> Optional[Any]:
        self.reads.append(key)
        return self.entries.get(key)

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        self.writes.append((key, ttl))
        self.entries[key] = value

    def invalidate_all(self) -> int:
        self.invalidate_all_calls += 1
        removed = len(self.entries)
        self.entries.clear()
        return removed

    def invalidate_user_notes(self, user_id: int) -> int:
        self.invalidated_users.append(user_id)
        return 1

    def get_sources(self, user_id: int) -> Optional[List[Any]]:
        return self.sources.get(user_id)

    def cache_sources(
        self,
        user_id: int,
        sources: List[Any],
        ttl: Optional[float] = None,
    ) -> None:
        self.sources[user_id] = sources


@dataclass
class FakeConfigCache:
    """Minimal stand-in satisfying the ConfigCache port."""

    watch_configs: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    monitored_sources: Optional[List[Dict[str, Any]]] = None
    invalidations: List[Optional[int]] = field(default_factory=list)

    def get_watch_config(self, user_id: int) -> Optional[Dict[str, Any]]:
        return self.watch_configs.get(user_id)

    def cache_watch_config(
        self,
        user_id: int,
        config: Dict[str, Any],
        ttl: Optional[float] = None,
    ) -> None:
        self.watch_configs[user_id] = config

    def get_monitored_sources(self) -> Optional[List[Dict[str, Any]]]:
        return self.monitored_sources

    def cache_monitored_sources(
        self,
        sources: List[Dict[str, Any]],
        ttl: Optional[float] = None,
    ) -> None:
        self.monitored_sources = sources

    def invalidate_watch_config(self, user_id: Optional[int] = None) -> int:
        self.invalidations.append(user_id)
        return 1


class FakeNoteRepository:
    def __init__(self) -> None:
        self.search_calls = 0
        self.notes: Dict[int, Note] = {
            1: Note(
                id=1,
                user_id=123,
                source_chat_id="source-1",
                source_name="Source 1",
                message_text="hello",
                timestamp=datetime.now(),
            )
        }

    def get_by_id(self, note_id: int) -> Optional[Note]:
        return self.notes.get(note_id)

    def search(self, filter_criteria: NoteFilter):
        self.search_calls += 1
        notes = list(self.notes.values())
        return notes, len(notes)


class FakeWatchRepository:
    def __init__(self) -> None:
        self.config_calls = 0
        self.sources_calls = 0

    def get_user_config(self, user_id: str) -> Optional[WatchConfig]:
        self.config_calls += 1
        return WatchConfig(
            user_id=user_id,
            tasks={"task-1": WatchTask(source="-100123", dest=None)},
        )

    def get_monitored_sources(self) -> set:
        self.sources_calls += 1
        return {"-100123"}


class TestNoteCachePortInjection:
    def test_fake_satisfies_port(self) -> None:
        assert isinstance(FakeNoteCache(), NoteCache)

    def test_note_list_is_served_from_injected_cache(self) -> None:
        cache = FakeNoteCache()
        repo = FakeNoteRepository()
        service = NoteService(repo, cache_provider=lambda: cache)  # type: ignore[arg-type]

        first = service.get_notes(user_id=None, page=1, page_size=10)
        second = service.get_notes(user_id=None, page=1, page_size=10)

        assert repo.search_calls == 1, "second call should not reach the repository"
        assert second is first
        assert len(cache.writes) == 1
        assert cache.writes[0][1] == 60.0

    def test_writes_invalidate_through_injected_cache(self) -> None:
        cache = FakeNoteCache()
        service = NoteService(FakeNoteRepository(), cache_provider=lambda: cache)  # type: ignore[arg-type]

        service.get_notes(user_id=None, page=1, page_size=10)
        assert service.invalidate_cache(user_id=123) == 1

        assert cache.invalidated_users == [123]

    def test_unwired_provider_warns_and_degrades(self, caplog: pytest.LogCaptureFixture) -> None:
        repo = FakeNoteRepository()
        service = NoteService(repo)  # type: ignore[arg-type]

        with caplog.at_level("WARNING"):
            service.get_notes(user_id=None, page=1, page_size=10)
            service.get_notes(user_id=None, page=1, page_size=10)

        assert "Note cache unavailable" in caplog.text
        assert repo.search_calls == 2, "NullCache must always miss, never fake a hit"
        assert isinstance(service._cache, NullCache)


class TestConfigCachePortInjection:
    def test_fake_satisfies_port(self) -> None:
        assert isinstance(FakeConfigCache(), ConfigCache)

    def test_watch_config_is_served_from_injected_cache(self) -> None:
        cache = FakeConfigCache()
        repo = FakeWatchRepository()
        service = WatchService(repo, cache_provider=lambda: cache)  # type: ignore[arg-type]

        first = service.get_user_config("123")
        second = service.get_user_config("123")

        assert first is not None and second is not None
        assert repo.config_calls == 1, "second call should not reach the repository"
        assert 123 in cache.watch_configs

    def test_monitored_sources_are_cached_through_port(self) -> None:
        cache = FakeConfigCache()
        repo = FakeWatchRepository()
        service = WatchService(repo, cache_provider=lambda: cache)  # type: ignore[arg-type]

        assert service.get_monitored_sources() == {"-100123"}
        assert service.get_monitored_sources() == {"-100123"}

        assert repo.sources_calls == 1
        assert cache.monitored_sources == [{"id": "-100123"}]

    def test_unwired_provider_warns_and_degrades(self, caplog: pytest.LogCaptureFixture) -> None:
        repo = FakeWatchRepository()
        service = WatchService(repo)  # type: ignore[arg-type]

        with caplog.at_level("WARNING"):
            service.get_user_config("123")
            service.get_user_config("123")

        assert "Config cache unavailable" in caplog.text
        assert repo.config_calls == 2, "NullCache must always miss, never fake a hit"
        assert isinstance(service._cache, NullCache)
