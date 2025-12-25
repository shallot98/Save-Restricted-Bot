"""
Unit tests for default admin password initialization.
"""

from __future__ import annotations

import sqlite3

import bcrypt
import pytest

from src.infrastructure.persistence.sqlite import migrations


def _create_users_table(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
        """
    )


class TestDefaultAdminPassword:
    def test_uses_admin_password_env_when_provided(self, monkeypatch: pytest.MonkeyPatch) -> None:
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        _create_users_table(cursor)

        monkeypatch.setenv("ADMIN_PASSWORD", "secret123")
        migrations._create_default_admin(cursor)

        row = cursor.execute(
            "SELECT password_hash FROM users WHERE username = ?",
            ("admin",),
        ).fetchone()
        assert row is not None
        assert bcrypt.checkpw(b"secret123", row[0].encode("utf-8"))

    def test_defaults_to_admin_when_env_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        _create_users_table(cursor)

        monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
        migrations._create_default_admin(cursor)

        row = cursor.execute(
            "SELECT password_hash FROM users WHERE username = ?",
            ("admin",),
        ).fetchone()
        assert row is not None
        assert bcrypt.checkpw(b"admin", row[0].encode("utf-8"))

