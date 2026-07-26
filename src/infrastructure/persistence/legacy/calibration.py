"""Legacy calibration-task helpers for the root database module."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Optional
from zoneinfo import ZoneInfo

from src.core.utils.datetime_utils import format_db_datetime


@dataclass(frozen=True)
class CalibrationDeps:
    db_connection_factory: Callable[[], Any]
    timezone: ZoneInfo


@dataclass(frozen=True)
class CalibrationTaskCreate:
    note_id: int
    magnet_hash: str
    delay_seconds: int = 600


@dataclass(frozen=True)
class CalibrationTaskUpdate:
    task_id: int
    status: str
    error_message: Optional[str] = None
    next_retry_seconds: Optional[int] = None


@dataclass(frozen=True)
class CalibrationTaskQuery:
    status: Optional[str] = None
    limit: int = 100
    offset: int = 0


def get_calibration_config(deps: CalibrationDeps) -> Optional[dict[str, Any]]:
    with deps.db_connection_factory() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM auto_calibration_config WHERE id = 1")
        row = cursor.fetchone()
        return dict(row) if row else None


def update_calibration_config(deps: CalibrationDeps, config: dict[str, Any]) -> bool:
    with deps.db_connection_factory() as conn:
        cursor = conn.cursor()
        cursor.execute(_UPDATE_CONFIG_SQL, _config_values(config))
        return cursor.rowcount > 0


def _config_values(config: dict[str, Any]) -> tuple[Any, ...]:
    return (
        config.get("enabled", 0),
        config.get("filter_mode", "empty_only"),
        config.get("first_delay", 600),
        config.get("retry_delay_1", 3600),
        config.get("retry_delay_2", 14400),
        config.get("retry_delay_3", 28800),
        config.get("max_retries", 3),
        config.get("concurrent_limit", 5),
        config.get("timeout_per_magnet", 30),
        config.get("batch_timeout", 300),
    )


def add_calibration_task(deps: CalibrationDeps, task: CalibrationTaskCreate) -> Optional[int]:
    with deps.db_connection_factory() as conn:
        cursor = conn.cursor()
        cursor.execute(_EXISTING_TASK_SQL, (task.note_id, task.magnet_hash))
        if cursor.fetchone():
            return None

        now = datetime.now(deps.timezone)
        next_attempt = now + timedelta(seconds=task.delay_seconds)
        cursor.execute(
            _INSERT_TASK_SQL,
            (
                task.note_id,
                task.magnet_hash,
                format_db_datetime(next_attempt),
                format_db_datetime(now),
            ),
        )
        return cursor.lastrowid


def get_pending_calibration_tasks(deps: CalibrationDeps, limit: int = 100) -> list[dict[str, Any]]:
    with deps.db_connection_factory() as conn:
        cursor = conn.cursor()
        now = format_db_datetime(datetime.now(deps.timezone))
        cursor.execute(_PENDING_TASKS_SQL, (now, limit))
        return [dict(row) for row in cursor.fetchall()]


def update_calibration_task(deps: CalibrationDeps, update: CalibrationTaskUpdate) -> bool:
    with deps.db_connection_factory() as conn:
        cursor = conn.cursor()
        now = format_db_datetime(datetime.now(deps.timezone))
        if update.status == "retrying" and update.next_retry_seconds:
            _update_retrying_task(deps, cursor, update, now)
        else:
            cursor.execute(
                _UPDATE_TASK_SQL,
                (update.status, now, update.error_message, update.task_id),
            )
        return cursor.rowcount > 0


def _update_retrying_task(
    deps: CalibrationDeps,
    cursor: Any,
    update: CalibrationTaskUpdate,
    now: str,
) -> None:
    next_attempt = datetime.now(deps.timezone) + timedelta(seconds=update.next_retry_seconds)
    cursor.execute(
        _UPDATE_RETRY_TASK_SQL,
        (
            update.status,
            now,
            format_db_datetime(next_attempt),
            update.error_message,
            update.task_id,
        ),
    )


def get_calibration_stats(deps: CalibrationDeps) -> dict[str, Any]:
    with deps.db_connection_factory() as conn:
        cursor = conn.cursor()
        stats = {"total": _fetch_total_count(cursor)}
        stats["by_status"] = _fetch_counts_by_status(cursor)
        stats["ready_to_process"] = _fetch_ready_count(deps, cursor)
        return stats


def _fetch_total_count(cursor: Any) -> int:
    cursor.execute("SELECT COUNT(*) FROM calibration_tasks")
    return cursor.fetchone()[0]


def _fetch_counts_by_status(cursor: Any) -> dict[str, int]:
    cursor.execute("SELECT status, COUNT(*) as count FROM calibration_tasks GROUP BY status")
    return {row[0]: row[1] for row in cursor.fetchall()}


def _fetch_ready_count(deps: CalibrationDeps, cursor: Any) -> int:
    now = format_db_datetime(datetime.now(deps.timezone))
    cursor.execute(_READY_TASKS_SQL, (now,))
    return cursor.fetchone()[0]


def delete_calibration_task(deps: CalibrationDeps, task_id: int) -> bool:
    with deps.db_connection_factory() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM calibration_tasks WHERE id = ?", (task_id,))
        return cursor.rowcount > 0


def delete_calibration_tasks_by_note_id(deps: CalibrationDeps, note_id: int) -> int:
    with deps.db_connection_factory() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM calibration_tasks WHERE note_id = ?", (note_id,))
        return cursor.rowcount


def clear_completed_calibration_tasks(deps: CalibrationDeps, days: int = 7) -> int:
    with deps.db_connection_factory() as conn:
        cursor = conn.cursor()
        cutoff = format_db_datetime(datetime.now(deps.timezone) - timedelta(days=days))
        cursor.execute(_CLEAR_COMPLETED_TASKS_SQL, (cutoff,))
        return cursor.rowcount


def get_all_calibration_tasks(
    deps: CalibrationDeps,
    query: CalibrationTaskQuery,
) -> list[dict[str, Any]]:
    with deps.db_connection_factory() as conn:
        cursor = conn.cursor()
        sql, params = _build_all_tasks_query(query)
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


def _build_all_tasks_query(query: CalibrationTaskQuery) -> tuple[str, list[Any]]:
    sql = "SELECT * FROM calibration_tasks WHERE 1=1"
    params: list[Any] = []
    if query.status:
        sql += " AND status = ?"
        params.append(query.status)
    sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([query.limit, query.offset])
    return sql, params


_UPDATE_CONFIG_SQL = """
    UPDATE auto_calibration_config
    SET enabled = ?, filter_mode = ?, first_delay = ?,
        retry_delay_1 = ?, retry_delay_2 = ?, retry_delay_3 = ?,
        max_retries = ?, concurrent_limit = ?,
        timeout_per_magnet = ?, batch_timeout = ?
    WHERE id = 1
"""

_EXISTING_TASK_SQL = """
    SELECT id FROM calibration_tasks
    WHERE note_id = ? AND magnet_hash = ? AND status IN ('pending', 'retrying')
"""

_INSERT_TASK_SQL = """
    INSERT INTO calibration_tasks (note_id, magnet_hash, status, next_attempt, created_at)
    VALUES (?, ?, 'pending', ?, ?)
"""

_PENDING_TASKS_SQL = """
    SELECT * FROM calibration_tasks
    WHERE status IN ('pending', 'retrying')
    AND next_attempt <= ?
    ORDER BY next_attempt ASC
    LIMIT ?
"""

_UPDATE_TASK_SQL = """
    UPDATE calibration_tasks
    SET status = ?, last_attempt = ?, error_message = ?
    WHERE id = ?
"""

_UPDATE_RETRY_TASK_SQL = """
    UPDATE calibration_tasks
    SET status = ?, retry_count = retry_count + 1,
        last_attempt = ?, next_attempt = ?, error_message = ?
    WHERE id = ?
"""

_READY_TASKS_SQL = """
    SELECT COUNT(*) FROM calibration_tasks
    WHERE status IN ('pending', 'retrying') AND next_attempt <= ?
"""

_CLEAR_COMPLETED_TASKS_SQL = """
    DELETE FROM calibration_tasks
    WHERE status = 'success' AND created_at < ?
"""
