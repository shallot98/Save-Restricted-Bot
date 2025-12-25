"""
JSON Watch Repository
=====================

JSON file-based implementation of WatchRepository interface.
"""

import json
import os
import shutil
import tempfile
import threading
import logging
from pathlib import Path
from typing import Optional, List, Set, Dict, Any, Tuple

from src.domain.entities.watch import WatchTask, WatchConfig
from src.domain.repositories.watch_repository import WatchRepository
from src.core.config import settings

logger = logging.getLogger(__name__)


class JSONWatchRepository(WatchRepository):
    """
    JSON file-based implementation of WatchRepository

    Stores watch configurations in a JSON file.
    """

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self._lock = threading.RLock()
        self._config_path = config_path or settings.paths.watch_file
        self._use_settings_backend = (
            self._config_path.resolve() == settings.paths.watch_file.resolve()
        )
        self._settings_revision: int = -1
        self._cache: Dict[str, WatchConfig] = {}
        self._source_index: Dict[str, List[Tuple[str, str, WatchTask]]] = {}
        with self._lock:
            self._load_cache()

    def _load_cache(self) -> None:
        """Load configurations into in-memory cache."""
        if self._use_settings_backend:
            self._sync_from_settings(force=True)
            return

        if not self._config_path.exists():
            self._cache = {}
            self._rebuild_source_index()
            return

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load watch config: {e}")
            self._cache = {}
            self._rebuild_source_index()
            return

        cache: Dict[str, WatchConfig] = {}
        for user_id, user_data in (data or {}).items():
            if not isinstance(user_data, dict):
                logger.warning(f"Invalid watch config entry: user={user_id}")
                continue
            try:
                cache[user_id] = WatchConfig.from_dict(user_id, user_data)
            except Exception as e:
                logger.warning(f"Failed to parse watch config: user={user_id}, err={e}")
                continue

        self._cache = cache
        self._rebuild_source_index()

    def _sync_from_settings(self, force: bool = False) -> None:
        """Sync cache from Settings (single source of truth)."""
        if not self._use_settings_backend:
            return

        current_revision = settings.watch_config_revision
        if not force and current_revision == self._settings_revision:
            return

        data = settings.watch_config
        cache: Dict[str, WatchConfig] = {}
        for user_id, user_data in (data or {}).items():
            if not isinstance(user_data, dict):
                logger.warning(f"Invalid watch config entry: user={user_id}")
                continue
            try:
                cache[user_id] = WatchConfig.from_dict(str(user_id), user_data)
            except Exception as e:
                logger.warning(f"Failed to parse watch config: user={user_id}, err={e}")
                continue

        self._cache = cache
        self._settings_revision = current_revision
        self._rebuild_source_index()

    def _ensure_fresh(self) -> None:
        """Ensure cache is in sync with Settings."""
        self._sync_from_settings(force=False)

    def _rebuild_source_index(self) -> None:
        """Rebuild source -> tasks index for fast lookups."""
        index: Dict[str, List[Tuple[str, str, WatchTask]]] = {}
        for user_id, config in self._cache.items():
            for watch_key, task in config.tasks.items():
                source_id = str(task.source) if task.source is not None else ""
                if not source_id:
                    continue
                index.setdefault(source_id, []).append((user_id, watch_key, task))
        self._source_index = index

    @staticmethod
    def _resolve_watch_key(config: WatchConfig, watch_key: str) -> Optional[str]:
        """Resolve a watch_key, allowing backward compatible lookups by source_id.

        If `watch_key` exists in the config, returns it directly.
        Otherwise, if `watch_key` looks like a plain source_id (no '|') and there is
        exactly one task whose `task.source` matches it, returns that task's key.
        """
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
        """Canonicalize watch keys to avoid ambiguous "key=source" semantics."""
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

    def _atomic_write_json(self, path: Path, data: Dict[str, Any]) -> None:
        """Atomically write JSON to disk to avoid config corruption."""
        path.parent.mkdir(parents=True, exist_ok=True)

        temp_fd, temp_path = tempfile.mkstemp(
            dir=str(path.parent),
            prefix=f".{path.name}.",
            suffix=".tmp",
        )

        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())

            if path.exists():
                backup_path = path.with_suffix(path.suffix + ".bak")
                try:
                    shutil.copy2(path, backup_path)
                except OSError:
                    pass

            os.replace(temp_path, path)
        finally:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass

    def _save_cache(self) -> None:
        """Persist cache and rebuild derived indices."""
        data = {user_id: config.to_dict() for user_id, config in self._cache.items()}

        if self._use_settings_backend:
            settings.save_watch_config(data, auto_reload=True)
            self._settings_revision = settings.watch_config_revision
        else:
            self._atomic_write_json(self._config_path, data)

        self._rebuild_source_index()
        logger.debug(f"Watch config saved: {len(self._cache)} users")

    def get_user_config(self, user_id: str) -> Optional[WatchConfig]:
        """Get watch configuration for a user"""
        with self._lock:
            self._ensure_fresh()
            return self._cache.get(user_id)

    def get_all_configs(self) -> List[WatchConfig]:
        """Get all watch configurations"""
        with self._lock:
            self._ensure_fresh()
            return list(self._cache.values())

    def save_user_config(self, config: WatchConfig) -> None:
        """Save user's watch configuration"""
        with self._lock:
            self._ensure_fresh()
            self._cache[config.user_id] = config
            self._save_cache()

    def save_config_dict(self, config_dict: Dict[str, Any]) -> None:
        """Save all watch configurations from raw dict in a single write."""
        with self._lock:
            cache: Dict[str, WatchConfig] = {}
            for user_id, user_data in (config_dict or {}).items():
                if not isinstance(user_data, dict):
                    logger.warning(f"Invalid watch config entry: user={user_id}")
                    continue
                try:
                    cache[str(user_id)] = WatchConfig.from_dict(str(user_id), user_data)
                except Exception as e:
                    logger.warning(f"Failed to parse watch config: user={user_id}, err={e}")
                    continue

            self._cache = cache
            self._save_cache()

    def delete_user_config(self, user_id: str) -> bool:
        """Delete user's watch configuration"""
        with self._lock:
            self._ensure_fresh()
            if user_id in self._cache:
                del self._cache[user_id]
                self._save_cache()
                return True
            return False

    def get_task(self, user_id: str, watch_key: str) -> Optional[WatchTask]:
        """Get specific watch task"""
        with self._lock:
            self._ensure_fresh()
            config = self._cache.get(user_id)
            if not config:
                return None

            resolved_key = self._resolve_watch_key(config, watch_key)
            if resolved_key is None:
                return None

            return config.get_task(resolved_key)

    def add_task(self, user_id: str, watch_key: str, task: WatchTask) -> None:
        """Add or update a watch task"""
        with self._lock:
            self._ensure_fresh()
            if user_id not in self._cache:
                self._cache[user_id] = WatchConfig(user_id=user_id)

            canonical_key = self._canonicalize_watch_key(watch_key, task)
            self._cache[user_id].add_task(canonical_key, task)
            self._save_cache()

    def remove_task(self, user_id: str, watch_key: str) -> bool:
        """Remove a watch task"""
        with self._lock:
            self._ensure_fresh()
            config = self._cache.get(user_id)
            if not config:
                return False

            resolved_key = self._resolve_watch_key(config, watch_key)
            if resolved_key is None:
                return False

            if config.remove_task(resolved_key):
                # Remove user config if no tasks left
                if config.task_count == 0:
                    del self._cache[user_id]
                self._save_cache()
                return True
            return False

    def get_monitored_sources(self) -> Set[str]:
        """Get all monitored source chat IDs"""
        with self._lock:
            self._ensure_fresh()
            sources = set()
            for config in self._cache.values():
                for task in config.tasks.values():
                    # Extract source from task, not from key
                    if task.source and task.source != "me":
                        sources.add(str(task.source))
            return sources

    def get_tasks_for_source(self, source_id: str) -> List[tuple]:
        """Get all tasks monitoring a specific source.

        Returns tuples of (user_id, watch_key, task).
        """
        with self._lock:
            self._ensure_fresh()
            return list(self._source_index.get(str(source_id), []))

    def reload(self) -> None:
        """Reload configurations from file"""
        with self._lock:
            if self._use_settings_backend:
                settings.reload_watch_config()
                self._sync_from_settings(force=True)
            else:
                self._load_cache()
