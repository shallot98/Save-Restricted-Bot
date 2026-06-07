"""PT pay monitor settings resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

from .pt_pay_client import coerce_chat_ref
from .pt_pay_models import (
    DEFAULT_COMMAND_PREFIX,
    DEFAULT_HISTORY_LIMIT,
    DEFAULT_POLL_INTERVAL_SECONDS,
    DEFAULT_REPLY_TIMEOUT_SECONDS,
    DEFAULT_SEND_INTERVAL_SECONDS,
    MonitorSettings,
    normalize_keywords,
)


@dataclass(frozen=True)
class MonitorResolutionOptions:
    command_prefix: str = DEFAULT_COMMAND_PREFIX
    success_keywords: Optional[Sequence[str]] = None
    reply_timeout_seconds: float = DEFAULT_REPLY_TIMEOUT_SECONDS
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS
    send_interval_seconds: float = DEFAULT_SEND_INTERVAL_SECONDS
    history_limit: int = DEFAULT_HISTORY_LIMIT


def resolve_monitor_settings(
    client: Any,
    source_chat_ref: str,
    target_bot_ref: str,
    *legacy_args: Any,
    options: MonitorResolutionOptions | None = None,
    **legacy_options: Any,
) -> MonitorSettings:
    resolved = _resolve_options(
        legacy_args,
        options,
        _monitor_resolution_options(legacy_options),
    )
    source_chat = client.get_chat(coerce_chat_ref(source_chat_ref))
    target_bot = client.get_chat(coerce_chat_ref(target_bot_ref))
    return MonitorSettings(
        source_chat_ref=source_chat_ref,
        target_bot_ref=target_bot_ref,
        source_chat_id=str(source_chat.id),
        target_bot_id=int(target_bot.id),
        command_prefix=(resolved.command_prefix or DEFAULT_COMMAND_PREFIX).strip() or DEFAULT_COMMAND_PREFIX,
        success_keywords=normalize_keywords(resolved.success_keywords),
        reply_timeout_seconds=max(resolved.reply_timeout_seconds, 1.0),
        poll_interval_seconds=max(resolved.poll_interval_seconds, 0.0),
        send_interval_seconds=max(resolved.send_interval_seconds, 0.0),
        history_limit=max(resolved.history_limit, 1),
    )


def _monitor_resolution_options(legacy_options: dict[str, Any]) -> MonitorResolutionOptions:
    options = MonitorResolutionOptions(
        command_prefix=legacy_options.pop("command_prefix", DEFAULT_COMMAND_PREFIX),
        success_keywords=legacy_options.pop("success_keywords", None),
        reply_timeout_seconds=legacy_options.pop("reply_timeout_seconds", DEFAULT_REPLY_TIMEOUT_SECONDS),
        poll_interval_seconds=legacy_options.pop("poll_interval_seconds", DEFAULT_POLL_INTERVAL_SECONDS),
        send_interval_seconds=legacy_options.pop("send_interval_seconds", DEFAULT_SEND_INTERVAL_SECONDS),
        history_limit=legacy_options.pop("history_limit", DEFAULT_HISTORY_LIMIT),
    )
    if legacy_options:
        unknown = ", ".join(sorted(legacy_options))
        raise TypeError(f"resolve_monitor_settings got unexpected keyword argument(s): {unknown}")
    return options


def _resolve_options(
    legacy_args: tuple[Any, ...],
    options: MonitorResolutionOptions | None,
    keyword_options: MonitorResolutionOptions,
) -> MonitorResolutionOptions:
    if options is not None and legacy_args:
        raise TypeError("options 不能与旧式位置参数同时使用")
    if options is not None:
        return options
    if not legacy_args:
        return keyword_options
    if len(legacy_args) > 6:
        raise TypeError("resolve_monitor_settings 最多接收 6 个旧式可选位置参数")

    values = list(keyword_options.__dict__.values())
    values[: len(legacy_args)] = legacy_args
    return MonitorResolutionOptions(*values)
