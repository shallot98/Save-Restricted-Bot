"""
SQLite Watch Repository
======================

SQLite-backed persistence for watch configuration.

Notes:
- Keeps an in-memory cache + source index for fast hot-path lookups.
- SQLite is the source of truth; cache is refreshed on writes or explicit reload().
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from typing import Optional, List, Set, Dict, Any, Tuple

from src.domain.entities.watch import WatchTask, WatchConfig
from src.domain.repositories.watch_repository import WatchRepository
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
                cursor.execute(
                    """
                    SELECT
                        user_id,
                        watch_key,
                        watch_id,
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
                    FROM watch_tasks
                    """
                )
                rows = cursor.fetchall()
            except sqlite3.Error as e:
                logger.warning(f"Failed to load watch_tasks (treat as empty): {e}")
                rows = []

        for row in rows:
            user_id = str(row["user_id"])
            watch_key = str(row["watch_key"])
            task = self._row_to_task(dict(row))
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

    @staticmethod
    def _safe_load_list(value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if item is not None]
        if not isinstance(value, str):
            return []
        value = value.strip()
        if not value:
            return []
        try:
            parsed = json.loads(value)
        except Exception:
            return []
        if not isinstance(parsed, list):
            return []
        return [str(item) for item in parsed if item is not None]

    @staticmethod
    def _row_to_task(row: Dict[str, Any]) -> WatchTask:
        return WatchTask(
            source=str(row.get("source_id") or "").strip(),
            dest=str(row["dest_id"]) if row.get("dest_id") is not None else None,
            whitelist=SQLiteWatchRepository._safe_load_list(row.get("whitelist_json")),
            blacklist=SQLiteWatchRepository._safe_load_list(row.get("blacklist_json")),
            whitelist_regex=SQLiteWatchRepository._safe_load_list(row.get("whitelist_regex_json")),
            blacklist_regex=SQLiteWatchRepository._safe_load_list(row.get("blacklist_regex_json")),
            preserve_forward_source=bool(row.get("preserve_forward_source", 0)),
            forward_mode=str(row.get("forward_mode") or "full"),
            extract_patterns=SQLiteWatchRepository._safe_load_list(row.get("extract_patterns_json")),
            record_mode=bool(row.get("record_mode", 0)),
            watch_id=str(row.get("watch_id") or "").strip() or None,
        )

    @staticmethod
    def _resolve_watch_key(config: WatchConfig, watch_key: str) -> Optional[str]:
        """Resolve a watch_key, allowing backward compatible lookups by source_id."""
        if not watch_key:
            return None

        if watch_key in config.tasks:
            return watch_key

        if "|" in watch_key:
            return None

        matches = [
            key
            for key, task in config.tasks.items()
            if str(getattr(task, "source", "") or "") == str(watch_key)
        ]
        if len(matches) == 1:
            return matches[0]
        return None

    @staticmethod
    def _canonicalize_watch_key(watch_key: str, task: WatchTask) -> str:
        if watch_key and "|" in watch_key:
            return watch_key

        source_id = str(getattr(task, "source", "") or watch_key or "").strip()
        dest_id = getattr(task, "dest", None)
        record_mode = bool(getattr(task, "record_mode", False))

        if record_mode:
            return f"{source_id}|record"
        if dest_id is not None:
            return f"{source_id}|{dest_id}"
        return source_id or watch_key

    @staticmethod
    def _ensure_watch_id(task: WatchTask) -> str:
        watch_id = getattr(task, "watch_id", None)
        if isinstance(watch_id, str) and watch_id.strip():
            task.watch_id = watch_id.strip()
            return task.watch_id
        task.watch_id = uuid.uuid4().hex
        return task.watch_id

    @staticmethod
    def _task_to_row(user_id: str, watch_key: str, task: WatchTask) -> Tuple[Any, ...]:
        return (
            str(user_id),
            str(watch_key),
            str(task.source),
            None if task.dest is None else str(task.dest),
            1 if task.record_mode else 0,
            json.dumps(list(task.whitelist), ensure_ascii=False),
            json.dumps(list(task.blacklist), ensure_ascii=False),
            json.dumps(list(task.whitelist_regex), ensure_ascii=False),
            json.dumps(list(task.blacklist_regex), ensure_ascii=False),
            1 if task.preserve_forward_source else 0,
            str(task.forward_mode or "full"),
            json.dumps(list(task.extract_patterns), ensure_ascii=False),
            SQLiteWatchRepository._ensure_watch_id(task),
        )

    def get_user_config(self, user_id: str) -> Optional[WatchConfig]:
        with self._lock:
            return self._cache.get(user_id)

    def get_all_configs(self) -> List[WatchConfig]:
        with self._lock:
            return list(self._cache.values())

    def save_user_config(self, config: WatchConfig) -> None:
        with self._lock:
            user_id = str(config.user_id)
            canonical_config = WatchConfig(user_id=user_id)
            for watch_key, task in config.tasks.items():
                canonical_key = self._canonicalize_watch_key(watch_key, task)
                canonical_config.add_task(canonical_key, task)

            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM watch_tasks WHERE user_id = ?", (user_id,))
                rows = [
                    self._task_to_row(user_id, watch_key, task)
                    for watch_key, task in canonical_config.tasks.items()
                ]
                if rows:
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
                            extract_patterns_json,
                            watch_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        rows,
                    )

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

            resolved = self._resolve_watch_key(config, watch_key)
            if resolved is None:
                return None
            return config.get_task(resolved)

    def add_task(self, user_id: str, watch_key: str, task: WatchTask) -> None:
        with self._lock:
            user_id = str(user_id)
            canonical_key = self._canonicalize_watch_key(watch_key, task)

            existing = self._cache.get(user_id)
            if existing is not None:
                existing_task = existing.get_task(canonical_key)
                if existing_task is not None and getattr(existing_task, "watch_id", None):
                    task.watch_id = existing_task.watch_id

            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
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
                        extract_patterns_json,
                        watch_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, watch_key) DO UPDATE SET
                        source_id=excluded.source_id,
                        dest_id=excluded.dest_id,
                        record_mode=excluded.record_mode,
                        whitelist_json=excluded.whitelist_json,
                        blacklist_json=excluded.blacklist_json,
                        whitelist_regex_json=excluded.whitelist_regex_json,
                        blacklist_regex_json=excluded.blacklist_regex_json,
                        preserve_forward_source=excluded.preserve_forward_source,
                        forward_mode=excluded.forward_mode,
                        extract_patterns_json=excluded.extract_patterns_json,
                        watch_id=COALESCE(watch_tasks.watch_id, excluded.watch_id)
                    """,
                    self._task_to_row(user_id, canonical_key, task),
                )

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

            resolved = self._resolve_watch_key(config, watch_key)
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
        parsed: Dict[str, WatchConfig] = {}
        for user_id, user_data in (config_dict or {}).items():
            if not isinstance(user_data, dict):
                continue

            config = WatchConfig(user_id=str(user_id))
            for watch_key, watch_data in user_data.items():
                task: Optional[WatchTask] = None
                if isinstance(watch_data, dict):
                    payload = dict(watch_data)
                    if "source" not in payload or not payload.get("source"):
                        payload["source"] = str(watch_key).split("|")[0] if "|" in str(watch_key) else str(watch_key)
                    try:
                        task = WatchTask.from_dict(payload)
                    except Exception:
                        task = None
                else:
                    task = WatchTask(source=str(watch_key), dest=str(watch_data) if watch_data is not None else None)

                if task is None:
                    continue

                canonical_key = self._canonicalize_watch_key(str(watch_key), task)
                config.add_task(canonical_key, task)

            parsed[str(user_id)] = config

        with self._lock:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                target_users = list(parsed.keys())

                if not target_users:
                    cursor.execute("DELETE FROM watch_tasks")
                else:
                    placeholders = ",".join("?" for _ in target_users)
                    cursor.execute(
                        f"DELETE FROM watch_tasks WHERE user_id NOT IN ({placeholders})",
                        target_users,
                    )

                for user_id, config in parsed.items():
                    cursor.execute("DELETE FROM watch_tasks WHERE user_id = ?", (user_id,))
                    rows = [
                        self._task_to_row(user_id, watch_key, task)
                        for watch_key, task in config.tasks.items()
                    ]
                    if rows:
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
                                extract_patterns_json,
                                watch_id
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            rows,
                        )

            self._cache = parsed
            self._rebuild_source_index()
