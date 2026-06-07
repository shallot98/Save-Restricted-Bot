"""Message loading helpers for MessageWorker retries."""

import logging

from bot.workers.errors import RetryLater, UnrecoverableError

logger = logging.getLogger(__name__)


class MessageLoadingMixin:
    """Load or restore Telegram messages before processing."""

    def _ensure_message_loaded(self, msg_obj):
        """确保 msg_obj.message 可用于处理（重试时按需重新获取）。"""
        if msg_obj.message is not None:
            self._fill_text_from_existing_message(msg_obj)
            return msg_obj.message

        return self._fetch_missing_message(msg_obj)

    def _fill_text_from_existing_message(self, msg_obj) -> None:
        self._set_text_from_message_if_empty(msg_obj, msg_obj.message)
        if msg_obj.message_text or not self.acc:
            return
        if not getattr(msg_obj.message, "media_group_id", None):
            return

        chat_id = self._coerce_chat_id(msg_obj.source_chat_id)
        try:
            self._fill_text_from_media_group(msg_obj, chat_id)
        except RetryLater:
            raise
        except Exception as e:
            logger.debug(f"📸 获取媒体组文本失败: {e}")

    def _fetch_missing_message(self, msg_obj):
        if not self.acc:
            raise UnrecoverableError("User client 未初始化，无法重新获取消息")

        chat_id = self._coerce_chat_id(msg_obj.source_chat_id)
        self._warm_source_peer_cache(chat_id)
        fetched = self._execute_with_flood_retry(
            "重新获取消息",
            lambda: self.acc.get_messages(chat_id, msg_obj.message_id),
        )
        fetched = self._first_fetched_message(fetched)

        if not fetched:
            raise UnrecoverableError(f"无法重新获取消息: {msg_obj.source_chat_id}/{msg_obj.message_id}")

        msg_obj.message = fetched
        self._set_text_from_message_if_empty(msg_obj, fetched)
        if not msg_obj.message_text and getattr(fetched, "media_group_id", None):
            self._fill_text_from_media_group(msg_obj, chat_id)

        return fetched

    def _fill_text_from_media_group(self, msg_obj, chat_id) -> None:
        media_group = self._execute_with_flood_retry(
            "获取媒体组文本",
            lambda: self.acc.get_media_group(chat_id, msg_obj.message_id),
        )
        if not media_group:
            return

        first = media_group[0]
        msg_obj.message_text = first.text or first.caption or ""

    @staticmethod
    def _set_text_from_message_if_empty(msg_obj, message) -> None:
        if msg_obj.message_text:
            return
        msg_obj.message_text = message.text or message.caption or ""

    @staticmethod
    def _first_fetched_message(fetched):
        if isinstance(fetched, list):
            return fetched[0] if fetched else None
        return fetched

    def _warm_source_peer_cache(self, chat_id) -> None:
        try:
            from bot.services.peer_cache import cache_peer_if_needed

            if chat_id != "me":
                cache_peer_if_needed(self.acc, chat_id, "源频道")
        except Exception as e:
            logger.debug(f"源频道 Peer 缓存预热失败（忽略，不影响主流程）: {e}")
