"""Single-message copy helpers for Telegram history copy."""

from __future__ import annotations

from dataclasses import dataclass

from bot.utils.logger import get_logger
from .history_copy_models import HistoryCopyStats
from .history_copy_utils import is_forward_restricted_error

logger = get_logger(__name__)


@dataclass(frozen=True)
class SingleCopyContext:
    source_ref: str
    message_id_value: int
    stats: HistoryCopyStats


class HistoryCopySingleMixin:
    def _copy_single_entry(self, message, stats: HistoryCopyStats) -> None:
        current_message_id = int(getattr(message, "id", 0) or 0)
        if self._state_store.is_copied(
            self._settings.source_chat_id,
            self._settings.dest_chat_id,
            current_message_id,
        ):
            stats.skipped_count += 1
            return

        if self._copy_single_via_bot(current_message_id, stats):
            return
        self._copy_single_via_user(current_message_id, stats)

    def _copy_single_via_user(self, message_id_value: int, stats: HistoryCopyStats) -> None:
        try:
            self._execute_with_retry(
                "TG 直拷消息",
                lambda: self._client.copy_message(
                    int(self._settings.dest_chat_id),
                    int(self._settings.source_chat_id),
                    message_id_value,
                ),
                is_outbound=True,
                skip_failure_record=is_forward_restricted_error,
            )
        except Exception as exc:
            self._handle_user_copy_error(message_id_value, stats, exc)
            return
        self._mark_message_copied(message_id_value, stats, "TG 直拷")

    def _handle_user_copy_error(self, message_id_value: int, stats: HistoryCopyStats, exc: Exception) -> None:
        if is_forward_restricted_error(exc):
            self._resend_single_entry(message_id_value, stats)
            return
        self._raise_if_fatal(exc, message_id_value)
        stats.record_failure(message_id_value)
        logger.warning("⚠️ TG 直拷消息失败，继续后续消息: id=%s error=%s", message_id_value, exc)

    def _copy_single_via_bot(self, message_id_value: int, stats: HistoryCopyStats) -> bool:
        source_ref = self._public_source_ref()
        if self._bot_client is None or source_ref is None:
            return False
        try:
            self._execute_with_retry(
                "Bot 直拷消息",
                lambda: self._bot_client.copy_message(
                    int(self._settings.dest_chat_id),
                    source_ref,
                    message_id_value,
                ),
                is_outbound=True,
                skip_failure_record=self._skip_failure_record,
            )
        except Exception as exc:
            return self._copy_single_after_bot_failure(
                SingleCopyContext(source_ref, message_id_value, stats),
                exc,
            )

        self._mark_message_copied(message_id_value, stats, "Bot 直拷")
        return True

    def _copy_single_after_bot_failure(self, context, exc):
        logger.warning(
            "⚠️ Bot 直拷消息失败，尝试 Bot 私聊中转: source_ref=%s id=%s error=%s: %s",
            context.source_ref,
            context.message_id_value,
            type(exc).__name__,
            exc,
        )
        return self._copy_single_via_bot_staging(
            context.source_ref,
            context.message_id_value,
            context.stats,
        )

    def _copy_single_via_bot_staging(self, source_ref: str, message_id_value: int, stats: HistoryCopyStats) -> bool:
        if not self._can_use_bot_staging():
            return False
        staged_id = 0
        try:
            staged_id = self._stage_single_message_with_bot(source_ref, message_id_value)
            self._copy_staged_single_message(staged_id)
        except Exception as exc:
            logger.warning(
                "⚠️ Bot 中转直拷消息失败，回退到 User 直拷: id=%s error=%s: %s",
                message_id_value,
                type(exc).__name__,
                exc,
            )
            return False
        finally:
            self._delete_staged_messages([staged_id] if staged_id > 0 else [])

        self._mark_message_copied(message_id_value, stats, "Bot 中转直拷")
        return True

    def _stage_single_message_with_bot(self, source_ref: str, message_id_value: int) -> int:
        previous_staging_id = self._latest_bot_staging_message_id()
        self._execute_with_retry(
            "Bot 中转暂存消息",
            lambda: self._bot_client.copy_message(
                int(self._bot_staging_chat_id),
                source_ref,
                message_id_value,
            ),
            is_outbound=True,
            skip_failure_record=self._skip_failure_record,
        )
        staged_id = self._wait_for_user_staged_message_ids(previous_staging_id, 1)[0]
        if staged_id <= 0:
            raise RuntimeError("Bot 中转消息未返回有效消息 ID")
        return staged_id

    def _copy_staged_single_message(self, staged_id: int) -> None:
        copied_message = self._execute_with_retry(
            "Bot 中转直拷消息",
            lambda: self._client.copy_message(
                int(self._settings.dest_chat_id),
                self._bot_staging_source_ref,
                staged_id,
            ),
            is_outbound=True,
            skip_failure_record=self._skip_failure_record,
        )
        self._verify_copy_result_target(copied_message, "Bot 中转直拷消息")

    def _resend_single_entry(self, message_id_value: int, stats: HistoryCopyStats) -> None:
        logger.info(
            "🔒 消息受保护，回退到下载后重发: source=%s message_id=%s",
            self._settings.source_chat_id,
            message_id_value,
        )
        try:
            self._resender.resend(message_id_value)
        except Exception as exc:
            self._raise_if_fatal(exc, message_id_value)
            stats.record_failure(message_id_value)
            logger.warning("⚠️ 重发消息失败，继续后续消息: id=%s error=%s", message_id_value, exc)
            return
        self._mark_message_copied(message_id_value, stats, "下载后重发")

    def _mark_message_copied(self, message_id_value: int, stats: HistoryCopyStats, transfer_mode: str) -> None:
        self._state_store.mark_copied(
            self._settings.source_chat_id,
            self._settings.dest_chat_id,
            message_id_value,
        )
        stats.copied_count += 1
        logger.info(
            "📄 已处理消息: source=%s message_id=%s mode=%s",
            self._settings.source_chat_id,
            message_id_value,
            transfer_mode,
        )
