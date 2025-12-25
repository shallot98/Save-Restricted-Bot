"""
告警渠道实现

- LogChannel: 输出到应用日志
- TelegramChannel: 通过 Telegram Bot API 发送消息（失败不影响主流程）
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Alert:
    level: str
    title: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class AlertChannel:
    """告警渠道抽象"""

    def send(self, alert: Alert) -> None:
        raise NotImplementedError


class LogChannel(AlertChannel):
    """日志告警渠道"""

    def __init__(self, *, logger_name: str = "monitoring.alerts") -> None:
        self._logger = logging.getLogger(logger_name)

    def send(self, alert: Alert) -> None:
        payload = {"title": alert.title, "message": alert.message, "details": alert.details}
        level = (alert.level or "info").lower()
        if level in {"error", "critical"}:
            self._logger.error("告警: %s", payload)
        elif level in {"warning", "warn"}:
            self._logger.warning("告警: %s", payload)
        else:
            self._logger.info("告警: %s", payload)


class TelegramChannel(AlertChannel):
    """Telegram 告警渠道（Bot API）"""

    def __init__(
        self,
        *,
        bot_token: str,
        chat_id: str,
        api_base: str = "https://api.telegram.org",
        timeout_seconds: float = 3.0,
    ) -> None:
        self._bot_token = bot_token.strip()
        self._chat_id = str(chat_id).strip()
        self._api_base = api_base.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def send(self, alert: Alert) -> None:
        if not self._bot_token or not self._chat_id:
            return

        text = self._format(alert)
        url = f"{self._api_base}/bot{self._bot_token}/sendMessage"
        data = {
            "chat_id": self._chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }

        try:
            import requests  # 依赖已在 requirements 中

            requests.post(url, json=data, timeout=self._timeout_seconds)
        except Exception as e:
            logger.warning("Telegram 告警发送失败: %s", e)

    @staticmethod
    def _format(alert: Alert) -> str:
        ts = alert.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        level = (alert.level or "info").upper()
        lines = [f"[{level}] {alert.title}", alert.message, f"时间: {ts}"]
        return "\n".join([line for line in lines if line])

