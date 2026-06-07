"""定时签到脚本运行时。"""

from __future__ import annotations

import threading
from typing import Any

from bot.utils.logger import get_logger

from .signin_models import ScheduledSigninTaskConfig, resolve_interval_seconds


logger = get_logger(__name__)


class ScheduledSigninRuntime:
    """定期向目标会话发送固定文本。"""

    def __init__(self, client: Any, task: ScheduledSigninTaskConfig) -> None:
        self._client = client
        self._task = task
        self._stop_event = threading.Event()
        self._worker: threading.Thread | None = None

    def start(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            return

        self._stop_event.clear()
        self._worker = threading.Thread(
            target=self._worker_loop,
            name=f"signin-{self._task.task_id}",
            daemon=True,
        )
        self._worker.start()
        logger.info(
            "✅ 定时签到脚本已启动: chat=%s interval=%s",
            self._task.chat_id,
            self._task.interval_spec,
        )

    def stop(self) -> None:
        self._stop_event.set()
        if self._worker is not None:
            self._worker.join(timeout=5)
        self._worker = None

    def _worker_loop(self) -> None:
        interval_seconds = resolve_interval_seconds(self._task.interval_spec)
        while not self._stop_event.wait(interval_seconds):
            self._send_once()

    def _send_once(self) -> None:
        try:
            logger.info("📤 定时签到脚本发送消息: chat=%s", self._task.chat_ref)
            self._client.send_message(self._task.chat_ref, self._task.message_text)
        except Exception as exc:
            logger.error(
                "❌ 定时签到脚本发送失败: chat=%s error=%s: %s",
                self._task.chat_ref,
                type(exc).__name__,
                exc,
                exc_info=True,
            )
