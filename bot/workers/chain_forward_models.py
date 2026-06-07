"""Data helpers for chain-forward processing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ChainTaskEntry:
    user_id: str
    watch_key: str
    watch_data: dict


@dataclass(frozen=True)
class ChainProcessContext:
    forwarded_message: Any
    user_id: str
    dest_chat_id: str
    message_text: str
    watch_data: dict
    chain_context: Optional[Dict[str, Any]]


def normalize_chain_task_entry(entry) -> Optional[ChainTaskEntry]:
    if not isinstance(entry, (tuple, list)):
        return None

    parsed_entry = _parse_chain_task_tuple(entry)
    if parsed_entry is None:
        return None

    check_user_id, check_watch_key, check_task = parsed_entry
    check_watch_data = _chain_task_to_dict(check_task)
    if check_watch_data is None:
        return None
    return ChainTaskEntry(str(check_user_id), str(check_watch_key), check_watch_data)


def _parse_chain_task_tuple(entry) -> Optional[tuple[Any, str, Any]]:
    if len(entry) == 3:
        check_user_id, check_watch_key, check_task = entry
        return check_user_id, check_watch_key, check_task
    if len(entry) == 2:
        check_user_id, check_task = entry
        return check_user_id, "", check_task
    return None


def _chain_task_to_dict(task) -> Optional[dict]:
    if hasattr(task, "to_dict"):
        return task.to_dict()
    if isinstance(task, dict):
        return task
    return None
