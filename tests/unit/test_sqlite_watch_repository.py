"""
Unit tests for SQLiteWatchRepository.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager

import pytest

from src.domain.entities.watch import WatchTask
from src.infrastructure.persistence.repositories.sqlite_watch_repository import SQLiteWatchRepository


def _create_watch_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE watch_tasks (
            user_id TEXT NOT NULL,
            watch_key TEXT NOT NULL,
            watch_id TEXT,
            source_id TEXT NOT NULL,
            dest_id TEXT,
            record_mode INTEGER NOT NULL DEFAULT 0,
            whitelist_json TEXT NOT NULL DEFAULT '[]',
            blacklist_json TEXT NOT NULL DEFAULT '[]',
            whitelist_regex_json TEXT NOT NULL DEFAULT '[]',
            blacklist_regex_json TEXT NOT NULL DEFAULT '[]',
            preserve_forward_source INTEGER NOT NULL DEFAULT 0,
            forward_mode TEXT NOT NULL DEFAULT 'full',
            extract_patterns_json TEXT NOT NULL DEFAULT '[]',
            PRIMARY KEY (user_id, watch_key)
        )
        """
    )


def test_sqlite_watch_repository_loads_and_indexes(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _create_watch_schema(conn)

    conn.execute(
        """
        INSERT INTO watch_tasks (user_id, watch_key, source_id, dest_id, record_mode)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("1", "s1|record", "s1", None, 1),
    )
    conn.execute(
        """
        INSERT INTO watch_tasks (user_id, watch_key, source_id, dest_id, record_mode, forward_mode)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("2", "s1|d1", "s1", "d1", 0, "extract"),
    )
    conn.commit()

    @contextmanager
    def _fake_db():
        yield conn

    monkeypatch.setattr(
        "src.infrastructure.persistence.repositories.sqlite_watch_repository.get_db_connection",
        _fake_db,
        raising=True,
    )

    repo = SQLiteWatchRepository()
    tasks = repo.get_tasks_for_source("s1")
    assert {(u, k) for (u, k, _t) in tasks} == {("1", "s1|record"), ("2", "s1|d1")}

    task_by_key = {k: t for (_u, k, t) in tasks}
    assert task_by_key["s1|record"].record_mode is True
    assert task_by_key["s1|d1"].dest == "d1"
    assert task_by_key["s1|d1"].forward_mode == "extract"


def test_sqlite_watch_repository_add_and_remove_task(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _create_watch_schema(conn)

    @contextmanager
    def _fake_db():
        yield conn

    monkeypatch.setattr(
        "src.infrastructure.persistence.repositories.sqlite_watch_repository.get_db_connection",
        _fake_db,
        raising=True,
    )

    repo = SQLiteWatchRepository()
    task = WatchTask(source="s2", dest="d2", whitelist=["ok"], forward_mode="full")
    repo.add_task("1", "s2|d2", task)

    loaded = repo.get_task("1", "s2|d2")
    assert loaded is not None
    assert loaded.source == "s2"
    assert loaded.dest == "d2"
    assert loaded.whitelist == ["ok"]
    assert loaded.watch_id is not None

    assert repo.get_monitored_sources() == {"s2"}
    assert repo.remove_task("1", "s2|d2") is True
    assert repo.get_monitored_sources() == set()


def test_sqlite_watch_repository_resolves_legacy_watch_key(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _create_watch_schema(conn)

    @contextmanager
    def _fake_db():
        yield conn

    monkeypatch.setattr(
        "src.infrastructure.persistence.repositories.sqlite_watch_repository.get_db_connection",
        _fake_db,
        raising=True,
    )

    repo = SQLiteWatchRepository()
    repo.add_task("1", "s3|d1", WatchTask(source="s3", dest="d1"))
    assert repo.get_task("1", "s3") is not None

    repo.add_task("1", "s3|d2", WatchTask(source="s3", dest="d2"))
    assert repo.get_task("1", "s3") is None
