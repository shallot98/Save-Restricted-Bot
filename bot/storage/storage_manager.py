"""Storage manager for local and WebDAV-backed media files."""

import logging
import os
import re
import shutil
from typing import Optional

from bot.storage.webdav_remote import WebDAVClient

logger = logging.getLogger(__name__)


class StorageManager:
    """Manage local and optional WebDAV storage."""

    _SAFE_FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,255}$")

    def __init__(self, local_dir: str, webdav_client: Optional[WebDAVClient] = None):
        self.local_dir = local_dir
        self.webdav_client = webdav_client
        self.use_webdav = webdav_client is not None

        os.makedirs(local_dir, exist_ok=True)

        if self.use_webdav:
            logger.info("📦 存储管理器：WebDAV 模式已启用")
        else:
            logger.info("📦 存储管理器：仅使用本地存储")

    @classmethod
    def _sanitize_filename(cls, filename: str) -> Optional[str]:
        """Validate a flat, safe filename."""
        if not filename:
            return None

        if filename != filename.strip():
            return None

        if "/" in filename or "\\" in filename:
            return None

        if ".." in filename:
            return None

        if not cls._SAFE_FILENAME_RE.fullmatch(filename):
            return None

        return filename

    def _parse_storage_location(self, storage_location: str) -> Optional[tuple[str, str]]:
        """Parse local/webdav storage location identifiers."""
        if not storage_location:
            return None

        storage_location = storage_location.strip()
        if not storage_location:
            return None

        if ":" in storage_location:
            storage_type, filename = storage_location.split(":", 1)
            storage_type = storage_type.strip().lower()
        else:
            storage_type, filename = "local", storage_location

        safe_filename = self._sanitize_filename(filename.strip())
        if safe_filename is None:
            logger.warning(f"⚠️ 非法文件名，已拒绝: {filename.strip()}")
            return None

        if storage_type not in {"local", "webdav"}:
            logger.warning(f"⚠️ 未知的存储类型: {storage_type}")
            return None

        return storage_type, safe_filename

    def _get_local_path(self, filename: str) -> Optional[str]:
        """Return a safe absolute local path within local_dir."""
        safe_filename = self._sanitize_filename(filename)
        if safe_filename is None:
            return None

        local_root = os.path.abspath(self.local_dir)
        full_path = os.path.abspath(os.path.join(self.local_dir, safe_filename))

        try:
            if os.path.commonpath([local_root, full_path]) != local_root:
                logger.warning(f"⚠️ 非法路径访问已拒绝: {filename}")
                return None
        except ValueError:
            logger.warning(f"⚠️ 非法路径访问已拒绝: {filename}")
            return None

        return full_path

    def save_file(self, local_path: str, filename: str, keep_local: bool = False) -> tuple[bool, str]:
        """Save a file locally or to WebDAV according to current configuration."""
        try:
            safe_filename = self._sanitize_filename(filename)
            if safe_filename is None:
                logger.error(f"❌ 非法文件名，拒绝保存: {filename}")
                return False, ""

            if self.use_webdav:
                return self._save_webdav(local_path, safe_filename, keep_local)

            return self._save_local(local_path, safe_filename)
        except Exception as e:
            logger.error(f"❌ 保存文件失败: {e}", exc_info=True)
            return False, ""

    def _save_webdav(self, local_path: str, filename: str, keep_local: bool) -> tuple[bool, str]:
        success = self.webdav_client.upload_file(local_path, filename)

        if not success:
            logger.warning(f"⚠️ WebDAV 上传失败，降级到本地存储: {filename}")
            return self._save_local(local_path, filename)

        if not keep_local and os.path.exists(local_path):
            try:
                os.remove(local_path)
                logger.debug(f"🗑️ 已删除本地临时文件: {filename}")
            except Exception as e:
                logger.warning(f"⚠️ 删除临时文件失败: {e}")

        return True, f"webdav:{filename}"

    def _save_local(self, local_path: str, filename: str) -> tuple[bool, str]:
        """Save a file to local storage."""
        try:
            target_path = self._get_local_path(filename)
            if not target_path:
                logger.error(f"❌ 非法文件名，无法保存到本地: {filename}")
                return False, ""

            if os.path.abspath(local_path) != os.path.abspath(target_path):
                shutil.copy2(local_path, target_path)

            logger.info(f"✅ 文件已保存到本地: {filename}")
            return True, f"local:{filename}"
        except Exception as e:
            logger.error(f"❌ 本地保存失败: {e}", exc_info=True)
            return False, ""

    def get_file_path(self, storage_location: str) -> Optional[str]:
        """Return the local path or WebDAV URL for a storage location."""
        try:
            parsed = self._parse_storage_location(storage_location)
            if not parsed:
                return None

            storage_type, filename = parsed
            if storage_type == "local":
                return self._get_local_path(filename)

            if storage_type == "webdav":
                if not self.webdav_client:
                    logger.warning(f"⚠️ WebDAV 客户端未配置，无法获取 URL: {filename}")
                    return None
                return self.webdav_client.get_file_url(filename)

            return None
        except Exception as e:
            logger.error(f"❌ 获取文件路径失败: {e}")
            return None

    def delete_file(self, storage_location: str) -> bool:
        """Delete a local or WebDAV file by storage location."""
        try:
            parsed = self._parse_storage_location(storage_location)
            if not parsed:
                return False

            storage_type, filename = parsed
            if storage_type == "local":
                return self._delete_local(filename)

            if storage_type == "webdav":
                return self._delete_webdav(filename)

            return False
        except Exception as e:
            logger.error(f"❌ 删除文件失败: {e}", exc_info=True)
            return False

    def _delete_local(self, filename: str) -> bool:
        local_path = self._get_local_path(filename)
        if not local_path:
            return False

        if os.path.exists(local_path):
            os.remove(local_path)
            logger.info(f"✅ 本地文件已删除: {filename}")
        return True

    def _delete_webdav(self, filename: str) -> bool:
        if not self.webdav_client:
            logger.warning(f"⚠️ WebDAV 客户端未配置: {filename}")
            return False
        return self.webdav_client.delete_file(filename)
