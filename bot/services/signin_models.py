"""定时签到脚本的数据模型。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


DEFAULT_INTERVAL_SPEC = "1d"
DEFAULT_INTERVAL_SECONDS = 86400.0
_INTERVAL_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([smhdSMHD]?)\s*$")
_UNIT_SECONDS = {
    "s": 1.0,
    "m": 60.0,
    "h": 3600.0,
    "d": 86400.0,
}
_UNIT_LABELS = {
    "s": "秒",
    "m": "分钟",
    "h": "小时",
    "d": "天",
}


def normalize_message_text(message_text: str | None) -> str:
    value = str(message_text or "").strip()
    if not value:
        raise ValueError("签到消息不能为空")
    return value


def normalize_interval_spec(interval_spec: str | None) -> str:
    value = str(interval_spec or "").strip()
    if not value:
        return DEFAULT_INTERVAL_SPEC

    match = _INTERVAL_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError("请输入正数间隔，例如 3600、30m、8h、1d")

    amount = float(match.group(1))
    if amount <= 0:
        raise ValueError("签到间隔必须大于 0")

    unit = (match.group(2) or "s").lower()
    return f"{_format_amount(amount)}{unit}"


def resolve_interval_seconds(interval_spec: str | None) -> float:
    normalized = normalize_interval_spec(interval_spec)
    match = _INTERVAL_PATTERN.fullmatch(normalized)
    if match is None:
        return DEFAULT_INTERVAL_SECONDS

    amount = float(match.group(1))
    unit = (match.group(2) or "s").lower()
    return amount * _UNIT_SECONDS[unit]


def describe_interval_spec(interval_spec: str | None) -> str:
    normalized = normalize_interval_spec(interval_spec)
    match = _INTERVAL_PATTERN.fullmatch(normalized)
    if match is None:
        return f"每 {DEFAULT_INTERVAL_SPEC}"

    amount = float(match.group(1))
    unit = (match.group(2) or "s").lower()
    return f"每 {_format_amount(amount)} {_UNIT_LABELS[unit]}"


def _format_amount(value: float) -> str:
    return str(int(value)) if value.is_integer() else f"{value:.3f}".rstrip("0").rstrip(".")


@dataclass(frozen=True)
class ScheduledSigninTaskConfig:
    task_id: str
    chat_id: str
    chat_name: str
    chat_ref: str
    message_text: str
    interval_spec: str = DEFAULT_INTERVAL_SPEC
    enabled: bool = True

    @classmethod
    def from_dict(cls, task_id: str, data: dict[str, Any]) -> "ScheduledSigninTaskConfig":
        chat_id = str(data.get("chat_id") or "").strip()
        if not chat_id:
            raise ValueError("chat_id 不能为空")
        chat_name = str(data.get("chat_name") or "").strip() or chat_id
        chat_ref = str(data.get("chat_ref") or "").strip() or chat_id
        return cls(
            task_id=str(task_id),
            chat_id=chat_id,
            chat_name=chat_name,
            chat_ref=chat_ref,
            message_text=normalize_message_text(data.get("message_text")),
            interval_spec=normalize_interval_spec(data.get("interval_spec", DEFAULT_INTERVAL_SPEC)),
            enabled=bool(data.get("enabled", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "chat_id": self.chat_id,
            "chat_name": self.chat_name,
            "chat_ref": self.chat_ref or self.chat_id,
            "message_text": normalize_message_text(self.message_text),
            "interval_spec": normalize_interval_spec(self.interval_spec),
            "enabled": self.enabled,
        }
