"""Helpers for SQLiteWatchRepository row conversion and config parsing."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

from src.domain.entities.watch import WatchConfig, WatchTask

logger = logging.getLogger(__name__)

_FILTER_LIST_COLUMNS = (
    ("whitelist", "whitelist_json"),
    ("blacklist", "blacklist_json"),
    ("whitelist_regex", "whitelist_regex_json"),
    ("blacklist_regex", "blacklist_regex_json"),
    ("extract_patterns", "extract_patterns_json"),
)


class CorruptFilterDataError(ValueError):
    """过滤器列表字段无法解析（JSON 损坏或类型不符）。"""

SELECT_WATCH_TASKS_SQL = """
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

INSERT_WATCH_TASK_SQL = """
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
"""

UPSERT_WATCH_TASK_SQL = INSERT_WATCH_TASK_SQL + """
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
"""


def row_to_task(row: Dict[str, Any]) -> WatchTask:
    """把一行 watch_tasks 记录转成 WatchTask。

    失败方向：任一过滤器列（黑/白名单等）JSON 损坏时，记录 error 并把该任务标记
    为 filters_corrupt=True —— FilterService 会据此拦截该源的全部消息。绝不能像
    以前那样静默降级成空列表（那等于把过滤器无声关掉，方向是「放行」）。
    """
    filter_lists, corrupt_columns = _load_filter_lists(row)
    if corrupt_columns:
        logger.error(
            "监控任务过滤器数据损坏，该任务将拦截全部消息: user=%s watch_key=%s columns=%s",
            row.get("user_id"),
            row.get("watch_key"),
            ",".join(corrupt_columns),
        )

    return WatchTask(
        source=str(row.get("source_id") or "").strip(),
        dest=str(row["dest_id"]) if row.get("dest_id") is not None else None,
        preserve_forward_source=bool(row.get("preserve_forward_source", 0)),
        forward_mode=str(row.get("forward_mode") or "full"),
        record_mode=bool(row.get("record_mode", 0)),
        watch_id=str(row.get("watch_id") or "").strip() or None,
        filters_corrupt=bool(corrupt_columns),
        **filter_lists,
    )


def _load_filter_lists(row: Dict[str, Any]) -> Tuple[Dict[str, List[str]], List[str]]:
    """加载全部过滤器列表列，返回 (字段值, 损坏的列名列表)。"""
    values: Dict[str, List[str]] = {}
    corrupt_columns: List[str] = []
    for field_name, column in _FILTER_LIST_COLUMNS:
        try:
            values[field_name] = safe_load_list(row.get(column))
        except CorruptFilterDataError as exc:
            logger.error("过滤器列解析失败: column=%s error=%s", column, exc)
            values[field_name] = []
            corrupt_columns.append(column)
    return values, corrupt_columns


def safe_load_list(value: Any) -> List[str]:
    """解析存储为 JSON 的字符串列表。

    Raises:
        CorruptFilterDataError: 值无法解析成列表。调用方必须显式处理，
            不允许静默返回空列表。
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    if not isinstance(value, str):
        raise CorruptFilterDataError(f"unexpected value type: {type(value).__name__}")
    value = value.strip()
    if not value:
        return []
    return _json_list_to_strings(value)


def _json_list_to_strings(value: str) -> List[str]:
    try:
        parsed = json.loads(value)
    except ValueError as exc:
        raise CorruptFilterDataError(f"invalid JSON: {exc}") from exc
    if not isinstance(parsed, list):
        raise CorruptFilterDataError(f"expected JSON list, got {type(parsed).__name__}")
    return [str(item) for item in parsed if item is not None]


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


def canonical_config_for_user(user_id: str, config: WatchConfig) -> WatchConfig:
    canonical_config = WatchConfig(user_id=user_id)
    for watch_key, task in config.tasks.items():
        canonical_config.add_task(canonicalize_watch_key(watch_key, task), task)
    return canonical_config


def task_to_row(user_id: str, watch_key: str, task: WatchTask) -> Tuple[Any, ...]:
    if getattr(task, "filters_corrupt", False):
        # 该任务的过滤器数据读取时已损坏，此处回写会用空列表覆盖原始损坏值。
        logger.error(
            "回写过滤器数据已损坏的监控任务，原过滤器内容将被清空: user=%s watch_key=%s",
            user_id,
            watch_key,
        )
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
        ensure_watch_id(task),
    )


def task_rows(user_id: str, config: WatchConfig) -> List[Tuple[Any, ...]]:
    return [task_to_row(user_id, watch_key, task) for watch_key, task in config.tasks.items()]


def ensure_watch_id(task: WatchTask) -> str:
    watch_id = getattr(task, "watch_id", None)
    if isinstance(watch_id, str) and watch_id.strip():
        task.watch_id = watch_id.strip()
        return task.watch_id
    task.watch_id = uuid.uuid4().hex
    return task.watch_id


def parse_config_dict(config_dict: Dict[str, Any]) -> Dict[str, WatchConfig]:
    parsed: Dict[str, WatchConfig] = {}
    for user_id, user_data in (config_dict or {}).items():
        if not isinstance(user_data, dict):
            continue
        parsed[str(user_id)] = _parse_user_config(str(user_id), user_data)
    return parsed


def _parse_user_config(user_id: str, user_data: dict) -> WatchConfig:
    config = WatchConfig(user_id=user_id)
    for watch_key, watch_data in user_data.items():
        task = _parse_watch_task(str(watch_key), watch_data)
        if task is None:
            continue
        config.add_task(canonicalize_watch_key(str(watch_key), task), task)
    return config


def _parse_watch_task(watch_key: str, watch_data: Any) -> Optional[WatchTask]:
    if isinstance(watch_data, dict):
        return _parse_dict_watch_task(watch_key, watch_data)
    return WatchTask(source=watch_key, dest=str(watch_data) if watch_data is not None else None)


def _parse_dict_watch_task(watch_key: str, watch_data: dict) -> Optional[WatchTask]:
    """解析单条任务字典。

    失败方向：字段不兼容时跳过该条并记录 error（此前是静默消失、零日志）。
    """
    payload = dict(watch_data)
    if "source" not in payload or not payload.get("source"):
        payload["source"] = watch_key.split("|")[0] if "|" in watch_key else watch_key
    try:
        return WatchTask.from_dict(payload)
    except Exception as exc:
        logger.error(
            "跳过无法解析的监控任务: watch_key=%s error=%s keys=%s",
            watch_key,
            exc,
            sorted(payload.keys()),
        )
        return None
