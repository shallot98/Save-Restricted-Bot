"""
Narrow-port injection tests for note media storage.

覆盖报告 §3 P1-1 / 路线图 #19：`src.application` 不再 import
`bot.storage.webdav_client`，删除媒体走 `src.core.interfaces.MediaStorage`
端口，实现由组合根注入（`bot/storage/media_storage_provider.py`）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

import pytest

from src.application.services.note_service import NoteService
from src.core.interfaces import MediaStorage
from src.domain.entities.note import Note
from src.infrastructure.cache.managers import NoteCacheManager
from src.infrastructure.cache.unified import UnifiedCache


class FakeMediaStorage:
    """Minimal stand-in satisfying the MediaStorage port."""

    def __init__(self, results: Optional[Dict[str, bool]] = None) -> None:
        self.results = results or {}
        self.calls: List[str] = []

    def delete_file(self, storage_location: str) -> bool:
        self.calls.append(storage_location)
        return self.results.get(storage_location, True)


class FakeNoteRepository:
    def __init__(self, note: Optional[Note]) -> None:
        self.note = note

    def get_by_id(self, note_id: int) -> Optional[Note]:
        if self.note and self.note.id == note_id:
            return self.note
        return None

    def delete(self, note_id: int) -> bool:
        if self.get_by_id(note_id) is None:
            return False
        self.note = None
        return True


def _note_with_media() -> Note:
    return Note(
        id=1,
        user_id=123,
        source_chat_id="source-1",
        source_name="Source 1",
        message_text="hello",
        timestamp=datetime.now(),
        media_path="local:a.jpg",
        media_paths=["local:a.jpg", "webdav:b.jpg"],
    )


@pytest.fixture
def note_cache_manager() -> NoteCacheManager:
    cache = UnifiedCache(default_ttl=60.0, max_size=1000, name="test-media-injection")
    return NoteCacheManager(cache=cache)


def _build_service(note: Note, provider, cache: NoteCacheManager) -> NoteService:
    service = NoteService(
        FakeNoteRepository(note),  # type: ignore[arg-type]
        media_storage_provider=provider,
    )
    service._cache = cache
    return service


def test_fake_storage_satisfies_port() -> None:
    assert isinstance(FakeMediaStorage(), MediaStorage)


def test_delete_note_uses_injected_media_storage(note_cache_manager: NoteCacheManager) -> None:
    storage = FakeMediaStorage()
    service = _build_service(_note_with_media(), lambda: storage, note_cache_manager)

    assert service.delete_note(1) is True
    assert set(storage.calls) == {"local:a.jpg", "webdav:b.jpg"}


def test_media_storage_provider_is_resolved_once(note_cache_manager: NoteCacheManager) -> None:
    storage = FakeMediaStorage()
    calls = {"count": 0}

    def provider() -> MediaStorage:
        calls["count"] += 1
        return storage

    service = _build_service(_note_with_media(), provider, note_cache_manager)

    assert service.delete_note(1) is True
    assert calls["count"] == 1


def test_unwired_provider_warns_and_skips_cleanup(
    note_cache_manager: NoteCacheManager,
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = _build_service(_note_with_media(), lambda: None, note_cache_manager)

    with caplog.at_level("WARNING"):
        assert service.delete_note(1) is True

    assert "Media storage unavailable" in caplog.text


def test_bot_side_storage_manager_satisfies_port() -> None:
    """StorageManager 是端口的生产实现，结构必须匹配。"""
    from bot.storage.storage_manager import StorageManager

    assert isinstance(StorageManager("/tmp/media-port-check"), MediaStorage)
