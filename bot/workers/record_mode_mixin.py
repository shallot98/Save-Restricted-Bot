"""Record-mode helpers for MessageWorker."""

import logging

from src.core.exceptions import ValidationError
from bot.filters import extract_content
from bot.workers.processing_models import RecordModeContext, RecordSaveContext

try:
    from src.infrastructure.monitoring.performance.decorators import monitor_performance
except Exception:
    def monitor_performance(*args, **kwargs):
        def _decorator(fn):
            return fn
        return _decorator

logger = logging.getLogger(__name__)


class RecordModeMixin:
    """Provide record-mode note persistence behavior."""

    @monitor_performance("worker.handle_record_mode")
    def _handle_record_mode(self, context: RecordModeContext):
        """Handle record mode processing."""
        logger.info("📝 记录模式：开始处理消息")
        logger.info(
            f"   来源: {context.source_chat_id} "
            f"({getattr(context.message.chat, 'title', None) or getattr(context.message.chat, 'username', None)})"
        )
        source_name = context.message.chat.title or context.message.chat.username or context.source_chat_id
        content_to_save = self._extract_record_content(
            context.message_text,
            context.forward_mode,
            context.extract_patterns,
        )
        media_type, media_path, media_paths, content_to_save = self._collect_record_media(
            context.message,
            content_to_save,
        )
        save_context = RecordSaveContext(
            user_id=context.user_id,
            source_chat_id=context.source_chat_id,
            source_name=source_name,
            content_to_save=content_to_save,
            media_type=media_type,
            media_path=media_path,
            media_paths=media_paths,
            media_group_id=context.message.media_group_id,
        )
        self._log_record_save_attempt(save_context)
        return self._save_record_note(save_context)

    @staticmethod
    def _extract_record_content(message_text, forward_mode, extract_patterns):
        content_to_save = message_text
        logger.debug(f"   原始内容长度: {len(message_text)}")
        if forward_mode == "extract" and extract_patterns:
            return extract_content(message_text, extract_patterns)
        return content_to_save

    def _collect_record_media(self, message, content_to_save):
        media_type = None
        media_path = None
        media_paths = []

        logger.debug("   开始处理媒体")
        if message.media_group_id:
            return self._handle_media_group(message, content_to_save)
        if message.photo:
            media_type, media_path, media_paths = self._handle_single_photo(message)
        elif message.video:
            media_type, media_path, media_paths = self._handle_single_video(message)
        elif message.animation:
            media_type, media_path, media_paths = self._handle_single_animation(message)

        return media_type, media_path, media_paths, content_to_save

    @staticmethod
    def _log_record_save_attempt(context: RecordSaveContext) -> None:
        logger.info("💾 记录模式：准备保存笔记到数据库")
        logger.info(f"   - 用户ID: {context.user_id}")
        logger.info(f"   - 来源: {context.source_name} ({context.source_chat_id})")
        logger.info(
            f"   - 文本: {bool(context.content_to_save)} "
            f"({len(context.content_to_save) if context.content_to_save else 0} 字符)"
        )
        logger.info(f"   - 媒体类型: {context.media_type}")
        logger.info(f"   - 媒体数量: {len(context.media_paths)} 个")
        logger.info(f"   - 媒体组ID: {context.media_group_id if context.media_group_id else 'None'}")

    def _save_record_note(self, context: RecordSaveContext):
        try:
            note_id = self._message_service.save_recorded_note(
                user_id=context.user_id,
                source_chat_id=context.source_chat_id,
                source_name=context.source_name,
                content_to_save=context.content_to_save,
                media_type=context.media_type,
                media_path=context.media_path,
                media_paths=context.media_paths,
                media_group_id=str(context.media_group_id) if context.media_group_id else None,
            )
            logger.info(f"✅ 记录模式：笔记保存成功！笔记ID: {note_id}")
            self._message_service.record_note_saved(success=True, has_media=bool(context.media_type))
            return "success"
        except ValidationError as e:
            if "Duplicate" in str(e):
                logger.info("⏭️ 记录模式：检测到重复笔记，已跳过写入")
                return "success"
            raise
        except Exception as e:
            logger.error("❌ 记录模式：保存笔记失败！", exc_info=True)
            self._message_service.record_note_saved(
                success=False,
                has_media=bool(context.media_type),
                error_type=type(e).__name__,
            )
            raise
