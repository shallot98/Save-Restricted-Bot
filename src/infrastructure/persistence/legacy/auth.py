"""遗留认证 helper（原仓库根 ``database_auth.py``）。

依赖以 ``db_connection_factory`` 形式由调用方注入，因此本模块对根目录与表现层
零 import，可以整体下沉到 infrastructure（报告 §5.4 迁移映射末三行）。
"""

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
