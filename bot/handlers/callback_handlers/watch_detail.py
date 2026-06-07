"""Watch task detail rendering helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup


@dataclass(frozen=True)
class WatchDetail:
    source_id: str
    dest: str
    whitelist: list[str]
    blacklist: list[str]
    whitelist_regex: list[str]
    blacklist_regex: list[str]
    preserve_source: bool
    forward_mode: str
    extract_patterns: list[str]
    record_mode: bool


def build_watch_detail(watch_key: str, watch_data: Any) -> WatchDetail:
    if isinstance(watch_data, dict):
        detail = _build_dict_detail(watch_key, watch_data)
    else:
        detail = _build_legacy_detail(watch_key, watch_data)
    return _normalize_detail(detail)


def _build_dict_detail(watch_key: str, watch_data: dict[str, Any]) -> WatchDetail:
    source, dest = _fallback_source_dest(watch_key)
    return WatchDetail(
        source_id=watch_data.get("source", source),
        dest=watch_data.get("dest", dest),
        whitelist=watch_data.get("whitelist", []),
        blacklist=watch_data.get("blacklist", []),
        whitelist_regex=watch_data.get("whitelist_regex", []),
        blacklist_regex=watch_data.get("blacklist_regex", []),
        preserve_source=watch_data.get("preserve_forward_source", False),
        forward_mode=watch_data.get("forward_mode", "full"),
        extract_patterns=watch_data.get("extract_patterns", []),
        record_mode=watch_data.get("record_mode", False),
    )


def _fallback_source_dest(watch_key: str) -> tuple[str, str]:
    if "|" not in watch_key:
        return watch_key, "unknown"
    source, dest = watch_key.split("|", 1)
    return source, dest


def _build_legacy_detail(watch_key: str, watch_data: Any) -> WatchDetail:
    return WatchDetail(
        source_id=watch_key,
        dest=watch_data,
        whitelist=[],
        blacklist=[],
        whitelist_regex=[],
        blacklist_regex=[],
        preserve_source=False,
        forward_mode="full",
        extract_patterns=[],
        record_mode=False,
    )


def _normalize_detail(detail: WatchDetail) -> WatchDetail:
    source_id = detail.source_id if detail.source_id is not None else "未知来源"
    dest = detail.dest if detail.dest is not None else "未知目标"
    return WatchDetail(
        source_id=source_id,
        dest=dest,
        whitelist=detail.whitelist,
        blacklist=detail.blacklist,
        whitelist_regex=detail.whitelist_regex,
        blacklist_regex=detail.blacklist_regex,
        preserve_source=detail.preserve_source,
        forward_mode=detail.forward_mode,
        extract_patterns=detail.extract_patterns,
        record_mode=detail.record_mode,
    )


def render_watch_detail_text(detail: WatchDetail) -> str:
    lines = ["**📋 监控任务详情**", "", f"**来源：** `{detail.source_id}`"]
    lines.extend(_mode_lines(detail))
    lines.extend(_filter_lines(detail))
    lines.extend(_extract_lines(detail))
    return "\n".join(lines)


def _mode_lines(detail: WatchDetail) -> list[str]:
    if detail.record_mode:
        return ["**模式：** 📝 记录模式（保存到网页）", ""]
    forward_mode = "🎯 提取模式" if detail.forward_mode == "extract" else "📦 完整转发"
    preserve_source = "✅ 是" if detail.preserve_source else "❌ 否"
    return [
        f"**目标：** `{detail.dest}`",
        "",
        f"**转发模式：** {forward_mode}",
        f"**保留来源：** {preserve_source}",
    ]


def _filter_lines(detail: WatchDetail) -> list[str]:
    lines = ["", "**过滤规则：**"]
    lines.extend(_named_rule_lines("🟢 关键词白名单", detail.whitelist))
    lines.extend(_named_rule_lines("🔴 关键词黑名单", detail.blacklist))
    lines.extend(_named_rule_lines("🟢 正则白名单", detail.whitelist_regex))
    lines.extend(_named_rule_lines("🔴 正则黑名单", detail.blacklist_regex))
    if not _has_filter_rules(detail):
        lines.append("⏭ 无过滤（转发所有消息）")
    return lines


def _named_rule_lines(label: str, values: list[str]) -> list[str]:
    return [f"{label}: `{', '.join(values)}`"] if values else []


def _has_filter_rules(detail: WatchDetail) -> bool:
    return bool(
        detail.whitelist
        or detail.blacklist
        or detail.whitelist_regex
        or detail.blacklist_regex
    )


def _extract_lines(detail: WatchDetail) -> list[str]:
    if detail.forward_mode != "extract" or not detail.extract_patterns:
        return []
    return ["", "**提取规则：**", *[f"• `{pattern}`" for pattern in detail.extract_patterns]]


def build_watch_detail_keyboard(task_ref: str, record_mode: bool) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton("✏️ 编辑过滤规则", callback_data=f"edit_filter_{task_ref}")]]
    if not record_mode:
        buttons.append([InlineKeyboardButton("📤 切换保留来源", callback_data=f"edit_preserve_{task_ref}")])
    buttons.append([InlineKeyboardButton("🗑 删除此监控", callback_data=f"watch_remove_{task_ref}")])
    buttons.append([InlineKeyboardButton("🔙 返回列表", callback_data="watch_list")])
    return InlineKeyboardMarkup(buttons)
