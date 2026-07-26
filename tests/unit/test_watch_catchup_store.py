"""Unit tests for watch catch-up cursor store (in-memory sqlite)."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager

import bot.services.watch_catchup_store as store


def _install_memory_db(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE watch_catchup_cursors (
            source_chat_id TEXT PRIMARY KEY,
            last_seen_id INTEGER NOT NULL DEFAULT 0,
            initialized INTEGER NOT NULL DEFAULT 0,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.commit()

    @contextmanager
    def fake_conn():
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    monkeypatch.setattr(store, "get_db_connection", fake_conn)
    return conn


def test_ensure_and_advance_cursor(monkeypatch):
    _install_memory_db(monkeypatch)

    assert store.get_cursor("-1001") is None

    cursor = store.ensure_cursor_initialized("-1001", 50)
    assert cursor.initialized is True
    assert cursor.last_seen_id == 50

    # Re-init should not rewind an initialized cursor.
    cursor = store.ensure_cursor_initialized("-1001", 10)
    assert cursor.last_seen_id == 50

    store.advance_cursor("-1001", 55)
    cursor = store.get_cursor("-1001")
    assert cursor is not None
    assert cursor.last_seen_id == 55

    # Never move backwards.
    store.advance_cursor("-1001", 40)
    cursor = store.get_cursor("-1001")
    assert cursor is not None
    assert cursor.last_seen_id == 55
