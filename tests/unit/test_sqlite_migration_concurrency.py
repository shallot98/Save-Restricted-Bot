"""
Unit tests for migration race protection.

bot 与 web 两个进程都会在启动时执行 run_migrations()，真正加列的那次
会有一方拿到 "duplicate column name" 并把进程打挂。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from src.infrastructure.persistence.sqlite import migrations


def _legacy_notes_cursor() -> sqlite3.Cursor:
    """建一个只有早期列的 notes 表（模拟老库）。"""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            source_chat_id TEXT NOT NULL,
            message_text TEXT
        )
        """
    )
    return cursor


class TestAddNoteColumn:
    def test_duplicate_column_is_tolerated(self) -> None:
        cursor = _legacy_notes_cursor()

        migrations._add_note_column(cursor, "magnet_link", "TEXT")

        # 裸 ALTER（修复前的写法）在这里必然抛错，正是打挂进程的那条路径
        with pytest.raises(sqlite3.OperationalError, match="duplicate column name"):
            cursor.execute("ALTER TABLE notes ADD COLUMN magnet_link TEXT")

        # 第二次调用等价于「另一进程已经赢得竞态并加过这一列」
        migrations._add_note_column(cursor, "magnet_link", "TEXT")

        cursor.execute("PRAGMA table_info(notes)")
        assert "magnet_link" in {row[1] for row in cursor.fetchall()}

    def test_other_operational_errors_still_raise(self) -> None:
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()

        with pytest.raises(sqlite3.OperationalError, match="no such table"):
            migrations._add_note_column(cursor, "magnet_link", "TEXT")

    def test_apply_column_migrations_is_idempotent(self) -> None:
        cursor = _legacy_notes_cursor()

        migrations._apply_column_migrations(cursor)
        migrations._apply_column_migrations(cursor)

        cursor.execute("PRAGMA table_info(notes)")
        columns = {row[1] for row in cursor.fetchall()}
        assert {
            "media_paths",
            "media_group_id",
            "magnet_link",
            "filename",
            "is_favorite",
        }.issubset(columns)


class TestBeginImmediate:
    def test_takes_write_lock_so_second_migrator_waits(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "notes.db")
        first = sqlite3.connect(db_path)
        second = sqlite3.connect(db_path, timeout=0.1)
        try:
            migrations._begin_immediate(first)
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                migrations._begin_immediate(second)
        finally:
            first.rollback()
            first.close()
            second.close()

    def test_noop_when_already_in_transaction(self, tmp_path: Path) -> None:
        conn = sqlite3.connect(str(tmp_path / "notes.db"))
        try:
            conn.execute("CREATE TABLE t (id INTEGER)")
            conn.execute("INSERT INTO t VALUES (1)")
            assert conn.in_transaction

            migrations._begin_immediate(conn)  # 不应抛 "transaction within a transaction"
        finally:
            conn.rollback()
            conn.close()
