"""
Unit tests for SQLiteNoteRepository.search using SQLite FTS5 when available.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager

import pytest

from src.domain.entities.note import NoteFilter
from src.infrastructure.persistence.repositories.note_repository import SQLiteNoteRepository


def _create_notes_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
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


def _create_fts_schema_or_skip(conn: sqlite3.Connection) -> None:
    try:
        conn.execute(
            """
            CREATE VIRTUAL TABLE notes_fts USING fts5(
                message_text,
                source_name
            )
            """
        )
    except sqlite3.OperationalError as e:
        pytest.skip(f"SQLite FTS5 unavailable: {e}")


@pytest.fixture
def conn() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    _create_notes_schema(connection)
    yield connection
    connection.close()


def test_search_query_uses_fts_when_table_exists(monkeypatch: pytest.MonkeyPatch, conn) -> None:
    _create_fts_schema_or_skip(conn)

    conn.execute(
        """
        INSERT INTO notes (id, user_id, source_chat_id, source_name, message_text, timestamp, is_favorite)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (1, 1, "s1", "src", "nope", "2025-01-01 00:00:00", 0),
    )
    conn.execute(
        """
        INSERT INTO notes_fts (rowid, message_text, source_name)
        VALUES (?, ?, ?)
        """,
        (1, "matchme", "src"),
    )
    conn.commit()

    @contextmanager
    def _fake_db():
        yield conn

    monkeypatch.setattr(
        "src.infrastructure.persistence.repositories.note_repository.get_db_connection",
        _fake_db,
        raising=True,
    )

    repo = SQLiteNoteRepository()
    notes, total = repo.search(NoteFilter(user_id=1, search_query="matchme", limit=10, offset=0))
    assert total == 1
    assert len(notes) == 1
    assert notes[0].id == 1


def test_search_query_falls_back_to_like_when_fts_missing(monkeypatch: pytest.MonkeyPatch, conn) -> None:
    conn.execute(
        """
        INSERT INTO notes (id, user_id, source_chat_id, source_name, message_text, timestamp, is_favorite)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (1, 1, "s1", "src", "hello matchme", "2025-01-01 00:00:00", 0),
    )
    conn.commit()

    @contextmanager
    def _fake_db():
        yield conn

    monkeypatch.setattr(
        "src.infrastructure.persistence.repositories.note_repository.get_db_connection",
        _fake_db,
        raising=True,
    )

    repo = SQLiteNoteRepository()
    notes, total = repo.search(NoteFilter(user_id=1, search_query="matchme", limit=10, offset=0))
    assert total == 1
    assert len(notes) == 1
    assert notes[0].id == 1

