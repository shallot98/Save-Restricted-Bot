"""
Unit tests for NoteService caching and invalidation.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Dict, Optional, Tuple, List

import pytest

from src.application.services.note_service import NoteService
from src.core.exceptions import NotFoundError, ValidationError
from src.domain.entities.note import Note, NoteFilter
from src.infrastructure.cache.managers import NoteCacheManager
from src.infrastructure.cache.unified import UnifiedCache


class FakeNoteRepository:
    def __init__(self) -> None:
        self.search_calls = 0
        self.last_filter: Optional[NoteFilter] = None
        self.notes: Dict[int, Note] = {}
        self.update_text_calls: List[Tuple[int, str]] = []

    def get_by_id(self, note_id: int) -> Optional[Note]:
        return self.notes.get(note_id)

    def search(self, filter_criteria: NoteFilter):
        self.search_calls += 1
        self.last_filter = filter_criteria
        notes = list(self.notes.values())
        return notes, len(notes)

    def update_text(self, note_id: int, message_text: str) -> bool:
        self.update_text_calls.append((note_id, message_text))
        note = self.notes.get(note_id)
        if not note:
            return False
        self.notes[note_id] = replace(note, message_text=message_text)
        return True

    def toggle_favorite(self, note_id: int) -> bool:
        note = self.notes.get(note_id)
        if not note:
            return False
        new_status = not note.is_favorite
        self.notes[note_id] = replace(note, is_favorite=new_status)
        return new_status


@pytest.fixture
def cache():
    return UnifiedCache(default_ttl=60.0, max_size=1000, name="test-notes")


@pytest.fixture
def note_cache_manager(cache):
    return NoteCacheManager(cache=cache)


@pytest.fixture
def repo():
    repo = FakeNoteRepository()
    repo.notes[1] = Note(
        id=1,
        user_id=123,
        source_chat_id="source-1",
        source_name="Source 1",
        message_text="hello",
        timestamp=datetime.now(),
        is_favorite=False,
    )
    return repo


@pytest.fixture
def service(repo, note_cache_manager):
    service = NoteService(repo)  # type: ignore[arg-type]
    service._cache = note_cache_manager  # Inject cache manager for deterministic tests
    return service


class TestNoteServiceCache:
    def test_get_notes_caches_result(self, service, repo):
        """Second identical call should be served from cache."""
        result1 = service.get_notes(user_id=None, page=1, page_size=10)
        assert repo.search_calls == 1
        assert repo.last_filter is not None
        assert repo.last_filter.user_id is None

        result2 = service.get_notes(user_id=None, page=1, page_size=10)
        assert repo.search_calls == 1
        assert result2 is result1

    def test_get_notes_does_not_cache_when_search_query_present(self, service, repo):
        result1 = service.get_notes(user_id=None, search_query="hello", page=1, page_size=10)
        assert repo.search_calls == 1

        result2 = service.get_notes(user_id=None, search_query="hello", page=1, page_size=10)
        assert repo.search_calls == 2
        assert result2 is not result1

    def test_get_notes_does_not_cache_when_date_filter_present(self, service, repo):
        result1 = service.get_notes(user_id=None, date_from="2025-01-01", page=1, page_size=10)
        assert repo.search_calls == 1

        result2 = service.get_notes(user_id=None, date_from="2025-01-01", page=1, page_size=10)
        assert repo.search_calls == 2
        assert result2 is not result1

    def test_get_notes_does_not_cache_for_high_page_numbers(self, service, repo):
        result1 = service.get_notes(user_id=None, page=11, page_size=10)
        assert repo.search_calls == 1

        result2 = service.get_notes(user_id=None, page=11, page_size=10)
        assert repo.search_calls == 2
        assert result2 is not result1

    def test_update_text_invalidates_notes_cache(self, service, cache):
        """Any write should invalidate note-related caches."""
        _ = service.get_notes(user_id=None, page=1, page_size=10)
        assert cache.size > 0

        assert service.update_text(1, "updated") is True
        assert cache.size == 0

    def test_update_text_empty_rejected(self, service):
        with pytest.raises(ValidationError):
            service.update_text(1, "   ")

    def test_toggle_favorite_invalidates_notes_cache(self, service, cache):
        _ = service.get_notes(user_id=None, page=1, page_size=10)
        assert cache.size > 0

        new_status = service.toggle_favorite(1)
        assert new_status is True
        assert cache.size == 0

    def test_toggle_favorite_missing_note_raises(self, service, repo):
        repo.notes.pop(1, None)
        with pytest.raises(NotFoundError):
            service.toggle_favorite(1)
