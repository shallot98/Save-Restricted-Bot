"""Media-group copy helpers for Telegram history copy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from bot.utils.logger import get_logger
from .history_copy_models import HistoryCopyStats
from .history_copy_utils import is_forward_restricted_error, message_id

logger = get_logger(__name__)


@dataclass(frozen=True)
class MediaGroupCopyContext:
    source_ref: str
    message_id_value: int
    pending_ids: list[int]
    stats: HistoryCopyStats


class HistoryCopyMediaGroupMixin:
    def _copy_media_group_entry(self, message, stats: HistoryCopyStats) -> None:
        try:
            media_group = list(
                self._execute_with_retry(
                    "获取媒体组",
                    lambda: self._client.get_media_group(message.chat.id, message.id),
                )
            )
        except Exception as exc:
            self._raise_if_fatal(exc, message.id)
            logger.warning("⚠️ 获取媒体组失败，回退到单条复制: id=%s error=%s", message.id, exc)
            self._copy_single_entry(message, stats)
            return

        pending_ids = self._get_pending_message_ids(media_group)
        if not pending_ids:
            self._copy_single_entry(message, stats)
            return
        if len(pending_ids) == len(media_group) and self._copy_media_group_direct(
            message.id,
            pending_ids,
            stats,
        ):
            return
        self._copy_media_group_individually(media_group, stats)

    def _copy_media_group_individually(self, media_group: Iterable, stats: HistoryCopyStats) -> None:
        for item in media_group:
            self._copy_single_entry(item, stats)
            self._report_progress(stats)

    def _get_pending_message_ids(self, media_group: Iterable) -> list[int]:
        pending_ids: list[int] = []
        for item in media_group:
            current_message_id = message_id(item)
            if current_message_id <= 0:
                continue
            if self._is_message_copied(current_message_id):
                continue
            pending_ids.append(current_message_id)
        return pending_ids

    def _is_message_copied(self, current_message_id: int) -> bool:
        return self._state_store.is_copied(
            self._settings.source_chat_id,
            self._settings.dest_chat_id,
            current_message_id,
        )

    def _copy_media_group_direct(
        self,
        message_id_value: int,
        pending_ids: list[int],
        stats: HistoryCopyStats,
    ) -> bool:
        if self._copy_media_group_via_bot(message_id_value, pending_ids, stats):
            return True
        return self._copy_media_group_via_user(message_id_value, pending_ids, stats)

    def _copy_media_group_via_bot(
        self,
        message_id_value: int,
        pending_ids: list[int],
        stats: HistoryCopyStats,
    ) -> bool:
        source_ref = self._public_source_ref()
        if self._bot_client is None or source_ref is None:
            return False
        context = MediaGroupCopyContext(source_ref, message_id_value, pending_ids, stats)
        try:
            self._execute_with_retry(
                "Bot 直拷媒体组",
                lambda: self._bot_client.copy_media_group(
                    int(self._settings.dest_chat_id),
                    source_ref,
                    message_id_value,
                ),
                is_outbound=True,
                success_units=len(pending_ids),
                skip_failure_record=self._skip_failure_record,
            )
        except Exception as exc:
            return self._copy_media_group_after_bot_failure(context, exc)
        self._mark_messages_copied(pending_ids, stats, "Bot 直拷媒体组")
        return True

    def _copy_media_group_after_bot_failure(self, context, exc):
        logger.warning(
            "⚠️ Bot 直拷媒体组失败，尝试 Bot 私聊中转: source_ref=%s id=%s error=%s: %s",
            context.source_ref,
            context.message_id_value,
            type(exc).__name__,
            exc,
        )
        return self._copy_media_group_via_bot_staging(context)

    def _copy_media_group_via_bot_staging(self, context) -> bool:
        if not self._can_use_bot_staging():
            return False
        staged_ids: list[int] = []
        try:
            staged_ids = self._stage_media_group_with_bot(
                context.source_ref,
                context.message_id_value,
                len(context.pending_ids),
            )
            self._copy_staged_media_group(staged_ids[0], len(context.pending_ids))
        except Exception as exc:
            logger.warning(
                "⚠️ Bot 中转直拷媒体组失败，回退到 User 直拷: id=%s error=%s: %s",
                context.message_id_value,
                type(exc).__name__,
                exc,
            )
            return False
        finally:
            self._delete_staged_messages(staged_ids)
        self._mark_messages_copied(context.pending_ids, context.stats, "Bot 中转直拷媒体组")
        return True

    def _stage_media_group_with_bot(self, source_ref: str, message_id_value: int, expected_count: int) -> list[int]:
        previous_staging_id = self._latest_bot_staging_message_id()
        self._execute_with_retry(
            "Bot 中转暂存媒体组",
            lambda: self._bot_client.copy_media_group(
                int(self._bot_staging_chat_id),
                source_ref,
                message_id_value,
            ),
            is_outbound=True,
            success_units=expected_count,
            skip_failure_record=self._skip_failure_record,
        )
        staged_ids = self._wait_for_user_staged_message_ids(previous_staging_id, expected_count)
        if not staged_ids:
            raise RuntimeError("Bot 中转媒体组未返回有效消息 ID")
        return staged_ids

    def _copy_staged_media_group(self, first_staged_id: int, expected_count: int) -> None:
        copied_messages = self._execute_with_retry(
            "Bot 中转直拷媒体组",
            lambda: self._client.copy_media_group(
                int(self._settings.dest_chat_id),
                self._bot_staging_source_ref,
                first_staged_id,
            ),
            is_outbound=True,
            success_units=expected_count,
            skip_failure_record=self._skip_failure_record,
        )
        self._verify_copy_result_target(copied_messages, "Bot 中转直拷媒体组")

    def _copy_media_group_via_user(
        self,
        message_id_value: int,
        pending_ids: list[int],
        stats: HistoryCopyStats,
    ) -> bool:
        try:
            self._execute_with_retry(
                "TG 直拷媒体组",
                lambda: self._client.copy_media_group(
                    int(self._settings.dest_chat_id),
                    int(self._settings.source_chat_id),
                    message_id_value,
                ),
                is_outbound=True,
                success_units=len(pending_ids),
                skip_failure_record=is_forward_restricted_error,
            )
        except Exception as exc:
            return self._handle_media_group_user_copy_error(message_id_value, exc)
        self._mark_messages_copied(pending_ids, stats, "TG 直拷媒体组")
        return True

    def _handle_media_group_user_copy_error(self, message_id_value: int, exc: Exception) -> bool:
        if is_forward_restricted_error(exc):
            logger.info(
                "🔒 媒体组受保护，回退到下载后重发: source=%s message_id=%s error=%s: %s",
                self._settings.source_chat_id,
                message_id_value,
                type(exc).__name__,
                exc,
            )
            return False
        self._raise_if_fatal(exc, message_id_value)
        logger.warning("⚠️ TG 直拷媒体组失败，回退到逐条处理: id=%s error=%s", message_id_value, exc)
        return False

    def _mark_messages_copied(
        self,
        message_ids: list[int],
        stats: HistoryCopyStats,
        transfer_mode: str,
    ) -> None:
        self._state_store.mark_copied_many(
            self._settings.source_chat_id,
            self._settings.dest_chat_id,
            message_ids,
        )
        stats.copied_count += len(message_ids)
        logger.info(
            "📦 已处理媒体组: source=%s count=%s mode=%s",
            self._settings.source_chat_id,
            len(message_ids),
            transfer_mode,
        )
