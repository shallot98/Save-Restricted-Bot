"""
Notes FTS Migrations
====================

Helpers for notes_fts creation, validation, and trigger repair.
"""

from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)

_EXPECTED_FTS_COLUMNS = {"message_text", "source_name"}


def create_or_rebuild_notes_fts(cursor: sqlite3.Cursor) -> None:
    """Create notes_fts and keep its triggers/schema compatible."""
    has_fts = _notes_fts_exists(cursor)
    if not _ensure_fts_table(cursor):
        return
    if not _fts_schema_matches(cursor):
        has_fts = _rebuild_fts_table(cursor)
        if has_fts is None:
            return
    _ensure_fts_triggers(cursor)
    if not has_fts:
        _rebuild_fts_content(cursor)


def _notes_fts_exists(cursor: sqlite3.Cursor) -> bool:
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='notes_fts' LIMIT 1"
    )
    return cursor.fetchone() is not None


def _ensure_fts_table(cursor: sqlite3.Cursor) -> bool:
    try:
        cursor.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
                message_text,
                source_name,
                content='notes',
                content_rowid='id',
                tokenize='unicode61'
            )
            """
        )
        return True
    except sqlite3.OperationalError as exc:
        logger.warning(f"SQLite FTS5 unavailable, skip notes_fts: {exc}")
        return False


def _fts_schema_matches(cursor: sqlite3.Cursor) -> bool:
    try:
        cursor.execute("PRAGMA table_info(notes_fts)")
        columns = {row[1] for row in cursor.fetchall()}
        return _EXPECTED_FTS_COLUMNS.issubset(columns)
    except sqlite3.Error as exc:
        logger.warning(f"Failed to inspect notes_fts schema: {exc}")
        return False


def _rebuild_fts_table(cursor: sqlite3.Cursor) -> bool | None:
    logger.warning("notes_fts schema mismatch, rebuilding index")
    try:
        cursor.execute("DROP TRIGGER IF EXISTS notes_fts_ai")
        cursor.execute("DROP TRIGGER IF EXISTS notes_fts_ad")
        cursor.execute("DROP TRIGGER IF EXISTS notes_fts_au")
        cursor.execute("DROP TABLE IF EXISTS notes_fts")
        cursor.execute(
            """
            CREATE VIRTUAL TABLE notes_fts USING fts5(
                message_text,
                source_name,
                content='notes',
                content_rowid='id',
                tokenize='unicode61'
            )
            """
        )
        return False
    except sqlite3.Error as exc:
        logger.warning(f"Failed to rebuild notes_fts: {exc}")
        return None


def _ensure_fts_triggers(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        """
        CREATE TRIGGER IF NOT EXISTS notes_fts_ai
        AFTER INSERT ON notes
        BEGIN
            INSERT INTO notes_fts(rowid, message_text, source_name)
            VALUES (new.id, new.message_text, new.source_name);
        END
        """
    )
    cursor.execute(
        """
        CREATE TRIGGER IF NOT EXISTS notes_fts_ad
        AFTER DELETE ON notes
        BEGIN
            INSERT INTO notes_fts(notes_fts, rowid, message_text, source_name)
            VALUES('delete', old.id, old.message_text, old.source_name);
        END
        """
    )
    cursor.execute(
        """
        CREATE TRIGGER IF NOT EXISTS notes_fts_au
        AFTER UPDATE OF message_text, source_name ON notes
        BEGIN
            INSERT INTO notes_fts(notes_fts, rowid, message_text, source_name)
            VALUES('delete', old.id, old.message_text, old.source_name);
            INSERT INTO notes_fts(rowid, message_text, source_name)
            VALUES (new.id, new.message_text, new.source_name);
        END
        """
    )


def _rebuild_fts_content(cursor: sqlite3.Cursor) -> None:
    try:
        cursor.execute("INSERT INTO notes_fts(notes_fts) VALUES('rebuild')")
        logger.info("notes_fts created and rebuilt")
    except sqlite3.OperationalError as exc:
        logger.warning(f"Failed to rebuild notes_fts: {exc}")
