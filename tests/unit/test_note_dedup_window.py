"""Duplicate detection must honour the configured time window.

Timestamps are stored as naive local-time strings, so comparing them against
SQLite's ``datetime('now')`` (always UTC) silently widened the window by the
storage timezone's UTC offset. These tests pin the effective window instead of
the SQL text, so they fail for any regression that reintroduces a basis
mismatch.
"""

from __future__ import annotations

import sqlite3
from datetime import timedelta

import pytest

from src.core.constants import AppConstants
from src.core.utils.datetime_utils import db_now, format_db_datetime
from src.infrastructure.persistence.repositories.note_repository_duplicates import (
    DuplicateCheckRequest,
    SQLiteNoteDuplicateMixin,
)

USER_ID = 1
SOURCE_CHAT_ID = "-1001234567890"
MESSAGE_TEXT = "同一条消息"


@pytest.fixture()
def cursor():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            source_chat_id TEXT,
            message_text TEXT,
            timestamp TEXT,
            media_group_id TEXT
        )
        """
    )
    try:
        yield conn.cursor()
    finally:
        conn.close()


def _insert_note(cursor, *, age_seconds: float, text: str = MESSAGE_TEXT) -> int:
    """Insert a note aged ``age_seconds``, written exactly as production does."""
    timestamp = format_db_datetime(db_now() - timedelta(seconds=age_seconds))
    cursor.execute(
        """INSERT INTO notes (user_id, source_chat_id, message_text, timestamp)
           VALUES (?, ?, ?, ?)""",
        (USER_ID, SOURCE_CHAT_ID, text, timestamp),
    )
    return int(cursor.lastrowid)


def _find(cursor, text: str = MESSAGE_TEXT):
    return SQLiteNoteDuplicateMixin._find_message_duplicate_id(
        cursor,
        DuplicateCheckRequest(
            user_id=USER_ID,
            source_chat_id=SOURCE_CHAT_ID,
            message_text=text,
        ),
    )


def test_note_inside_the_window_is_a_duplicate(cursor) -> None:
    note_id = _insert_note(cursor, age_seconds=1)

    assert _find(cursor) == note_id


@pytest.mark.parametrize("age_seconds", [60, 3600, 8 * 3600, 24 * 3600])
def test_note_older_than_the_window_is_not_a_duplicate(cursor, age_seconds) -> None:
    """Guards the UTC/local basis mismatch that widened the window to ~8 hours."""
    _insert_note(cursor, age_seconds=age_seconds)

    assert _find(cursor) is None


def test_window_boundary_matches_the_configured_constant(cursor) -> None:
    window = AppConstants.Time.DB_DEDUP_WINDOW
    _insert_note(cursor, age_seconds=window * 4)

    assert _find(cursor) is None, (
        f"配置窗口为 {window}s，但 {window * 4}s 前的笔记仍被判为重复"
    )


def test_different_text_is_never_a_duplicate(cursor) -> None:
    _insert_note(cursor, age_seconds=1)

    assert _find(cursor, text="另一条消息") is None


def test_missing_text_short_circuits(cursor) -> None:
    _insert_note(cursor, age_seconds=1)

    assert _find(cursor, text="") is None
