"""
Unit tests for SQLiteCalibrationRepository datetime parsing.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime

import pytest

from src.infrastructure.persistence.repositories.calibration_repository import SQLiteCalibrationRepository


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE calibration_tasks (
            id INTEGER PRIMARY KEY,
            note_id INTEGER NOT NULL,
            magnet_hash TEXT NOT NULL,
            status TEXT NOT NULL,
            retry_count INTEGER DEFAULT 0,
            last_attempt TEXT,
            next_attempt TEXT NOT NULL,
            error_message TEXT,
            created_at TEXT
        )
        """
    )
    connection.execute(
        """
        INSERT INTO calibration_tasks
            (id, note_id, magnet_hash, status, retry_count, last_attempt, next_attempt, error_message, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            1,
            10,
            "ABC",
            "pending",
            0,
            "2025-01-01 00:00:00",
            "2025-01-01 00:10:00",
            None,
            "2025-01-01 00:00:00",
        ),
    )
    connection.commit()
    yield connection
    connection.close()


def test_get_by_id_parses_datetimes(monkeypatch: pytest.MonkeyPatch, conn) -> None:
    @contextmanager
    def _fake_db():
        yield conn

    monkeypatch.setattr(
        "src.infrastructure.persistence.repositories.calibration_repository.get_db_connection",
        _fake_db,
        raising=True,
    )

    repo = SQLiteCalibrationRepository()
    task = repo.get_by_id(1)
    assert task is not None
    assert isinstance(task.last_attempt, datetime)
    assert isinstance(task.next_attempt, datetime)
    assert isinstance(task.created_at, datetime)

