"""
Watch Setup Service
===================

Application service for creating watch tasks while keeping bot callbacks stable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from src.application.services.watch_service import WatchService


@dataclass(frozen=True)
class WatchSetupResult:
    """Result of creating or detecting a watch task."""

    duplicate: bool
    message_text: str
    watch_key: str


@dataclass(frozen=True)
class WatchFilterSet:
    whitelist: List[str]
    blacklist: List[str]
    whitelist_regex: List[str]
    blacklist_regex: List[str]


@dataclass(frozen=True)
class ForwardWatchCreateRequest:
    user_id: str
    source_id: str
    source_name: str
    dest_id: str
    dest_name: str
    filters: WatchFilterSet
    preserve_source: bool
    forward_mode: str
    extract_patterns: List[str]


@dataclass(frozen=True)
class RecordWatchCreateRequest:
    user_id: str
    source_id: str
    source_name: str
    filters: WatchFilterSet


class WatchSetupService:
    """Create watch tasks without leaking persistence details into handlers."""

    def __init__(self, watch_service: WatchService) -> None:
        self._watch_service = watch_service

    def create_forward_watch(
        self,
        request: ForwardWatchCreateRequest | None = None,
        **legacy_fields,
    ) -> WatchSetupResult:
        request = _forward_watch_create_request(request, legacy_fields)
        watch_key = self._make_watch_key(request.source_id, request.dest_id, record_mode=False)
        config = self._ensure_user_config(request.user_id)
        if watch_key in config:
            return self._build_forward_duplicate_result(request.source_name, request.dest_name, watch_key)

        config[watch_key] = self._build_forward_task_config(request)
        self._persist_user_config(request.user_id, config)
        return WatchSetupResult(
            duplicate=False,
            message_text=self._build_forward_success_message(request),
            watch_key=watch_key,
        )

    @staticmethod
    def _build_forward_duplicate_result(source_name: str, dest_name: str, watch_key: str) -> WatchSetupResult:
        return WatchSetupResult(
            duplicate=True,
            message_text=(
                f"**⚠️ 该监控任务已存在**\n\n"
                f"来源：`{source_name}`\n"
                f"目标：`{dest_name}`"
            ),
            watch_key=watch_key,
        )

    @staticmethod
    def _build_forward_task_config(request: ForwardWatchCreateRequest) -> dict:
        return {
            "source": request.source_id,
            "dest": request.dest_id,
            "whitelist": request.filters.whitelist,
            "blacklist": request.filters.blacklist,
            "whitelist_regex": request.filters.whitelist_regex,
            "blacklist_regex": request.filters.blacklist_regex,
            "preserve_forward_source": request.preserve_source,
            "forward_mode": request.forward_mode,
            "extract_patterns": request.extract_patterns,
            "record_mode": False,
        }

    def create_record_watch(
        self,
        request: RecordWatchCreateRequest | None = None,
        **legacy_fields,
    ) -> WatchSetupResult:
        request = _record_watch_create_request(request, legacy_fields)
        watch_key = self._make_watch_key(request.source_id, None, record_mode=True)
        config = self._ensure_user_config(request.user_id)
        if watch_key in config:
            return WatchSetupResult(
                duplicate=True,
                message_text=(
                    f"**⚠️ 该监控任务已存在**\n\n"
                    f"来源：`{request.source_name}`\n"
                    f"模式：记录模式"
                ),
                watch_key=watch_key,
            )

        config[watch_key] = {
            "source": request.source_id,
            "dest": None,
            "whitelist": request.filters.whitelist,
            "blacklist": request.filters.blacklist,
            "whitelist_regex": request.filters.whitelist_regex,
            "blacklist_regex": request.filters.blacklist_regex,
            "preserve_forward_source": False,
            "forward_mode": "full",
            "extract_patterns": [],
            "record_mode": True,
        }
        self._persist_user_config(request.user_id, config)
        return WatchSetupResult(
            duplicate=False,
            message_text=self._build_record_success_message(
                source_name=request.source_name,
                filters=request.filters,
            ),
            watch_key=watch_key,
        )

    def _ensure_user_config(self, user_id: str) -> dict:
        all_configs = self._watch_service.get_all_configs_dict()
        user_config = all_configs.setdefault(user_id, {})
        self._current_all_configs = all_configs
        return user_config

    def _persist_user_config(self, user_id: str, user_config: dict) -> None:
        self._current_all_configs[user_id] = user_config
        self._watch_service.save_config_dict(self._current_all_configs)

    @staticmethod
    def _make_watch_key(source_id: str, dest_id: Optional[str], record_mode: bool) -> str:
        if record_mode:
            return f"{source_id}|record"
        return f"{source_id}|{dest_id}"

    @staticmethod
    def _build_forward_success_message(request: ForwardWatchCreateRequest) -> str:
        lines = [
            "**✅ 监控任务添加成功！**",
            "",
            f"来源：`{request.source_name}`",
            f"目标：`{request.dest_name}`",
            f"转发模式：{'🎯 提取模式' if request.forward_mode == 'extract' else '📦 完整转发'}",
        ]
        lines.extend(WatchSetupService._build_filter_lines(request.filters))
        if request.extract_patterns:
            lines.append(f"提取规则：`{', '.join(request.extract_patterns)}`")
        if request.preserve_source:
            lines.append("保留来源：`是`")
        lines.extend(["", "从现在开始，新消息将自动转发 🎉"])
        return "\n".join(lines)

    @staticmethod
    def _build_record_success_message(
        *,
        source_name: str,
        filters: WatchFilterSet,
    ) -> str:
        lines = [
            "**✅ 监控任务添加成功！**",
            "",
            f"来源：`{source_name}`",
            "模式：📝 **记录模式**",
        ]
        lines.extend(WatchSetupService._build_filter_lines(filters))
        lines.extend(["", "从现在开始，新消息将自动记录到网页笔记 📝"])
        return "\n".join(lines)

    @staticmethod
    def _build_filter_lines(filters: WatchFilterSet) -> List[str]:
        lines: List[str] = []
        if filters.whitelist:
            lines.append(f"关键词白名单：`{', '.join(filters.whitelist)}`")
        if filters.blacklist:
            lines.append(f"关键词黑名单：`{', '.join(filters.blacklist)}`")
        if filters.whitelist_regex:
            lines.append(f"正则白名单：`{', '.join(filters.whitelist_regex)}`")
        if filters.blacklist_regex:
            lines.append(f"正则黑名单：`{', '.join(filters.blacklist_regex)}`")
        return lines


def _forward_watch_create_request(
    request: ForwardWatchCreateRequest | None,
    legacy_fields: dict,
) -> ForwardWatchCreateRequest:
    if request is not None:
        if legacy_fields:
            raise TypeError("create_forward_watch received both request object and legacy fields")
        return request
    fields = dict(legacy_fields)
    filters = _watch_filter_set(fields)
    request = ForwardWatchCreateRequest(
        user_id=fields.pop("user_id"),
        source_id=fields.pop("source_id"),
        source_name=fields.pop("source_name"),
        dest_id=fields.pop("dest_id"),
        dest_name=fields.pop("dest_name"),
        filters=filters,
        preserve_source=fields.pop("preserve_source"),
        forward_mode=fields.pop("forward_mode"),
        extract_patterns=fields.pop("extract_patterns"),
    )
    _reject_extra_fields("create_forward_watch", fields)
    return request


def _record_watch_create_request(
    request: RecordWatchCreateRequest | None,
    legacy_fields: dict,
) -> RecordWatchCreateRequest:
    if request is not None:
        if legacy_fields:
            raise TypeError("create_record_watch received both request object and legacy fields")
        return request
    fields = dict(legacy_fields)
    filters = _watch_filter_set(fields)
    request = RecordWatchCreateRequest(
        user_id=fields.pop("user_id"),
        source_id=fields.pop("source_id"),
        source_name=fields.pop("source_name"),
        filters=filters,
    )
    _reject_extra_fields("create_record_watch", fields)
    return request


def _watch_filter_set(fields: dict) -> WatchFilterSet:
    return WatchFilterSet(
        whitelist=fields.pop("whitelist"),
        blacklist=fields.pop("blacklist"),
        whitelist_regex=fields.pop("whitelist_regex"),
        blacklist_regex=fields.pop("blacklist_regex"),
    )


def _reject_extra_fields(function_name: str, fields: dict) -> None:
    if fields:
        unknown = ", ".join(sorted(fields))
        raise TypeError(f"{function_name} got unexpected keyword argument(s): {unknown}")
