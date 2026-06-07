"""PT pay target-bot reply polling."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from bot.utils.logger import get_logger

from .pt_pay_models import (
    BotReplyResult,
    DEFAULT_HISTORY_LIMIT,
    DEFAULT_POLL_INTERVAL_SECONDS,
    DEFAULT_REPLY_TIMEOUT_SECONDS,
    DEFAULT_SUCCESS_KEYWORDS,
    normalize_keywords,
)

logger = get_logger(__name__)

FAILURE_REPLY_KEYWORDS = ("无效", "不存在")


@dataclass(frozen=True)
class BotReplyWaitOptions:
    success_keywords: Sequence[str] = DEFAULT_SUCCESS_KEYWORDS
    timeout_seconds: float = DEFAULT_REPLY_TIMEOUT_SECONDS
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS
    history_limit: int = DEFAULT_HISTORY_LIMIT


@dataclass
class ReplyScanState:
    seen_text_by_id: dict[int, str] = field(default_factory=dict)
    observed_replies: list[str] = field(default_factory=list)


def contains_success_keyword(text: str, keywords: Sequence[str]) -> bool:
    if not text:
        return False
    return any(keyword in text for keyword in normalize_keywords(keywords))


def contains_failure_keyword(text: str) -> bool:
    if not text:
        return False
    return any(keyword in text for keyword in FAILURE_REPLY_KEYWORDS)


def extract_message_text(message: Any) -> str:
    text = getattr(message, "text", None) or getattr(message, "caption", None) or ""
    return str(text).strip()


def wait_for_bot_reply(
    client: Any,
    target_chat_ref: int | str,
    sent_message_id: int,
    *legacy_args: Any,
    options: BotReplyWaitOptions | None = None,
    **legacy_options: Any,
) -> BotReplyResult:
    resolved = _resolve_wait_options(
        legacy_args,
        options,
        _bot_reply_wait_options(legacy_options),
    )
    deadline = time.monotonic() + max(resolved.timeout_seconds, 0.0)
    state = ReplyScanState()

    while time.monotonic() <= deadline:
        result = _scan_latest_replies(
            client,
            target_chat_ref,
            sent_message_id,
            options=resolved,
            state=state,
        )
        if result is not None:
            return result
        time.sleep(resolved.poll_interval_seconds)

    return BotReplyResult(False, "", tuple(state.observed_replies))


def _bot_reply_wait_options(legacy_options: dict[str, Any]) -> BotReplyWaitOptions:
    options = BotReplyWaitOptions(
        legacy_options.pop("success_keywords", DEFAULT_SUCCESS_KEYWORDS),
        legacy_options.pop("timeout_seconds", DEFAULT_REPLY_TIMEOUT_SECONDS),
        legacy_options.pop("poll_interval_seconds", DEFAULT_POLL_INTERVAL_SECONDS),
        legacy_options.pop("history_limit", DEFAULT_HISTORY_LIMIT),
    )
    if legacy_options:
        unknown = ", ".join(sorted(legacy_options))
        raise TypeError(f"wait_for_bot_reply got unexpected keyword argument(s): {unknown}")
    return options


def _resolve_wait_options(
    legacy_args: tuple[Any, ...],
    options: Optional[BotReplyWaitOptions],
    keyword_options: BotReplyWaitOptions,
) -> BotReplyWaitOptions:
    if options is not None and legacy_args:
        raise TypeError("options 不能与旧式位置参数同时使用")
    if options is not None:
        return options
    if not legacy_args:
        return keyword_options
    if len(legacy_args) > 4:
        raise TypeError("wait_for_bot_reply 最多接收 4 个旧式可选位置参数")

    values = list(keyword_options.__dict__.values())
    values[: len(legacy_args)] = legacy_args
    return BotReplyWaitOptions(*values)


def _scan_latest_replies(
    client: Any,
    target_chat_ref: int | str,
    sent_message_id: int,
    *,
    options: BotReplyWaitOptions,
    state: ReplyScanState,
) -> Optional[BotReplyResult]:
    try:
        for message in client.get_chat_history(target_chat_ref, limit=options.history_limit):
            result = _inspect_reply_message(message, sent_message_id, options=options, state=state)
            if result is not None:
                return result
    except Exception as exc:
        logger.warning(f"轮询目标 Bot 回复失败: {type(exc).__name__}: {exc}")
    return None


def _inspect_reply_message(
    message: Any,
    sent_message_id: int,
    *,
    options: BotReplyWaitOptions,
    state: ReplyScanState,
) -> Optional[BotReplyResult]:
    message_id = int(getattr(message, "id", 0) or 0)
    if message_id <= sent_message_id:
        return None
    if bool(getattr(message, "outgoing", False)):
        return None

    current_text = extract_message_text(message)
    if not current_text or state.seen_text_by_id.get(message_id) == current_text:
        return None

    state.seen_text_by_id[message_id] = current_text
    state.observed_replies.append(current_text)
    if contains_success_keyword(current_text, options.success_keywords):
        return BotReplyResult(True, current_text, tuple(state.observed_replies))
    if contains_failure_keyword(current_text):
        return BotReplyResult(False, current_text, tuple(state.observed_replies))
    return None
