"""
Unit test to ensure update_note_with_calibrated_dns is safe under concurrent updates.
"""

from __future__ import annotations

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
import re as re_module

import pytest

import database


def _create_notes_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE notes (
            id INTEGER PRIMARY KEY,
            message_text TEXT,
            magnet_link TEXT,
            filename TEXT,
            user_id INTEGER
        )
        """
    )


def test_update_note_with_calibrated_dns_merges_concurrent_updates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "notes.db"
    conn = sqlite3.connect(str(db_path))
    try:
        _create_notes_schema(conn)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=2000")
        conn.execute(
            """
            INSERT INTO notes (id, message_text, magnet_link, filename, user_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                1,
                "magnet:?xt=urn:btih:AAA\nmagnet:?xt=urn:btih:BBB\n",
                "magnet:?xt=urn:btih:AAA",
                None,
                1,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    @contextmanager
    def _fake_db_connection():
        connection = sqlite3.connect(str(db_path), timeout=2.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=2000")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    monkeypatch.setattr(database, "get_db_connection", _fake_db_connection, raising=True)

    original_sub = database.re.sub
    barrier = threading.Barrier(2)
    call_lock = threading.Lock()
    call_count = {"n": 0}

    class _ReProxy:
        IGNORECASE = re_module.IGNORECASE

        @staticmethod
        def escape(*args, **kwargs):
            return re_module.escape(*args, **kwargs)

        @staticmethod
        def sub(*args, **kwargs):
            with call_lock:
                call_count["n"] += 1
                current = call_count["n"]
            if current <= 2:
                barrier.wait(timeout=5)
            return original_sub(*args, **kwargs)

    monkeypatch.setattr(database, "re", _ReProxy, raising=True)

    result_a = {
        "info_hash": "AAA",
        "old_magnet": "magnet:?xt=urn:btih:AAA",
        "filename": "fileA",
        "success": True,
    }
    result_b = {
        "info_hash": "BBB",
        "old_magnet": "magnet:?xt=urn:btih:BBB",
        "filename": "fileB",
        "success": True,
    }

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(database.update_note_with_calibrated_dns, 1, [result_a])
        future_b = executor.submit(database.update_note_with_calibrated_dns, 1, [result_b])

        assert future_a.result(timeout=10) is True
        assert future_b.result(timeout=10) is True

    conn = sqlite3.connect(str(db_path))
    try:
        message_text = conn.execute("SELECT message_text FROM notes WHERE id = 1").fetchone()[0]
    finally:
        conn.close()

    assert "btih:AAA&dn=fileA" in message_text
    assert "btih:BBB&dn=fileB" in message_text
