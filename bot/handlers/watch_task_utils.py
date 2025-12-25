"""
Watch task utils - 监控任务工具函数

目标：
- 兼容旧的“按序号(task_id)”回调格式
- 新格式使用 watch_id 作为稳定标识，避免 dict 顺序/DB 无序导致的任务错配
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


def extract_watch_id(watch_data: Any) -> Optional[str]:
    """从 watch_data 中提取 watch_id（若存在）。"""
    if not isinstance(watch_data, dict):
        return None
    value = watch_data.get("watch_id")
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def resolve_watch_entry(
    user_watch_config: Dict[str, Any],
    token: str,
) -> Tuple[Optional[str], Optional[Any], Optional[str]]:
    """根据 token 解析具体 watch 任务。

    Args:
        user_watch_config: 单个用户的 watch 配置字典（key=watch_key, value=watch_data）
        token: 兼容两种格式：
          - 旧格式：1-based 序号（纯数字字符串）
          - 新格式：watch_id（推荐）

    Returns:
        (watch_key, watch_data, watch_id)
    """
    token = (token or "").strip()
    if not token:
        return None, None, None

    # 旧格式：按序号定位（顺序取决于 dict insertion order；新按钮不再依赖此机制）
    if token.isdigit():
        idx = int(token)
        if idx < 1 or idx > len(user_watch_config):
            return None, None, None
        watch_key = list(user_watch_config.keys())[idx - 1]
        watch_data = user_watch_config.get(watch_key)
        return watch_key, watch_data, extract_watch_id(watch_data)

    # 新格式：按 watch_id 定位（稳定）
    for watch_key, watch_data in user_watch_config.items():
        if extract_watch_id(watch_data) == token:
            return watch_key, watch_data, token

    return None, None, None

