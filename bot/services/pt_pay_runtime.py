"""PT 支付监控运行时。"""

from __future__ import annotations

import queue
import threading
import time
from collections import defaultdict
from typing import Any, Optional

from pyrogram import filters

from bot.utils.logger import get_logger

from .pt_pay_client import coerce_chat_ref, create_dedicated_user_client
from .pt_pay_models import BotReplyResult, MonitorSettings, SourceMessageTask, resolve_trigger_delay_seconds
from .pt_pay_parsing import extract_pt_codes
from .pt_pay_reply import (
    contains_failure_keyword,
    contains_success_keyword,
    extract_message_text,
    wait_for_bot_reply,
)
from .pt_pay_settings import MonitorResolutionOptions, resolve_monitor_settings


logger = get_logger(__name__)

MIN_TRIGGER_PT_CODES = 2
MAX_TRACKED_SOURCE_MESSAGES = 5000
SOURCE_HANDLER_FILTER = filters.incoming & (filters.group | filters.channel | filters.private)
_TARGET_BOT_LOCKS: defaultdict[int, threading.Lock] = defaultdict(threading.Lock)


class PtPayMonitor:
    """监听指定群聊并按顺序调用目标 Bot 的 `/pay` 命令。"""

    def __init__(self, client: Any, settings: MonitorSettings) -> None:
        self._client = client
        self._settings = settings
        self._task_queue: queue.Queue[Optional[SourceMessageTask]] = queue.Queue()
        self._stop_event = threading.Event()
        self._processed_source_messages: set[int] = set()
        self._processed_lock = threading.Lock()
        self._worker: threading.Thread | None = None

    def start(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            return

        self._stop_event.clear()
        self._worker = threading.Thread(
            target=self._worker_loop,
            name=f"pt-pay-{self._settings.source_chat_id}",
            daemon=True,
        )
        self._worker.start()
        logger.info(
            "✅ PT 联动脚本已启动: source=%s -> target=%s",
            self._settings.source_chat_id,
            self._settings.target_bot_ref,
        )

    def stop(self) -> None:
        self._stop_event.set()
        self._task_queue.put(None)
        if self._worker is not None:
            self._worker.join(timeout=5)
        self._worker = None

    def handle_message(self, message: Any) -> None:
        if self._stop_event.is_set():
            return
        self._enqueue_source_message(message)

    def _enqueue_source_message(self, message: Any) -> None:
        if str(getattr(getattr(message, "chat", None), "id", "")) != self._settings.source_chat_id:
            return

        source_message_id = int(getattr(message, "id", 0) or 0)
        if source_message_id <= 0 or self._is_processed_message(source_message_id):
            return

        pt_codes = tuple(extract_pt_codes(extract_message_text(message)))
        if len(pt_codes) < MIN_TRIGGER_PT_CODES:
            logger.info(
                "ℹ️ PT 联动脚本忽略消息: source=%s message_id=%s 提取到 %s 个 PT 编号，未达到最小触发数 %s",
                self._settings.source_chat_id,
                source_message_id,
                len(pt_codes),
                MIN_TRIGGER_PT_CODES,
            )
            return

        self._task_queue.put(SourceMessageTask(source_message_id=source_message_id, pt_codes=pt_codes))
        logger.info(
            "📥 PT 联动脚本捕获消息: source=%s message_id=%s pt_codes=%s",
            self._settings.source_chat_id,
            source_message_id,
            ",".join(pt_codes),
        )

    def _is_processed_message(self, source_message_id: int) -> bool:
        with self._processed_lock:
            if source_message_id in self._processed_source_messages:
                return True
            if len(self._processed_source_messages) >= MAX_TRACKED_SOURCE_MESSAGES:
                self._processed_source_messages.clear()
            self._processed_source_messages.add(source_message_id)
            return False

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            task = self._task_queue.get()
            if task is None:
                return
            try:
                self._process_source_task(task)
            except Exception as exc:
                logger.error(
                    "❌ PT 联动脚本处理失败: source=%s message_id=%s error=%s: %s",
                    self._settings.source_chat_id,
                    task.source_message_id,
                    type(exc).__name__,
                    exc,
                    exc_info=True,
                )

    def _process_source_task(self, task: SourceMessageTask) -> None:
        delay_seconds = resolve_trigger_delay_seconds(self._settings.trigger_delay_spec)
        if delay_seconds > 0:
            time.sleep(delay_seconds)
        for pt_code in task.pt_codes:
            if self._stop_event.is_set():
                return
            result = self._send_pay_command_and_wait(pt_code)
            if result.success:
                logger.info("✅ PT 联动脚本命中成功: source=%s pt_code=%s", self._settings.source_chat_id, pt_code)
                return
        logger.info("ℹ️ PT 联动脚本未命中成功回复: source=%s pt_codes=%s", self._settings.source_chat_id, ",".join(task.pt_codes))

    def _send_pay_command_and_wait(self, pt_code: str) -> BotReplyResult:
        command = f"{self._settings.command_prefix} {pt_code}"
        target_chat_ref = self._ensure_target_chat_ready()
        bot_lock = _TARGET_BOT_LOCKS[self._settings.target_bot_id]
        with bot_lock:
            logger.info("📤 PT 联动脚本发送命令: target=%s command=%s", self._settings.target_bot_ref, command)
            sent_message = self._client.send_message(target_chat_ref, command)
            result = wait_for_bot_reply(
                client=self._client,
                target_chat_ref=target_chat_ref,
                sent_message_id=int(getattr(sent_message, "id", 0) or 0),
                success_keywords=self._settings.success_keywords,
                timeout_seconds=self._settings.reply_timeout_seconds,
                poll_interval_seconds=self._settings.poll_interval_seconds,
                history_limit=self._settings.history_limit,
            )

        if result.matched_reply and not result.success:
            logger.info("⚠️ PT 联动脚本收到失败回复，立即尝试下一个 PT: target=%s reply=%s", self._settings.target_bot_ref, result.matched_reply)

        if not result.success and self._settings.send_interval_seconds > 0:
            time.sleep(self._settings.send_interval_seconds)
        return result

    def _ensure_target_chat_ready(self) -> int | str:
        preferred_ref = coerce_chat_ref(self._settings.target_bot_ref)
        try:
            self._client.get_chat(preferred_ref)
            return preferred_ref
        except Exception as preferred_exc:
            fallback_ref = self._settings.target_bot_id
            logger.warning(
                "⚠️ PT 联动脚本目标 Bot 首选引用不可用: ref=%s error=%s: %s，尝试回退到 id=%s",
                self._settings.target_bot_ref,
                type(preferred_exc).__name__,
                preferred_exc,
                fallback_ref,
            )
            self._client.get_chat(fallback_ref)
            return fallback_ref
