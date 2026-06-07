"""Bot staging helpers for Telegram history copy."""

from __future__ import annotations

import time
from typing import Any

from bot.utils.logger import get_logger
from .history_copy_utils import message_id

STAGING_WAIT_SECONDS = 10.0
STAGING_POLL_SECONDS = 0.25
STAGING_HISTORY_EXTRA = 10
STAGING_HISTORY_MIN = 20

logger = get_logger(__name__)


class HistoryCopyStagingMixin:
    def _public_source_ref(self) -> str | None:
        source_ref = str(self._settings.source_chat_ref or "").strip()
        if not source_ref:
            return None
        try:
            int(source_ref)
        except ValueError:
            return source_ref
        return None

    def _can_use_bot_staging(self) -> bool:
        return bool(self._bot_client and self._bot_staging_chat_id and self._bot_staging_source_ref)

    def _delete_staged_messages(self, message_ids: list[int]) -> None:
        if not message_ids or not self._bot_staging_source_ref:
            return
        try:
            self._client.delete_messages(self._bot_staging_source_ref, message_ids)
        except Exception as exc:
            logger.warning(
                "⚠️ 删除 Bot 中转消息失败: ids=%s error=%s: %s",
                message_ids,
                type(exc).__name__,
                exc,
            )

    def _latest_bot_staging_message_id(self) -> int:
        for item in self._client.get_chat_history(self._bot_staging_source_ref, limit=1):
            return message_id(item)
        return 0

    def _wait_for_user_staged_message_ids(self, previous_message_id: int, expected_count: int) -> list[int]:
        deadline = time.monotonic() + STAGING_WAIT_SECONDS
        history_limit = max(expected_count + STAGING_HISTORY_EXTRA, STAGING_HISTORY_MIN)
        while time.monotonic() <= deadline:
            staged_ids = self._collect_staged_message_ids(previous_message_id, history_limit)
            if len(staged_ids) >= expected_count:
                return staged_ids[:expected_count]
            time.sleep(STAGING_POLL_SECONDS)
        raise RuntimeError(
            f"Bot 中转消息未出现在 User 私聊视角: previous_id={previous_message_id} expected={expected_count}"
        )

    def _collect_staged_message_ids(self, previous_message_id: int, history_limit: int) -> list[int]:
        messages = list(self._client.get_chat_history(self._bot_staging_source_ref, limit=history_limit))
        return sorted(
            message_id(item)
            for item in messages
            if message_id(item) > previous_message_id and not bool(getattr(item, "outgoing", False))
        )

    def _verify_copy_result_target(self, result: Any, operation_name: str) -> None:
        messages = result if isinstance(result, list) else [result]
        expected_chat_id = int(self._settings.dest_chat_id)
        copied_ids = self._collect_copy_result_ids(messages, expected_chat_id, operation_name)
        logger.info(
            "✅ %s 已写入目标: dest=%s message_ids=%s",
            operation_name,
            expected_chat_id,
            ",".join(map(str, copied_ids)),
        )

    @staticmethod
    def _collect_copy_result_ids(messages, expected_chat_id, operation_name):
        copied_ids: list[int] = []
        for item in messages:
            copied_ids.append(message_id(item))
            chat = getattr(item, "chat", None)
            if chat is None or getattr(chat, "id", None) is None:
                continue
            actual_chat_id = int(getattr(chat, "id"))
            if actual_chat_id != expected_chat_id:
                raise RuntimeError(
                    f"{operation_name} 返回目标不匹配: expected={expected_chat_id} actual={actual_chat_id}"
                )
        return copied_ids
