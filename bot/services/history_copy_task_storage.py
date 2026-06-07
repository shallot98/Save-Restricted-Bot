"""Persistent storage for history-copy keyboard tasks."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from threading import RLock

from src.core.config import settings

from .history_copy_task_models import HistoryCopyTaskConfig


class HistoryCopyTaskStorage:
    """Store history-copy task records in JSON."""

    def __init__(self, config_path: Path | None = None) -> None:
        self._config_path = config_path or settings.paths.config_dir / "history_copy_tasks.json"
        self._lock = RLock()

    def load(self) -> dict[str, dict[str, HistoryCopyTaskConfig]]:
        with self._lock:
            payload = self._load_raw()
            return self._deserialize(payload)

    def save(self, config: dict[str, dict[str, HistoryCopyTaskConfig]]) -> None:
        with self._lock:
            payload = self._serialize(config)
            self._atomic_write(payload)

    def _load_raw(self) -> dict:
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._config_path.exists():
            self._atomic_write({})
            return {}

        with self._config_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}

    def _deserialize(self, payload: dict) -> dict[str, dict[str, HistoryCopyTaskConfig]]:
        result: dict[str, dict[str, HistoryCopyTaskConfig]] = {}
        for user_id, user_tasks in payload.items():
            if not isinstance(user_tasks, dict):
                continue
            parsed_tasks: dict[str, HistoryCopyTaskConfig] = {}
            for task_id, task_data in user_tasks.items():
                if not isinstance(task_data, dict):
                    continue
                try:
                    task = HistoryCopyTaskConfig.from_dict(str(task_id), task_data)
                except Exception:
                    continue
                parsed_tasks[task.task_id] = task
            if parsed_tasks:
                result[str(user_id)] = parsed_tasks
        return result

    @staticmethod
    def _serialize(config: dict[str, dict[str, HistoryCopyTaskConfig]]) -> dict[str, dict[str, dict]]:
        return {
            str(user_id): {task_id: task.to_dict() for task_id, task in tasks.items()}
            for user_id, tasks in config.items()
        }

    def _atomic_write(self, payload: dict) -> None:
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(
            dir=str(self._config_path.parent),
            prefix=f".{self._config_path.name}.",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self._config_path)
        finally:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass
