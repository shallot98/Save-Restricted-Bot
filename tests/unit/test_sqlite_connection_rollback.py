"""
Unit tests for connection-level transaction safety.

覆盖两点回归：
1. 非 sqlite 异常必须回滚 + 记日志 + 原样抛出（此前直接跳到 close()，无回滚无日志）
2. monitoring 子系统停用后，连接不再被 db_tracer 包装
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pytest

from src.infrastructure.persistence.sqlite.connection import DatabaseConnection


class _RollbackSpy(sqlite3.Connection):
    """记录 rollback 调用次数的连接子类。"""

    rollback_calls = 0

    def rollback(self) -> None:  # type: ignore[override]
        type(self).rollback_calls += 1
        super().rollback()


@pytest.fixture
def manager(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> DatabaseConnection:
    instance = DatabaseConnection()
    monkeypatch.setattr(instance, "_db_path", tmp_path / "notes.db")
    return instance


@pytest.fixture
def rollback_spy(monkeypatch: pytest.MonkeyPatch) -> type[_RollbackSpy]:
    real_connect = sqlite3.connect

    def spy_connect(*args: object, **kwargs: object) -> sqlite3.Connection:
        kwargs.setdefault("factory", _RollbackSpy)
        return real_connect(*args, **kwargs)  # type: ignore[arg-type]

    _RollbackSpy.rollback_calls = 0
    monkeypatch.setattr(sqlite3, "connect", spy_connect)
    return _RollbackSpy


class TestNonSqliteErrorRollback:
    def test_non_sqlite_error_rolls_back_and_reraises(
        self,
        manager: DatabaseConnection,
        rollback_spy: type[_RollbackSpy],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with manager.get_connection() as conn:
            conn.execute("CREATE TABLE t (id INTEGER)")

        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError, match="boom"):
                with manager.get_connection() as conn:
                    conn.execute("INSERT INTO t VALUES (1)")
                    raise ValueError("boom")

        assert rollback_spy.rollback_calls >= 1
        assert any("rolled back" in record.message for record in caplog.records)

        with manager.get_connection() as conn:
            assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 0

    def test_successful_block_commits(self, manager: DatabaseConnection) -> None:
        with manager.get_connection() as conn:
            conn.execute("CREATE TABLE t (id INTEGER)")
            conn.execute("INSERT INTO t VALUES (1)")

        with manager.get_connection() as conn:
            assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1


class TestMonitoringDisabled:
    def test_connection_is_not_wrapped_by_db_tracer(self, manager: DatabaseConnection) -> None:
        with manager.get_connection() as conn:
            # db_tracer 会返回 _TracedConnection 包装器；停用后必须是原生连接
            assert type(conn) is sqlite3.Connection
