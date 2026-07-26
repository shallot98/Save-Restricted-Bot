"""
Media handling helpers for MessageWorker record mode.

Keeps Telegram media download and storage decisions out of the queue worker
loop and forwarding flow.
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.core.config import settings
from src.core.utils.datetime_utils import DB_TIMEZONE
from bot.storage.webdav_client import StorageManager, WebDAVClient
from constants import MAX_MEDIA_PER_GROUP

logger = logging.getLogger(__name__)

# 直取权威源（原为 src.compat.config_compat.MEDIA_DIR，Phase 3 已删该包）。
# 保持 import 期快照语义：settings.paths.media_dir 每次访问都重读 DATA_DIR 环境
# 变量，而本模块的存储根目录在进程内必须恒定。
MEDIA_DIR = str(settings.paths.media_dir)

# Alias: the storage timezone is defined once in datetime_utils so that writers
# and time-window queries cannot drift onto different bases.
CHINA_TZ = DB_TIMEZONE


@dataclass(frozen=True)
class MediaGroupThumbnailRequest:
    msg: object
    idx: int
    timestamp: str
    keep_local: bool
    media_type: Optional[str]
    kind: str


@dataclass(frozen=True)
class MediaGroupItemRequest:
    msg: object
    idx: int
    keep_local: bool
    media_type: Optional[str]


@dataclass(frozen=True)
class SavedMediaPathRequest:
    idx: int
    saved: bool
    storage_location: Optional[str]
    media_path: Optional[str]


@dataclass(frozen=True)
class SingleThumbnailRequest:
    message: object
    attr_name: str
    label: str
    suffix: str


class MediaHandlingMixin:
    """Provide media download and record-mode storage helpers."""

    def _init_storage_manager(self) -> StorageManager:
        """初始化存储管理器"""
        try:
            webdav_config = settings.webdav_config
            if not webdav_config.get('enabled', False):
                logger.info("📁 使用本地存储模式")
                return StorageManager(MEDIA_DIR)

            url = webdav_config.get('url', '').strip()
            username = webdav_config.get('username', '').strip()
            password = webdav_config.get('password', '').strip()
            base_path = webdav_config.get('base_path', '/telegram_media')
            if not (url and username and password):
                logger.warning("⚠️ WebDAV 配置不完整，使用本地存储")
                logger.info("📁 使用本地存储模式")
                return StorageManager(MEDIA_DIR)

            try:
                webdav_client = WebDAVClient(url, username, password, base_path)
                if webdav_client.test_connection():
                    logger.info("✅ WebDAV 存储已启用")
                    return StorageManager(MEDIA_DIR, webdav_client)
                logger.warning("⚠️ WebDAV 连接测试失败，降级到本地存储")
            except Exception as e:
                logger.error(f"❌ WebDAV 初始化失败: {e}，降级到本地存储")
            logger.info("📁 使用本地存储模式")
            return StorageManager(MEDIA_DIR)
        except Exception as e:
            logger.error(f"❌ 存储管理器初始化失败: {e}，使用本地存储")
            return StorageManager(MEDIA_DIR)

    def _download_and_save_media(self, file_id: str, file_name: str, keep_local: bool) -> tuple[bool, Optional[str]]:
        """下载并保存单个媒体文件"""
        file_path = os.path.join(MEDIA_DIR, file_name)
        try:
            self.acc.download_media(file_id, file_name=file_path)
            return self.storage_manager.save_file(file_path, file_name, keep_local=keep_local)
        except Exception as e:
            logger.error(f"      ❌ 下载媒体失败: {e}")
            return False, None

    def _process_single_media_in_group(
        self,
        request: MediaGroupItemRequest,
    ) -> tuple[Optional[str], bool, Optional[str]]:
        """处理媒体组中的单个媒体"""
        timestamp = datetime.now(CHINA_TZ).strftime('%Y%m%d_%H%M%S')
        msg = request.msg

        if msg.photo:
            file_name = f"{msg.id}_{request.idx}_{timestamp}.jpg"
            success, location = self._download_and_save_media(
                msg.photo.file_id,
                file_name,
                request.keep_local,
            )
            if success:
                logger.debug(f"      ✅ 保存图片: {file_name}")
            return "photo", success, location

        if msg.video:
            return self._process_media_group_thumbnail(
                MediaGroupThumbnailRequest(
                    msg=msg,
                    idx=request.idx,
                    timestamp=timestamp,
                    keep_local=request.keep_local,
                    media_type=request.media_type,
                    kind="video",
                )
            )

        if msg.animation:
            return self._process_media_group_thumbnail(
                MediaGroupThumbnailRequest(
                    msg=msg,
                    idx=request.idx,
                    timestamp=timestamp,
                    keep_local=request.keep_local,
                    media_type=request.media_type,
                    kind="animation",
                )
            )

        return request.media_type, False, None

    def _process_media_group_thumbnail(
        self,
        request: MediaGroupThumbnailRequest,
    ) -> tuple[Optional[str], bool, Optional[str]]:
        new_type = request.media_type or request.kind
        media_obj = getattr(request.msg, request.kind)
        if not media_obj.thumbs:
            return new_type, False, None

        suffix = "gif_thumb" if request.kind == "animation" else "thumb"
        thumb = media_obj.thumbs[-1]
        file_name = f"{request.msg.id}_{request.idx}_{suffix}_{request.timestamp}.jpg"
        success, location = self._download_and_save_media(thumb.file_id, file_name, request.keep_local)
        if success:
            label = "GIF缩略图" if request.kind == "animation" else "视频缩略图"
            logger.debug(f"      ✅ 保存{label}: {file_name}")
        return new_type, success, location

    def _handle_media_group(self, message, content_to_save):
        """Handle media group download"""
        media_type = None
        media_path = None
        media_paths = []
        keep_local = settings.webdav_config.get('keep_local_copy', False)

        try:
            media_group = self.acc.get_media_group(message.chat.id, message.id)
            if not media_group:
                raise Exception("无法获取媒体组")

            logger.info(f"   📷 发现媒体组，共 {len(media_group)} 个媒体")
            for idx, msg in enumerate(media_group):
                media_type, saved, storage_location = self._process_single_media_in_group(
                    MediaGroupItemRequest(
                        msg=msg,
                        idx=idx,
                        keep_local=keep_local,
                        media_type=media_type,
                    )
                )
                if saved and storage_location:
                    media_paths.append(storage_location)
                media_path = self._resolve_saved_media_path(
                    SavedMediaPathRequest(
                        idx=idx,
                        saved=saved,
                        storage_location=storage_location,
                        media_path=media_path,
                    )
                )

                if len(media_paths) >= MAX_MEDIA_PER_GROUP:
                    logger.warning(f"   ⚠️ 媒体组超过{MAX_MEDIA_PER_GROUP}个，仅保存前{MAX_MEDIA_PER_GROUP}个")
                    break

                if msg.caption and not content_to_save:
                    content_to_save = msg.caption

            logger.info(f"   ✅ 媒体组处理完成，共保存 {len(media_paths)} 个文件")

        except Exception as e:
            logger.error(f"   ❌ 获取媒体组失败: {e}", exc_info=True)
            if message.photo:
                media_type, media_path, media_paths = self._handle_single_photo(message)

        return media_type, media_path, media_paths, content_to_save

    @staticmethod
    def _resolve_saved_media_path(
        request: SavedMediaPathRequest,
    ) -> Optional[str]:
        if request.saved and request.storage_location:
            return request.storage_location if request.idx == 0 else request.media_path
        logger.warning(f"      ⚠️ 媒体 {request.idx + 1} 类型不支持或无缩略图")
        return request.media_path

    def _handle_single_photo(self, message):
        """Handle single photo download"""
        logger.info("   📷 处理单张图片")
        file_name = f"{message.id}_{datetime.now(CHINA_TZ).strftime('%Y%m%d_%H%M%S')}.jpg"
        file_path = os.path.join(MEDIA_DIR, file_name)

        self.acc.download_media(message.photo.file_id, file_name=file_path)
        success, storage_location = self.storage_manager.save_file(
            file_path,
            file_name,
            keep_local=settings.webdav_config.get('keep_local_copy', False),
        )
        if success:
            return "photo", storage_location, [storage_location]

        logger.warning(f"⚠️ 存储失败，使用本地路径: {file_name}")
        return "photo", file_name, [file_name]

    def _handle_single_video(self, message):
        """Handle single video thumbnail download"""
        return self._handle_single_thumbnail(
            SingleThumbnailRequest(
                message=message,
                attr_name="video",
                label="视频",
                suffix="thumb",
            )
        )

    def _handle_single_animation(self, message):
        """Handle single GIF animation thumbnail download"""
        return self._handle_single_thumbnail(
            SingleThumbnailRequest(
                message=message,
                attr_name="animation",
                label="GIF动图",
                suffix="gif_thumb",
            )
        )

    def _handle_single_thumbnail(self, request: SingleThumbnailRequest):
        logger.info(f"   📹 处理{request.label}消息")
        media_path = None
        media_paths = []

        try:
            media_obj = getattr(request.message, request.attr_name)
            if media_obj.thumbs and len(media_obj.thumbs) > 0:
                media_path, media_paths = self._save_single_thumbnail(
                    request.message,
                    media_obj,
                    request.suffix,
                )
                logger.info(f"   ✅ {request.label}缩略图已保存")
            else:
                logger.warning(f"   ⚠️ {request.label}没有缩略图")
        except Exception as e:
            logger.warning(f"   ⚠️ 下载{request.label}缩略图失败: {e}")

        return request.attr_name, media_path, media_paths

    def _save_single_thumbnail(self, message, media_obj, suffix: str) -> tuple[Optional[str], list[str]]:
        thumb = media_obj.thumbs[-1]
        file_name = f"{message.id}_{datetime.now(CHINA_TZ).strftime('%Y%m%d_%H%M%S')}_{suffix}.jpg"
        file_path = os.path.join(MEDIA_DIR, file_name)

        self.acc.download_media(thumb.file_id, file_name=file_path)
        success, storage_location = self.storage_manager.save_file(
            file_path,
            file_name,
            keep_local=settings.webdav_config.get('keep_local_copy', False),
        )
        if success:
            return storage_location, [storage_location]

        media_path = f"local:{file_name}"
        return media_path, [media_path]
