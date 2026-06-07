"""
JSON Watch Repository
=====================

JSON file-based implementation of WatchRepository interface.
"""

import json
import threading
import logging
from pathlib import Path
from typing import Optional, List, Set, Dict, Any, Tuple

from src.domain.entities.watch import WatchTask, WatchConfig
from src.domain.repositories.watch_repository import WatchRepository
from src.core.config import settings
from src.infrastructure.persistence.repositories.json_watch_repository_helpers import (
    atomic_write_json,
    build_source_index,
    canonicalize_watch_key,
    parse_user_config,
    resolve_watch_key,
)

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

        self._cache = self._parse_config_data(data)
        self._rebuild_source_index()

    def _sync_from_settings(self, force: bool = False) -> None:
        """Sync cache from Settings (single source of truth)."""
        if not self._use_settings_backend:
            return

        current_revision = settings.watch_config_revision
        if not force and current_revision == self._settings_revision:
            return

        self._cache = self._parse_config_data(settings.watch_config)
        self._settings_revision = current_revision
        self._rebuild_source_index()

    @staticmethod
    def _parse_config_data(data: Dict[str, Any]) -> Dict[str, WatchConfig]:
        cache: Dict[str, WatchConfig] = {}
        for user_id, user_data in (data or {}).items():
            if not isinstance(user_data, dict):
                logger.warning(f"Invalid watch config entry: user={user_id}")
                continue
            config = parse_user_config(str(user_id), user_data)
            if config is None:
                logger.warning(f"Failed to parse watch config: user={user_id}")
                continue
            cache[str(user_id)] = config
        return cache

    def _ensure_fresh(self) -> None:
        """Ensure cache is in sync with Settings."""
        self._sync_from_settings(force=False)

    def _rebuild_source_index(self) -> None:
        """Rebuild source -> tasks index for fast lookups."""
        self._source_index = build_source_index(self._cache)

    def _save_cache(self) -> None:
        """Persist cache and rebuild derived indices."""
        data = {user_id: config.to_dict() for user_id, config in self._cache.items()}

        if self._use_settings_backend:
            settings.save_watch_config(data, auto_reload=True)
            self._settings_revision = settings.watch_config_revision
        else:
            atomic_write_json(self._config_path, data)

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
            self._cache = self._parse_config_data(config_dict)
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

            resolved_key = resolve_watch_key(config, watch_key)
            if resolved_key is None:
                return None

            return config.get_task(resolved_key)

    def add_task(self, user_id: str, watch_key: str, task: WatchTask) -> None:
        """Add or update a watch task"""
        with self._lock:
            self._ensure_fresh()
            if user_id not in self._cache:
                self._cache[user_id] = WatchConfig(user_id=user_id)

            canonical_key = canonicalize_watch_key(watch_key, task)
            self._cache[user_id].add_task(canonical_key, task)
            self._save_cache()

    def remove_task(self, user_id: str, watch_key: str) -> bool:
        """Remove a watch task"""
        with self._lock:
            self._ensure_fresh()
            config = self._cache.get(user_id)
            if not config:
                return False

            resolved_key = resolve_watch_key(config, watch_key)
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
            return {
                str(task.source)
                for config in self._cache.values()
                for task in config.tasks.values()
                if task.source and task.source != "me"
            }

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
