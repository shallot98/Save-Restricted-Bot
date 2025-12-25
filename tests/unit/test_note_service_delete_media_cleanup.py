"""
Unit tests for NoteService media cleanup on delete.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, List

import pytest

from src.application.services.note_service import NoteService
from src.core.exceptions import NotFoundError
from src.domain.entities.note import Note
from src.infrastructure.cache.managers import NoteCacheManager
from src.infrastructure.cache.unified import UnifiedCache


@dataclass
class FakeStorageManager:
    results: Dict[str, bool]
    calls: List[str]

    def __init__(self, results: Optional[Dict[str, bool]] = None) -> None:
        self.results = results or {}
        self.calls = []

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


@pytest.fixture
def cache() -> UnifiedCache:
    return UnifiedCache(default_ttl=60.0, max_size=1000, name="test-notes-delete")


@pytest.fixture
def note_cache_manager(cache: UnifiedCache) -> NoteCacheManager:
    return NoteCacheManager(cache=cache)


class TestNoteServiceDeleteMediaCleanup:
    def test_delete_note_deletes_unique_media_locations(self, note_cache_manager: NoteCacheManager) -> None:
        note = Note(
            id=1,
            user_id=123,
            source_chat_id="source-1",
            source_name="Source 1",
            message_text="hello",
            timestamp=datetime.now(),
            media_path="local:a.jpg",
            media_paths=["local:a.jpg", "webdav:b.jpg"],
        )
        repo = FakeNoteRepository(note)
        service = NoteService(repo)  # type: ignore[arg-type]
        service._cache = note_cache_manager

        storage = FakeStorageManager()
        service._storage_manager = storage

        assert service.delete_note(1) is True
        assert repo.note is None
        assert set(storage.calls) == {"local:a.jpg", "webdav:b.jpg"}

    def test_delete_note_media_cleanup_is_best_effort(self, note_cache_manager: NoteCacheManager) -> None:
        note = Note(
            id=1,
            user_id=123,
            source_chat_id="source-1",
            source_name="Source 1",
            message_text="hello",
            timestamp=datetime.now(),
            media_paths=["webdav:missing.jpg"],
        )
        repo = FakeNoteRepository(note)
        service = NoteService(repo)  # type: ignore[arg-type]
        service._cache = note_cache_manager

        storage = FakeStorageManager(results={"webdav:missing.jpg": False})
        service._storage_manager = storage

        assert service.delete_note(1) is True
        assert set(storage.calls) == {"webdav:missing.jpg"}

    def test_delete_missing_note_raises(self, note_cache_manager: NoteCacheManager) -> None:
        repo = FakeNoteRepository(note=None)
        service = NoteService(repo)  # type: ignore[arg-type]
        service._cache = note_cache_manager

        with pytest.raises(NotFoundError):
            service.delete_note(1)

