"""
Unit tests for SQLiteNoteRepository timestamp parsing.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime

import pytest

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
    connection.execute(
        """
        INSERT INTO notes (id, user_id, source_chat_id, source_name, message_text, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (1, 1, "s1", "src", "hello", "2025-01-01 00:00:00"),
    )
    connection.execute(
        """
        INSERT INTO notes (id, user_id, source_chat_id, source_name, message_text, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (2, 1, "s1", "src", "hello", "2025-01-02T00:00:00"),
    )
    connection.execute(
        """
        INSERT INTO notes (id, user_id, source_chat_id, source_name, message_text, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (3, 1, "s1", "src", "hello", "2025-01-03T00:00:00Z"),
    )
    connection.commit()
    yield connection
    connection.close()


def test_get_by_id_parses_timestamp_to_datetime(monkeypatch: pytest.MonkeyPatch, conn) -> None:
    @contextmanager
    def _fake_db():
        yield conn

    monkeypatch.setattr(
        "src.infrastructure.persistence.repositories.note_repository.get_db_connection",
        _fake_db,
        raising=True,
    )

    repo = SQLiteNoteRepository()
    note_1 = repo.get_by_id(1)
    assert note_1 is not None
    assert isinstance(note_1.timestamp, datetime)
    assert note_1.timestamp.year == 2025
    assert note_1.timestamp.month == 1
    assert note_1.timestamp.day == 1

    note_2 = repo.get_by_id(2)
    assert note_2 is not None
    assert isinstance(note_2.timestamp, datetime)
    assert note_2.timestamp.year == 2025
    assert note_2.timestamp.month == 1
    assert note_2.timestamp.day == 2

    note_3 = repo.get_by_id(3)
    assert note_3 is not None
    assert isinstance(note_3.timestamp, datetime)
    assert note_3.timestamp.year == 2025
    assert note_3.timestamp.month == 1
    assert note_3.timestamp.day == 3
    assert note_3.timestamp.tzinfo is not None
