"""Persistent catch-up cursors for monitored Telegram sources."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from src.infrastructure.persistence.sqlite.connection import get_db_connection


@dataclass(frozen=True, kw_only=True)
class CatchupCursor:
    source_chat_id: str
    last_seen_id: int
    initialized: bool


def get_cursor(source_chat_id: str) -> Optional[CatchupCursor]:
    source = str(source_chat_id)
    with get_db_connection() as conn:
        row = conn.execute(
            """
            SELECT source_chat_id, last_seen_id, initialized
            FROM watch_catchup_cursors
            WHERE source_chat_id = ?
            """,
            (source,),
        ).fetchone()
    if row is None:
        return None
    return CatchupCursor(
        source_chat_id=str(row[0]),
        last_seen_id=int(row[1] or 0),
        initialized=bool(row[2]),
    )


def ensure_cursor_initialized(source_chat_id: str, latest_message_id: int) -> CatchupCursor:
    """Initialize cursor to latest id without backfilling historical messages."""
    source = str(source_chat_id)
    latest = max(0, int(latest_message_id or 0))
    now = time.time()
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO watch_catchup_cursors (
                source_chat_id, last_seen_id, initialized, updated_at
            ) VALUES (?, ?, 1, ?)
            ON CONFLICT(source_chat_id) DO UPDATE SET
                last_seen_id = CASE
                    WHEN watch_catchup_cursors.initialized = 0
                    THEN excluded.last_seen_id
                    ELSE watch_catchup_cursors.last_seen_id
                END,
                initialized = 1,
                updated_at = excluded.updated_at
            """,
            (source, latest, now),
        )
        conn.commit()
    cursor = get_cursor(source)
    assert cursor is not None
    return cursor


def advance_cursor(source_chat_id: str, message_id: int) -> None:
    """Move high-water mark forward (never backwards)."""
    source = str(source_chat_id)
    message_id = int(message_id)
    if message_id <= 0:
        return
    now = time.time()
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO watch_catchup_cursors (
                source_chat_id, last_seen_id, initialized, updated_at
            ) VALUES (?, ?, 1, ?)
            ON CONFLICT(source_chat_id) DO UPDATE SET
                last_seen_id = MAX(watch_catchup_cursors.last_seen_id, excluded.last_seen_id),
                initialized = 1,
                updated_at = excluded.updated_at
            """,
            (source, message_id, now),
        )
        conn.commit()
