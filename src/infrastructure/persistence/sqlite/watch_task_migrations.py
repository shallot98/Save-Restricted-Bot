"""
Watch Task Migrations
=====================

Helpers for watch task schema updates and legacy JSON migration.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Tuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LegacyWatchPayload:
    source_id: str
    dest_id: Any
    record_mode: int
    whitelist: Iterable[Any]
    blacklist: Iterable[Any]
    whitelist_regex: Iterable[Any]
    blacklist_regex: Iterable[Any]
    preserve_forward_source: int
    forward_mode: str
    extract_patterns: Iterable[Any]


def apply_watch_task_schema_updates(cursor: sqlite3.Cursor) -> None:
    """Ensure watch_tasks has watch_id values and supporting index."""
    existing_columns = _existing_watch_columns(cursor)
    if not existing_columns:
        return
    if "watch_id" not in existing_columns and not _add_watch_id_column(cursor):
        return

    existing_ids, missing_rows = _load_watch_id_state(cursor)
    if missing_rows:
        _backfill_missing_watch_ids(cursor, existing_ids, missing_rows)
    _create_watch_id_index(cursor)


def migrate_watch_config_from_json(cursor: sqlite3.Cursor) -> None:
    """Best-effort migration from legacy watch_config.json into watch_tasks.

    ``watch_config.json`` is a read-only legacy artifact: nothing writes it any
    more (``SQLiteWatchRepository._sync_to_json`` was removed), so this is a
    one-way import that only runs while ``watch_tasks`` is still empty.
    """
    if not _watch_tasks_is_empty(cursor):
        return

    try:
        from src.core.config import settings
    except Exception as exc:
        logger.warning(f"Skip watch config migration (settings unavailable): {exc}")
        return

    watch_file: Path = settings.paths.watch_file
    if not watch_file.exists():
        return

    try:
        raw = json.loads(watch_file.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(f"Skip watch config migration (invalid json): {exc}")
        return

    rows = _normalize_legacy_watch_rows(raw)
    if not rows:
        return

    try:
        cursor.executemany(
            """
            INSERT INTO watch_tasks (
                user_id,
                watch_key,
                source_id,
                dest_id,
                record_mode,
                whitelist_json,
                blacklist_json,
                whitelist_regex_json,
                blacklist_regex_json,
                preserve_forward_source,
                forward_mode,
                extract_patterns_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        logger.info(f"Migrated watch config from json: users={len(raw)} tasks={len(rows)}")
    except sqlite3.Error as exc:
        logger.warning(f"Failed to migrate watch config from json: {exc}")


def _existing_watch_columns(cursor: sqlite3.Cursor) -> set[str]:
    try:
        cursor.execute("PRAGMA table_info(watch_tasks)")
        return {col[1] for col in cursor.fetchall()}
    except sqlite3.Error as exc:
        logger.warning(f"Skip watch_tasks migrations (table unavailable): {exc}")
        return set()


def _add_watch_id_column(cursor: sqlite3.Cursor) -> bool:
    try:
        cursor.execute("ALTER TABLE watch_tasks ADD COLUMN watch_id TEXT")
        logger.info("Added column: watch_tasks.watch_id")
        return True
    except sqlite3.Error as exc:
        logger.warning(f"Failed to add watch_tasks.watch_id: {exc}")
        return False


def _load_watch_id_state(cursor: sqlite3.Cursor) -> Tuple[set[str], list[tuple[str, str]]]:
    try:
        cursor.execute(
            "SELECT watch_id FROM watch_tasks WHERE watch_id IS NOT NULL AND TRIM(watch_id) != ''"
        )
        existing_ids = {str(row[0]) for row in cursor.fetchall()}
        cursor.execute(
            "SELECT user_id, watch_key FROM watch_tasks WHERE watch_id IS NULL OR TRIM(watch_id) = ''"
        )
        missing_rows = [(str(row[0]), str(row[1])) for row in cursor.fetchall()]
        return existing_ids, missing_rows
    except sqlite3.Error as exc:
        logger.warning(f"Skip watch_id backfill (query failed): {exc}")
        return set(), []


def _backfill_missing_watch_ids(
    cursor: sqlite3.Cursor,
    existing_ids: set[str],
    missing_rows: list[tuple[str, str]],
) -> None:
    for user_id, watch_key in missing_rows:
        watch_id = _generate_watch_id(existing_ids)
        try:
            cursor.execute(
                "UPDATE watch_tasks SET watch_id = ? WHERE user_id = ? AND watch_key = ?",
                (watch_id, user_id, watch_key),
            )
        except sqlite3.Error as exc:
            logger.warning(f"Failed to backfill watch_id for {user_id}:{watch_key}: {exc}")
    logger.info(f"Backfilled watch_id for watch_tasks rows: {len(missing_rows)}")


def _generate_watch_id(existing_ids: set[str]) -> str:
    while True:
        watch_id = uuid.uuid4().hex
        if watch_id not in existing_ids:
            existing_ids.add(watch_id)
            return watch_id


def _create_watch_id_index(cursor: sqlite3.Cursor) -> None:
    try:
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_watch_tasks_watch_id ON watch_tasks(watch_id)"
        )
    except sqlite3.Error as exc:
        logger.warning(f"Failed to create idx_watch_tasks_watch_id: {exc}")


def _watch_tasks_is_empty(cursor: sqlite3.Cursor) -> bool:
    try:
        cursor.execute("SELECT 1 FROM watch_tasks LIMIT 1")
        return cursor.fetchone() is None
    except sqlite3.Error as exc:
        logger.warning(f"Skip watch config migration (watch_tasks unavailable): {exc}")
        return False


def _normalize_legacy_watch_rows(raw: Any) -> List[Tuple[Any, ...]]:
    if not isinstance(raw, dict) or not raw:
        return []

    rows: List[Tuple[Any, ...]] = []
    for user_id, user_data in raw.items():
        if not isinstance(user_data, dict):
            continue
        for watch_key, watch_data in user_data.items():
            normalized = _normalize_legacy_watch_row(user_id, watch_key, watch_data)
            if normalized is not None:
                rows.append(normalized)
    return rows


def _normalize_legacy_watch_row(user_id: Any, watch_key: Any, watch_data: Any) -> Tuple[Any, ...] | None:
    payload = _legacy_watch_payload(watch_key, watch_data)
    if not payload.source_id:
        return None

    return (
        str(user_id),
        _canonical_legacy_watch_key(watch_key, payload),
        payload.source_id,
        None if payload.dest_id is None else str(payload.dest_id),
        payload.record_mode,
        _json_list(payload.whitelist),
        _json_list(payload.blacklist),
        _json_list(payload.whitelist_regex),
        _json_list(payload.blacklist_regex),
        payload.preserve_forward_source,
        payload.forward_mode,
        _json_list(payload.extract_patterns),
    )


def _legacy_watch_payload(watch_key: Any, watch_data: Any) -> LegacyWatchPayload:
    if not isinstance(watch_data, dict):
        return LegacyWatchPayload(
            source_id=_source_id_from_watch_key(watch_key),
            dest_id=watch_data,
            record_mode=0,
            whitelist=[],
            blacklist=[],
            whitelist_regex=[],
            blacklist_regex=[],
            preserve_forward_source=0,
            forward_mode="full",
            extract_patterns=[],
        )

    source_id = str(watch_data.get("source") or "").strip()
    return LegacyWatchPayload(
        source_id=source_id or _source_id_from_watch_key(watch_key),
        dest_id=watch_data.get("dest"),
        record_mode=1 if bool(watch_data.get("record_mode", False)) else 0,
        whitelist=watch_data.get("whitelist", []) or [],
        blacklist=watch_data.get("blacklist", []) or [],
        whitelist_regex=watch_data.get("whitelist_regex", []) or [],
        blacklist_regex=watch_data.get("blacklist_regex", []) or [],
        preserve_forward_source=1 if bool(watch_data.get("preserve_forward_source", False)) else 0,
        forward_mode=str(watch_data.get("forward_mode", "full") or "full"),
        extract_patterns=watch_data.get("extract_patterns", []) or [],
    )


def _source_id_from_watch_key(watch_key: Any) -> str:
    key = str(watch_key)
    return str(key.split("|")[0] if "|" in key else watch_key).strip()


def _canonical_legacy_watch_key(watch_key: Any, payload: LegacyWatchPayload) -> str:
    canonical_key = str(watch_key)
    if "|" in canonical_key:
        return canonical_key
    if payload.record_mode:
        return f"{payload.source_id}|record"
    if payload.dest_id is not None:
        return f"{payload.source_id}|{payload.dest_id}"
    return payload.source_id or canonical_key


def _json_list(values: Iterable[Any]) -> str:
    return json.dumps(list(values), ensure_ascii=False)
