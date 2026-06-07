"""Helpers for JSONWatchRepository parsing, indexing, and persistence."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.domain.entities.watch import WatchConfig, WatchTask


def build_source_index(
    cache: Dict[str, WatchConfig],
) -> Dict[str, List[Tuple[str, str, WatchTask]]]:
    index: Dict[str, List[Tuple[str, str, WatchTask]]] = {}
    for user_id, config in cache.items():
        for watch_key, task in config.tasks.items():
            source_id = str(task.source) if task.source is not None else ""
            if source_id:
                index.setdefault(source_id, []).append((user_id, watch_key, task))
    return index


def parse_watch_config_dict(config_dict: Dict[str, Any]) -> Dict[str, WatchConfig]:
    cache: Dict[str, WatchConfig] = {}
    for user_id, user_data in (config_dict or {}).items():
        if not isinstance(user_data, dict):
            continue
        config = parse_user_config(str(user_id), user_data)
        if config is not None:
            cache[str(user_id)] = config
    return cache


def parse_user_config(user_id: str, user_data: dict) -> Optional[WatchConfig]:
    try:
        return WatchConfig.from_dict(user_id, user_data)
    except Exception:
        return None


def resolve_watch_key(config: WatchConfig, watch_key: str) -> Optional[str]:
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
    return matches[0] if len(matches) == 1 else None


def canonicalize_watch_key(watch_key: str, task: WatchTask) -> str:
    if watch_key and "|" in watch_key:
        return watch_key

    source_id = str(getattr(task, "source", "") or watch_key or "").strip()
    dest_id = getattr(task, "dest", None)
    if bool(getattr(task, "record_mode", False)):
        return f"{source_id}|record"
    if dest_id is not None:
        return f"{source_id}|{dest_id}"
    return source_id or watch_key


def atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
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
            _copy_backup(path)
        os.replace(temp_path, path)
    finally:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass


def _copy_backup(path: Path) -> None:
    backup_path = path.with_suffix(path.suffix + ".bak")
    try:
        shutil.copy2(path, backup_path)
    except OSError:
        pass
