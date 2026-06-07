"""Utilities for Telegram history copy runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .history_copy_models import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_BUDGET_WINDOW_SECONDS,
    DEFAULT_FAILURE_COOLDOWN_SECONDS,
    DEFAULT_FAILURE_THRESHOLD,
    DEFAULT_FLOODWAIT_BUFFER_SECONDS,
    DEFAULT_HOURLY_SEND_BUDGET,
    DEFAULT_MAX_FLOOD_RETRIES,
    DEFAULT_RATE_LIMIT_DELAY,
    DEFAULT_SESSION_NAME,
    DEFAULT_STATE_DB_PATH,
    HistoryCopySettings,
)

FATAL_ERROR_NAMES = {
    "AuthKeyUnregistered",
    "ChatForwardsRestricted",
    "SessionExpired",
    "SessionRevoked",
    "UserDeactivated",
    "UserDeactivatedBan",
    "ChatWriteForbidden",
    "ChatAdminRequired",
    "ChannelInvalid",
    "ChannelPrivate",
    "PeerIdInvalid",
    "UserBannedInChannel",
    "UserNotParticipant",
}
FATAL_ERROR_PATTERNS = (
    "AUTH_KEY_UNREGISTERED",
    "SESSION_EXPIRED",
    "SESSION_REVOKED",
    "USER_DEACTIVATED",
    "CHAT_WRITE_FORBIDDEN",
    "CHAT_ADMIN_REQUIRED",
    "CHAT_FORWARDS_RESTRICTED",
    "CHANNEL_PRIVATE",
    "PEER_ID_INVALID",
    "USER_NOT_PARTICIPANT",
)
FORWARD_RESTRICTED_ERROR_NAMES = {"ChatForwardsRestricted"}
FORWARD_RESTRICTED_ERROR_PATTERNS = (
    "CHAT_FORWARDS_RESTRICTED",
    "RESTRICTS FORWARDING CONTENT",
)


@dataclass(frozen=True)
class HistoryCopyResolutionOptions:
    state_db_path: Path = DEFAULT_STATE_DB_PATH
    batch_size: int = DEFAULT_BATCH_SIZE
    history_limit: Optional[int] = None
    max_flood_retries: int = DEFAULT_MAX_FLOOD_RETRIES
    rate_limit_delay: float = DEFAULT_RATE_LIMIT_DELAY
    hourly_send_budget: int = DEFAULT_HOURLY_SEND_BUDGET
    budget_window_seconds: int = DEFAULT_BUDGET_WINDOW_SECONDS
    failure_threshold: int = DEFAULT_FAILURE_THRESHOLD
    failure_cooldown_seconds: float = DEFAULT_FAILURE_COOLDOWN_SECONDS
    floodwait_buffer_seconds: float = DEFAULT_FLOODWAIT_BUFFER_SECONDS


def create_history_copy_client(session_name: str = DEFAULT_SESSION_NAME):
    """Reuse the existing dedicated user-session bootstrap."""

    try:
        from bot.services.pt_pay_runtime import create_dedicated_user_client
    except ModuleNotFoundError as exc:
        raise RuntimeError("缺少 pyrogram 依赖，请先安装 requirements.txt") from exc
    return create_dedicated_user_client(session_name=session_name)


def resolve_history_copy_settings(
    client: Any,
    source_chat_ref: str,
    dest_chat_ref: str,
    *,
    options: HistoryCopyResolutionOptions | None = None,
    **legacy_options: Any,
) -> HistoryCopySettings:
    """Resolve source/destination references to concrete chat ids."""

    options = _history_copy_resolution_options(options, legacy_options)
    source_chat = client.get_chat(coerce_chat_ref(source_chat_ref))
    dest_chat = client.get_chat(coerce_chat_ref(dest_chat_ref))
    return HistoryCopySettings(
        source_chat_ref=source_chat_ref,
        dest_chat_ref=dest_chat_ref,
        source_chat_id=str(source_chat.id),
        dest_chat_id=str(dest_chat.id),
        state_db_path=Path(options.state_db_path),
        batch_size=max(int(options.batch_size), 1),
        history_limit=max(int(options.history_limit), 1) if options.history_limit is not None else None,
        max_flood_retries=max(int(options.max_flood_retries), 1),
        rate_limit_delay=max(float(options.rate_limit_delay), 0.0),
        hourly_send_budget=max(int(options.hourly_send_budget), 0),
        budget_window_seconds=max(int(options.budget_window_seconds), 1),
        failure_threshold=max(int(options.failure_threshold), 0),
        failure_cooldown_seconds=max(float(options.failure_cooldown_seconds), 0.0),
        floodwait_buffer_seconds=max(float(options.floodwait_buffer_seconds), 0.0),
    )


def coerce_chat_ref(chat_ref: str) -> int | str:
    value = str(chat_ref).strip()
    try:
        return int(value)
    except ValueError:
        return value


def _history_copy_resolution_options(
    options: HistoryCopyResolutionOptions | None,
    legacy_options: dict[str, Any],
) -> HistoryCopyResolutionOptions:
    if options is not None:
        if legacy_options:
            raise TypeError("resolve_history_copy_settings received both options and legacy fields")
        return options
    resolved = HistoryCopyResolutionOptions(
        state_db_path=legacy_options.pop("state_db_path", DEFAULT_STATE_DB_PATH),
        batch_size=legacy_options.pop("batch_size", DEFAULT_BATCH_SIZE),
        history_limit=legacy_options.pop("history_limit", None),
        max_flood_retries=legacy_options.pop("max_flood_retries", DEFAULT_MAX_FLOOD_RETRIES),
        rate_limit_delay=legacy_options.pop("rate_limit_delay", DEFAULT_RATE_LIMIT_DELAY),
        hourly_send_budget=legacy_options.pop("hourly_send_budget", DEFAULT_HOURLY_SEND_BUDGET),
        budget_window_seconds=legacy_options.pop("budget_window_seconds", DEFAULT_BUDGET_WINDOW_SECONDS),
        failure_threshold=legacy_options.pop("failure_threshold", DEFAULT_FAILURE_THRESHOLD),
        failure_cooldown_seconds=legacy_options.pop("failure_cooldown_seconds", DEFAULT_FAILURE_COOLDOWN_SECONDS),
        floodwait_buffer_seconds=legacy_options.pop("floodwait_buffer_seconds", DEFAULT_FLOODWAIT_BUFFER_SECONDS),
    )
    if legacy_options:
        unknown = ", ".join(sorted(legacy_options))
        raise TypeError(f"resolve_history_copy_settings got unexpected keyword argument(s): {unknown}")
    return resolved


def is_fatal_error(exc: Exception) -> bool:
    error_name = type(exc).__name__
    if error_name in FATAL_ERROR_NAMES:
        return True
    error_text = str(exc).upper()
    return any(pattern in error_text for pattern in FATAL_ERROR_PATTERNS)


def is_forward_restricted_error(exc: Exception) -> bool:
    error_name = type(exc).__name__
    if error_name in FORWARD_RESTRICTED_ERROR_NAMES:
        return True
    error_text = str(exc).upper()
    return any(pattern in error_text for pattern in FORWARD_RESTRICTED_ERROR_PATTERNS)


def message_id(message: Any) -> int:
    return int(getattr(message, "id", 0) or 0)
