"""PT 支付监控的数据模型。"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Any, Optional, Sequence


DEFAULT_SUCCESS_KEYWORDS = ("成功",)
DEFAULT_COMMAND_PREFIX = "/pay"
DEFAULT_REPLY_TIMEOUT_SECONDS = 20.0
DEFAULT_POLL_INTERVAL_SECONDS = 1.0
DEFAULT_SEND_INTERVAL_SECONDS = 1.0
DEFAULT_HISTORY_LIMIT = 10
DEFAULT_TRIGGER_DELAY_SPEC = "0"
_USERNAME_PATTERN = re.compile(r"@?[A-Za-z0-9_]{5,}$")


def normalize_keywords(keywords: Optional[Sequence[str]]) -> tuple[str, ...]:
    if not keywords:
        return DEFAULT_SUCCESS_KEYWORDS

    normalized = tuple(keyword.strip() for keyword in keywords if keyword and keyword.strip())
    return normalized or DEFAULT_SUCCESS_KEYWORDS


def derive_target_bot_ref(target_bot_ref: str | None, target_bot_name: str, target_bot_id: int) -> str:
    explicit_ref = str(target_bot_ref or "").strip()
    if explicit_ref:
        return explicit_ref

    candidate_name = str(target_bot_name or "").strip()
    if candidate_name and _USERNAME_PATTERN.fullmatch(candidate_name):
        return candidate_name if candidate_name.startswith("@") else f"@{candidate_name}"

    return str(target_bot_id)


def normalize_trigger_delay_spec(delay_spec: str | None) -> str:
    value = str(delay_spec or "").strip()
    if not value:
        return DEFAULT_TRIGGER_DELAY_SPEC

    if "-" not in value:
        seconds = _parse_non_negative_seconds(value)
        return _format_seconds(seconds)

    raw_min, raw_max = (part.strip() for part in value.split("-", 1))
    min_seconds = _parse_non_negative_seconds(raw_min)
    max_seconds = _parse_non_negative_seconds(raw_max)
    if min_seconds > max_seconds:
        raise ValueError("延时范围格式错误：最小值不能大于最大值")
    return f"{_format_seconds(min_seconds)}-{_format_seconds(max_seconds)}"


def resolve_trigger_delay_seconds(delay_spec: str, rng: random.Random | None = None) -> float:
    normalized = normalize_trigger_delay_spec(delay_spec)
    if "-" not in normalized:
        return float(normalized)

    raw_min, raw_max = normalized.split("-", 1)
    min_seconds = float(raw_min)
    max_seconds = float(raw_max)
    generator = rng or random
    return generator.uniform(min_seconds, max_seconds)


def describe_trigger_delay_spec(delay_spec: str | None) -> str:
    normalized = normalize_trigger_delay_spec(delay_spec)
    if "-" not in normalized:
        return f"固定 {normalized} 秒"
    return f"随机 {normalized} 秒"


def _parse_non_negative_seconds(value: str) -> float:
    try:
        seconds = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("请输入非负秒数，或范围如 0-100") from exc
    if seconds < 0:
        raise ValueError("延时不能为负数")
    return seconds


def _format_seconds(value: float) -> str:
    return str(int(value)) if value.is_integer() else f"{value:.3f}".rstrip("0").rstrip(".")


@dataclass(frozen=True)
class MonitorSettings:
    source_chat_ref: str
    target_bot_ref: str
    source_chat_id: str
    target_bot_id: int
    command_prefix: str = DEFAULT_COMMAND_PREFIX
    success_keywords: tuple[str, ...] = DEFAULT_SUCCESS_KEYWORDS
    reply_timeout_seconds: float = DEFAULT_REPLY_TIMEOUT_SECONDS
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS
    send_interval_seconds: float = DEFAULT_SEND_INTERVAL_SECONDS
    history_limit: int = DEFAULT_HISTORY_LIMIT
    trigger_delay_spec: str = DEFAULT_TRIGGER_DELAY_SPEC


@dataclass(frozen=True)
class SourceMessageTask:
    source_message_id: int
    pt_codes: tuple[str, ...]


@dataclass(frozen=True)
class BotReplyResult:
    success: bool
    matched_reply: str
    observed_replies: tuple[str, ...]


@dataclass(frozen=True)
class PTPayTaskConfig:
    task_id: str
    source_chat_id: str
    source_name: str
    target_bot_id: int
    target_bot_name: str
    target_bot_ref: str = ""
    enabled: bool = True
    command_prefix: str = DEFAULT_COMMAND_PREFIX
    success_keywords: tuple[str, ...] = DEFAULT_SUCCESS_KEYWORDS
    reply_timeout_seconds: float = DEFAULT_REPLY_TIMEOUT_SECONDS
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS
    send_interval_seconds: float = DEFAULT_SEND_INTERVAL_SECONDS
    history_limit: int = DEFAULT_HISTORY_LIMIT
    trigger_delay_spec: str = DEFAULT_TRIGGER_DELAY_SPEC

    @classmethod
    def from_dict(cls, task_id: str, data: dict[str, Any]) -> "PTPayTaskConfig":
        target_bot_id = int(data.get("target_bot_id"))
        target_bot_name = str(data.get("target_bot_name") or "").strip()
        target_bot_ref = derive_target_bot_ref(data.get("target_bot_ref"), target_bot_name, target_bot_id)
        return cls(
            task_id=task_id,
            source_chat_id=str(data.get("source_chat_id") or "").strip(),
            source_name=str(data.get("source_name") or "").strip(),
            target_bot_id=target_bot_id,
            target_bot_name=target_bot_name,
            target_bot_ref=target_bot_ref,
            enabled=bool(data.get("enabled", True)),
            command_prefix=str(data.get("command_prefix") or DEFAULT_COMMAND_PREFIX).strip() or DEFAULT_COMMAND_PREFIX,
            success_keywords=normalize_keywords(data.get("success_keywords")),
            reply_timeout_seconds=max(float(data.get("reply_timeout_seconds", DEFAULT_REPLY_TIMEOUT_SECONDS)), 1.0),
            poll_interval_seconds=max(float(data.get("poll_interval_seconds", DEFAULT_POLL_INTERVAL_SECONDS)), 0.0),
            send_interval_seconds=max(float(data.get("send_interval_seconds", DEFAULT_SEND_INTERVAL_SECONDS)), 0.0),
            history_limit=max(int(data.get("history_limit", DEFAULT_HISTORY_LIMIT)), 1),
            trigger_delay_spec=normalize_trigger_delay_spec(data.get("trigger_delay_spec", DEFAULT_TRIGGER_DELAY_SPEC)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_chat_id": self.source_chat_id,
            "source_name": self.source_name,
            "target_bot_id": self.target_bot_id,
            "target_bot_name": self.target_bot_name,
            "target_bot_ref": derive_target_bot_ref(self.target_bot_ref, self.target_bot_name, self.target_bot_id),
            "enabled": self.enabled,
            "command_prefix": self.command_prefix,
            "success_keywords": list(self.success_keywords),
            "reply_timeout_seconds": self.reply_timeout_seconds,
            "poll_interval_seconds": self.poll_interval_seconds,
            "send_interval_seconds": self.send_interval_seconds,
            "history_limit": self.history_limit,
            "trigger_delay_spec": normalize_trigger_delay_spec(self.trigger_delay_spec),
        }

    def to_monitor_settings(self) -> MonitorSettings:
        return MonitorSettings(
            source_chat_ref=self.source_chat_id,
            target_bot_ref=derive_target_bot_ref(self.target_bot_ref, self.target_bot_name, self.target_bot_id),
            source_chat_id=self.source_chat_id,
            target_bot_id=self.target_bot_id,
            command_prefix=self.command_prefix,
            success_keywords=self.success_keywords,
            reply_timeout_seconds=self.reply_timeout_seconds,
            poll_interval_seconds=self.poll_interval_seconds,
            send_interval_seconds=self.send_interval_seconds,
            history_limit=self.history_limit,
            trigger_delay_spec=normalize_trigger_delay_spec(self.trigger_delay_spec),
        )
