"""Forwarding helpers for MessageWorker."""

import logging
import time
from typing import Any, Dict, Optional

from bot.filters import extract_content
from bot.workers.errors import UnrecoverableError
from bot.workers.processing_models import ForwardChainContext, ForwardModeContext, ForwardSendContext
from constants import RATE_LIMIT_DELAY

logger = logging.getLogger(__name__)


class ForwardingMixin:
    """Provide forward/copy behavior for MessageWorker."""

    def _handle_forward_mode(
        self,
        context: Optional[ForwardModeContext] = None,
        **legacy_kwargs,
    ):
        """Handle forward mode processing."""
        context = _forward_mode_context(context, legacy_kwargs)
        logger.info(f"📤 转发模式：开始处理，目标: {context.dest_chat_id}")

        if not context.dest_chat_id:
            raise UnrecoverableError("目标频道为空，无法转发")

        current_chain = self._build_chain_context(context.message, context.chain_context)
        if self._should_stop_chain(context.dest_chat_id, current_chain):
            return "success"

        if context.dest_chat_id != "me" and not self._ensure_peer_cached(str(context.dest_chat_id)):
            raise UnrecoverableError(f"目标 Peer 缓存失败: {context.dest_chat_id}")

        forwarded_message_id = self._send_forwarded_message(
            ForwardSendContext(
                message=context.message,
                dest_chat_id=context.dest_chat_id,
                message_text=context.message_text,
                forward_mode=context.forward_mode,
                extract_patterns=context.extract_patterns,
                preserve_forward_source=context.preserve_forward_source,
            )
        )
        self._message_service.record_forward(
            success=True,
            preserve_source=bool(context.preserve_forward_source),
        )
        self._trigger_forward_chain(
            ForwardChainContext(
                record_mode=context.record_mode,
                dest_chat_id=context.dest_chat_id,
                forwarded_message_id=forwarded_message_id,
                message_text=context.message_text,
                current_chain=current_chain,
            )
        )
        return "success"

    def _send_forwarded_message(self, context: ForwardSendContext):
        try:
            if context.forward_mode == "extract" and context.extract_patterns:
                return self._send_extracted_text(
                    context.dest_chat_id,
                    context.message_text,
                    context.extract_patterns,
                )

            dest_id = "me" if context.dest_chat_id == "me" else int(context.dest_chat_id)
            if context.preserve_forward_source:
                return self._forward_with_source(context.message, dest_id)
            return self._copy_without_source(context.message, dest_id)
        except Exception as e:
            self._message_service.record_forward(
                success=False,
                preserve_source=bool(context.preserve_forward_source),
                error_type=type(e).__name__,
            )
            raise

    def _send_extracted_text(self, dest_chat_id, message_text, extract_patterns):
        extracted_text = extract_content(message_text, extract_patterns)
        if not extracted_text:
            logger.debug("   未提取到任何内容，跳过发送")
            return None

        logger.info("   提取到内容，准备发送")
        dest_id = "me" if dest_chat_id == "me" else int(dest_chat_id)
        sent_msg = self._execute_with_flood_retry(
            "发送提取内容",
            lambda: self.acc.send_message(dest_id, extracted_text),
        )
        logger.info("   ✅ 提取内容已发送")
        time.sleep(RATE_LIMIT_DELAY)
        return sent_msg.id if sent_msg and hasattr(sent_msg, "id") else None

    def _trigger_forward_chain(self, context: ForwardChainContext) -> None:
        if (
            context.record_mode
            or not context.dest_chat_id
            or context.dest_chat_id == "me"
            or not context.forwarded_message_id
        ):
            return

        next_chain = {
            "depth": int(context.current_chain["depth"]) + 1,
            "max_hops": int(context.current_chain["max_hops"]),
            "visited": set(context.current_chain["visited"]) | {str(context.dest_chat_id)},
        }
        self._trigger_dest_monitoring(
            context.dest_chat_id,
            context.forwarded_message_id,
            context.message_text,
            chain_context=next_chain,
        )

    def _forward_with_source(self, message, dest_id):
        """Forward message preserving source."""
        logger.debug("   保留转发来源")
        if message.media_group_id:
            return self._forward_media_group_with_source(message, dest_id)

        result = self._execute_with_flood_retry(
            "转发消息",
            lambda: self.acc.forward_messages(dest_id, message.chat.id, message.id),
        )
        logger.info("   ✅ 消息已转发")
        time.sleep(RATE_LIMIT_DELAY)
        return self._first_forwarded_message_id(result)

    def _forward_media_group_with_source(self, message, dest_id):
        try:
            media_group = self.acc.get_media_group(message.chat.id, message.id)
            message_ids = [msg.id for msg in media_group] if media_group else [message.id]
            result = self._execute_with_flood_retry(
                "转发媒体组",
                lambda: self.acc.forward_messages(dest_id, message.chat.id, message_ids),
            )
            logger.info("   ✅ 媒体组已转发")
            time.sleep(RATE_LIMIT_DELAY)
            return self._first_forwarded_message_id(result)
        except UnrecoverableError:
            raise
        except Exception as e:
            logger.warning(f"   转发媒体组失败，回退到单条转发: {e}")
            result = self._execute_with_flood_retry(
                "转发单条消息",
                lambda: self.acc.forward_messages(dest_id, message.chat.id, message.id),
            )
            logger.info("   ✅ 消息已转发（单条）")
            time.sleep(RATE_LIMIT_DELAY)
            return self._first_forwarded_message_id(result)

    def _copy_without_source(self, message, dest_id):
        """Copy message hiding source."""
        logger.debug("   隐藏转发来源")
        if message.media_group_id:
            return self._copy_media_group_without_source(message, dest_id)

        result = self._execute_with_flood_retry(
            "复制消息",
            lambda: self.acc.copy_message(dest_id, message.chat.id, message.id),
        )
        logger.info("   ✅ 消息已复制")
        time.sleep(RATE_LIMIT_DELAY)
        return self._first_forwarded_message_id(result)

    def _copy_media_group_without_source(self, message, dest_id):
        try:
            result = self._execute_with_flood_retry(
                "复制媒体组",
                lambda: self.acc.copy_media_group(dest_id, message.chat.id, message.id),
            )
            logger.info("   ✅ 媒体组已复制（隐藏引用）")
            time.sleep(RATE_LIMIT_DELAY)
            return self._first_forwarded_message_id(result)
        except UnrecoverableError:
            raise
        except Exception as e:
            logger.warning(f"   复制媒体组失败，回退到复制单条: {e}")
            result = self._execute_with_flood_retry(
                "复制单条消息",
                lambda: self.acc.copy_message(dest_id, message.chat.id, message.id),
            )
            logger.info("   ✅ 消息已复制（单条）")
            time.sleep(RATE_LIMIT_DELAY)
            return self._first_forwarded_message_id(result)

    @staticmethod
    def _first_forwarded_message_id(result):
        if not result:
            return None
        if isinstance(result, list):
            if not result:
                return None
            first = result[0]
            return first.id if hasattr(first, "id") else first
        return result.id if hasattr(result, "id") else result


def _forward_mode_context(
    context: Optional[ForwardModeContext],
    legacy_kwargs: Dict[str, Any],
) -> ForwardModeContext:
    if context is not None:
        if legacy_kwargs:
            raise TypeError("_handle_forward_mode received both context and legacy keyword arguments")
        return context
    return ForwardModeContext(**legacy_kwargs)
