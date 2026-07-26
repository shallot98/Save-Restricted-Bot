"""
SQLite Watch Repository
======================

SQLite-backed persistence for watch configuration.

Notes:
- Keeps an in-memory cache + source index for fast hot-path lookups.
- SQLite is the source of truth; cache is refreshed on writes or explicit reload().
- ``data/config/watch_config.json`` is a read-only legacy artifact. This
  repository never writes it. It is only consumed once by
  ``migrate_watch_config_from_json`` when ``watch_tasks`` is still empty.
  The former ``_sync_to_json`` mirror was removed: it rewrote the whole file
  from one process' cache on every mutation, so bot and web (each holding
  their own repository instance) overwrote each other.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from typing import Optional, List, Set, Dict, Any, Tuple

from src.domain.entities.watch import WatchTask, WatchConfig
from src.domain.repositories.watch_repository import WatchRepository
from src.infrastructure.persistence.repositories.sqlite_watch_repository_helpers import (
    INSERT_WATCH_TASK_SQL,
    SELECT_WATCH_TASKS_SQL,
    UPSERT_WATCH_TASK_SQL,
    canonical_config_for_user,
    canonicalize_watch_key,
    parse_config_dict,
    resolve_watch_key,
    row_to_task,
    task_rows,
    task_to_row,
)
from src.infrastructure.persistence.sqlite.connection import get_db_connection

logger = logging.getLogger(__name__)


class SQLiteWatchRepository(WatchRepository):
    """SQLite implementation of WatchRepository."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._cache: Dict[str, WatchConfig] = {}
        self._source_index: Dict[str, List[Tuple[str, str, WatchTask]]] = {}
        with self._lock:
            self._load_cache()

    def reload(self) -> None:
        with self._lock:
            self._load_cache()

    def _load_cache(self) -> None:
        cache: Dict[str, WatchConfig] = {}

        with get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(SELECT_WATCH_TASKS_SQL)
                rows = cursor.fetchall()
            except sqlite3.Error as e:
                logger.warning(f"Failed to load watch_tasks (treat as empty): {e}")
                rows = []

        for row in rows:
            user_id = str(row["user_id"])
            watch_key = str(row["watch_key"])
            task = row_to_task(dict(row))
            if user_id not in cache:
                cache[user_id] = WatchConfig(user_id=user_id)
            cache[user_id].add_task(watch_key, task)

        self._cache = cache
        self._rebuild_source_index()

    def _rebuild_source_index(self) -> None:
        index: Dict[str, List[Tuple[str, str, WatchTask]]] = {}
        for user_id, config in self._cache.items():
            for watch_key, task in config.tasks.items():
                source_id = str(getattr(task, "source", "") or "")
                if not source_id or source_id == "me":
                    continue
                index.setdefault(source_id, []).append((user_id, watch_key, task))
        self._source_index = index

    def get_user_config(self, user_id: str) -> Optional[WatchConfig]:
        with self._lock:
            return self._cache.get(user_id)

    def get_all_configs(self) -> List[WatchConfig]:
        with self._lock:
            return list(self._cache.values())

    def save_user_config(self, config: WatchConfig) -> None:
        with self._lock:
            user_id = str(config.user_id)
            canonical_config = canonical_config_for_user(user_id, config)

            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM watch_tasks WHERE user_id = ?", (user_id,))
                self._insert_config_rows(cursor, user_id, canonical_config)

            self._cache[user_id] = canonical_config
            self._rebuild_source_index()

    def delete_user_config(self, user_id: str) -> bool:
        with self._lock:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM watch_tasks WHERE user_id = ?", (str(user_id),))
                deleted = cursor.rowcount > 0

            if user_id in self._cache:
                self._cache.pop(user_id, None)
                self._rebuild_source_index()
            return deleted

    def get_task(self, user_id: str, watch_key: str) -> Optional[WatchTask]:
        with self._lock:
            config = self._cache.get(str(user_id))
            if not config:
                return None

            resolved = resolve_watch_key(config, watch_key)
            if resolved is None:
                return None
            return config.get_task(resolved)

    def add_task(self, user_id: str, watch_key: str, task: WatchTask) -> None:
        with self._lock:
            user_id = str(user_id)
            canonical_key = canonicalize_watch_key(watch_key, task)

            existing = self._cache.get(user_id)
            if existing is not None:
                existing_task = existing.get_task(canonical_key)
                if existing_task is not None and getattr(existing_task, "watch_id", None):
                    task.watch_id = existing_task.watch_id

            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(UPSERT_WATCH_TASK_SQL, task_to_row(user_id, canonical_key, task))

            if user_id not in self._cache:
                self._cache[user_id] = WatchConfig(user_id=user_id)
            self._cache[user_id].add_task(canonical_key, task)
            self._rebuild_source_index()

    def remove_task(self, user_id: str, watch_key: str) -> bool:
        with self._lock:
            user_id = str(user_id)
            config = self._cache.get(user_id)
            if not config:
                return False

            resolved = resolve_watch_key(config, watch_key)
            if resolved is None:
                return False

            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM watch_tasks WHERE user_id = ? AND watch_key = ?",
                    (user_id, resolved),
                )
                deleted = cursor.rowcount > 0

            if deleted:
                config.remove_task(resolved)
                if config.task_count == 0:
                    self._cache.pop(user_id, None)
                self._rebuild_source_index()
            return deleted

    def get_monitored_sources(self) -> Set[str]:
        with self._lock:
            sources = set(self._source_index.keys())
            sources.discard("me")
            return sources

    def get_tasks_for_source(self, source_id: str) -> List[tuple]:
        with self._lock:
            return list(self._source_index.get(str(source_id), []))

    def save_config_dict(self, config_dict: Dict[str, Any]) -> None:
        """Save all watch configurations from raw dict in a single transaction."""
        parsed = parse_config_dict(config_dict)

        with self._lock:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                self._replace_config_rows(cursor, parsed)

            self._cache = parsed
            self._rebuild_source_index()

    @staticmethod
    def _insert_config_rows(cursor: sqlite3.Cursor, user_id: str, config: WatchConfig) -> None:
        rows = task_rows(user_id, config)
        if rows:
            cursor.executemany(INSERT_WATCH_TASK_SQL, rows)

    def _replace_config_rows(self, cursor: sqlite3.Cursor, parsed: Dict[str, WatchConfig]) -> None:
        self._delete_config_rows_not_in(cursor, list(parsed.keys()))
        for user_id, config in parsed.items():
            cursor.execute("DELETE FROM watch_tasks WHERE user_id = ?", (user_id,))
            self._insert_config_rows(cursor, user_id, config)

    @staticmethod
    def _delete_config_rows_not_in(cursor: sqlite3.Cursor, target_users: List[str]) -> None:
        if not target_users:
            cursor.execute("DELETE FROM watch_tasks")
            return
        placeholders = ",".join("?" for _ in target_users)
        cursor.execute(
            f"DELETE FROM watch_tasks WHERE user_id NOT IN ({placeholders})",
            target_users,
        )
