"""
Unit tests for SQLiteNoteRepository.search single-scan query.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager

import pytest

from src.domain.entities.note import NoteFilter
from src.infrastructure.persistence.repositories.note_repository import SQLiteNoteRepository


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE notes (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            source_chat_id TEXT NOT NULL,
            source_name TEXT,
            message_text TEXT,
            timestamp TEXT,
            media_type TEXT,
            media_path TEXT,
            media_paths TEXT,
            media_group_id TEXT,
            magnet_link TEXT,
            filename TEXT,
            is_favorite INTEGER DEFAULT 0
        )
        """
    )
    connection.executemany(
        """
        INSERT INTO notes (id, user_id, source_chat_id, source_name, message_text, timestamp, is_favorite)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (1, 1, "s1", "src", "a", "2025-01-01 00:00:00", 0),
            (2, 1, "s1", "src", "b", "2025-01-02 00:00:00", 1),
            (3, 1, "s2", "src2", "c", "2025-01-03 00:00:00", 0),
        ],
    )
    connection.commit()
    yield connection
    connection.close()


def test_search_returns_total_count_with_limit_offset(monkeypatch: pytest.MonkeyPatch, conn) -> None:
    @contextmanager
    def _fake_db():
        yield conn

    monkeypatch.setattr(
        "src.infrastructure.persistence.repositories.note_repository.get_db_connection",
        _fake_db,
        raising=True,
    )

    repo = SQLiteNoteRepository()

    notes, total = repo.search(NoteFilter(user_id=1, limit=2, offset=0))
    assert total == 3
    assert len(notes) == 2

    notes2, total2 = repo.search(NoteFilter(user_id=1, limit=2, offset=2))
    assert total2 == 3
    assert len(notes2) == 1


def test_search_with_favorite_only(monkeypatch: pytest.MonkeyPatch, conn) -> None:
    @contextmanager
    def _fake_db():
        yield conn

    monkeypatch.setattr(
        "src.infrastructure.persistence.repositories.note_repository.get_db_connection",
        _fake_db,
        raising=True,
    )

    repo = SQLiteNoteRepository()
    notes, total = repo.search(NoteFilter(user_id=1, favorite_only=True, limit=10, offset=0))
    assert total == 1
    assert len(notes) == 1
    assert notes[0].is_favorite is True

