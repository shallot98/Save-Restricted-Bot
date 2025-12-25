"""
Unit tests for sqlite connection PRAGMA configuration.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from src.infrastructure.persistence.sqlite.connection import _configure_connection


class TestSQLitePragmas:
    def test_configure_connection_enables_wal(self, tmp_path: Path) -> None:
        db_path = tmp_path / "notes.db"
        conn = sqlite3.connect(str(db_path))
        try:
            _configure_connection(conn, timeout_seconds=0.5)
            journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            assert str(journal_mode).lower() == "wal"

            synchronous = conn.execute("PRAGMA synchronous").fetchone()[0]
            assert int(synchronous) == 1  # NORMAL

            foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
            assert int(foreign_keys) == 1
        finally:
            conn.close()

