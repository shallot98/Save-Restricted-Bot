"""Legacy authentication helpers for the root database module."""

from __future__ import annotations

from typing import Any, Callable

import bcrypt


def verify_user(db_connection_factory: Callable[[], Any], username: str, password: str) -> bool:
    with db_connection_factory() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
        result = cursor.fetchone()
        if not result:
            return False
        return bcrypt.checkpw(password.encode("utf-8"), result[0].encode("utf-8"))


def update_password(db_connection_factory: Callable[[], Any], username: str, new_password: str) -> None:
    with db_connection_factory() as conn:
        cursor = conn.cursor()
        password_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        cursor.execute("UPDATE users SET password_hash = ? WHERE username = ?", (password_hash, username))
