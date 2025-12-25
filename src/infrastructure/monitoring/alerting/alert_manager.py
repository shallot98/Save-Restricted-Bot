"""
告警管理器

职责：
- 统一的 send_alert API
- 多渠道分发（日志、Telegram）
- 抑制/限流/去重，防止告警风暴
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional

from .channels import Alert, AlertChannel, LogChannel, TelegramChannel

logger = logging.getLogger(__name__)

_alert_manager: Optional["AlertManager"] = None


def _env_bool(key: str, default: bool) -> bool:
    value = os.environ.get(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(key: str, default: int) -> int:
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


def _env_str(key: str, default: str = "") -> str:
    value = os.environ.get(key)
    return default if value is None else value.strip()


def _fingerprint(level: str, title: str, message: str, details: Dict[str, Any]) -> str:
    payload = {
        "level": level,
        "title": title,
        "message": message,
        "details": details,
    }
    dumped = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


@dataclass
class _SuppressionConfig:
    window_seconds: int
    max_alerts_per_window: int
    dedup_seconds: int


class AlertManager:
    """告警管理器（多渠道 + 抑制）"""

    def __init__(
        self,
        *,
        enabled: bool = True,
        channels: Optional[List[AlertChannel]] = None,
        suppression_window_minutes: Optional[int] = None,
        max_alerts_per_window: Optional[int] = None,
        dedup_seconds: Optional[int] = None,
    ) -> None:
        self._enabled = enabled
        self._channels = channels if channels is not None else self._build_default_channels()
        self._suppression = _SuppressionConfig(
            window_seconds=max((suppression_window_minutes if suppression_window_minutes is not None else _env_int("ALERT_SUPPRESSION_WINDOW_MINUTES", 5)) * 60, 1),
            max_alerts_per_window=max(max_alerts_per_window if max_alerts_per_window is not None else _env_int("ALERT_MAX_ALERTS_PER_WINDOW", 10), 1),
            dedup_seconds=max(dedup_seconds if dedup_seconds is not None else _env_int("ALERT_DEDUP_WINDOW_SECONDS", 60), 1),
        )
        self._sent_times: Deque[float] = deque()
        self._last_sent_by_fingerprint: Dict[str, float] = {}

    @property
    def enabled(self) -> bool:
        return self._enabled and _env_bool("ALERTING_ENABLED", True)

    def send_alert(self, *, level: str, title: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        if not self.enabled:
            return

        details = details or {}
        alert = Alert(level=level, title=title, message=message, details=details)
        fp = _fingerprint(alert.level, alert.title, alert.message, alert.details)

        now = time.time()
        if self._is_suppressed(now_epoch=now, fingerprint=fp):
            return

        for channel in self._channels:
            try:
                channel.send(alert)
            except Exception:
                logger.exception("告警渠道发送失败（已忽略）: %s", type(channel).__name__)

    def _is_suppressed(self, *, now_epoch: float, fingerprint: str) -> bool:
        self._prune(now_epoch=now_epoch)

        last_sent = self._last_sent_by_fingerprint.get(fingerprint)
        if last_sent is not None and (now_epoch - last_sent) < self._suppression.dedup_seconds:
            return True

        if len(self._sent_times) >= self._suppression.max_alerts_per_window:
            logger.warning(
                "告警抑制：窗口内告警已达上限 (%d/%d)",
                len(self._sent_times),
                self._suppression.max_alerts_per_window,
            )
            return True

        self._sent_times.append(now_epoch)
        self._last_sent_by_fingerprint[fingerprint] = now_epoch
        return False

    def _prune(self, *, now_epoch: float) -> None:
        cutoff = now_epoch - self._suppression.window_seconds
        while self._sent_times and self._sent_times[0] < cutoff:
            self._sent_times.popleft()

        # 同步清理去重表（只保留窗口内 + dedup 范围）
        dedup_cutoff = now_epoch - max(self._suppression.window_seconds, self._suppression.dedup_seconds)
        stale = [fp for fp, ts in self._last_sent_by_fingerprint.items() if ts < dedup_cutoff]
        for fp in stale:
            self._last_sent_by_fingerprint.pop(fp, None)

    @staticmethod
    def _build_default_channels() -> List[AlertChannel]:
        channels_env = _env_str("ALERT_CHANNELS", "log")
        channel_names = [c.strip().lower() for c in channels_env.split(",") if c.strip()]

        channels: List[AlertChannel] = []
        if "log" in channel_names or not channel_names:
            channels.append(LogChannel())

        if "telegram" in channel_names:
            token = _env_str("ALERT_TELEGRAM_BOT_TOKEN", "")
            chat_id = _env_str("ALERT_TELEGRAM_CHAT_ID", "")

            # 兼容：允许复用项目配置的 TOKEN / OWNER_ID
                if (not token) or (not chat_id):
                    try:
                        from src.core.config import settings  # noqa: WPS433

                        token = token or str(settings.get("TOKEN", "")).strip()
                        chat_id = chat_id or str(settings.get("OWNER_ID", "")).strip()
                    except Exception as e:
                        logger.debug("读取项目配置以启用 Telegram 告警失败，已忽略: %s", e, exc_info=True)

            if token and chat_id:
                channels.append(TelegramChannel(bot_token=token, chat_id=chat_id))

        return channels


def get_alert_manager() -> AlertManager:
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager
