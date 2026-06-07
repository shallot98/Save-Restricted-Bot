"""WebDAV client wrapper for remote media storage."""

import logging
import os

from webdav3.client import Client
from webdav3.exceptions import WebDavException

logger = logging.getLogger(__name__)


class WebDAVClient:
    """WebDAV client wrapper."""

    def __init__(
        self,
        url: str,
        username: str,
        password: str,
        *legacy_args,
        base_path: str = "/telegram_media",
    ):
        if legacy_args:
            if len(legacy_args) > 1 or base_path != "/telegram_media":
                raise TypeError("WebDAVClient received conflicting base_path arguments")
            base_path = legacy_args[0]
        self.url = url
        self.username = username
        self.password = password
        self.base_path = base_path.rstrip("/")

        options = {
            "webdav_hostname": url,
            "webdav_login": username,
            "webdav_password": password,
            "webdav_timeout": 30,
        }

        try:
            self.client = Client(options)
            self._ensure_base_path()
            logger.info(f"✅ WebDAV 客户端初始化成功: {url}")
        except Exception as e:
            logger.error(f"❌ WebDAV 客户端初始化失败: {e}")
            raise

    def _ensure_base_path(self):
        """Ensure the configured base path exists."""
        try:
            if not self.client.check(self.base_path):
                self.client.mkdir(self.base_path)
                logger.info(f"📁 创建 WebDAV 基础目录: {self.base_path}")
        except WebDavException as e:
            logger.warning(f"⚠️ 检查/创建基础路径失败: {e}")

    def upload_file(self, local_path: str, remote_filename: str) -> bool:
        """Upload a local file to WebDAV."""
        try:
            if not os.path.exists(local_path):
                logger.error(f"❌ 本地文件不存在: {local_path}")
                return False

            remote_path = f"{self.base_path}/{remote_filename}"
            self.client.upload_sync(remote_path=remote_path, local_path=local_path)

            file_size = os.path.getsize(local_path)
            logger.info(f"✅ 文件上传成功: {remote_filename} ({file_size} bytes)")
            return True
        except WebDavException as e:
            logger.error(f"❌ WebDAV 上传失败: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ 上传文件时出错: {e}", exc_info=True)
            return False

    def download_file(self, remote_filename: str, local_path: str) -> bool:
        """Download a remote WebDAV file."""
        try:
            remote_path = f"{self.base_path}/{remote_filename}"
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            self.client.download_sync(remote_path=remote_path, local_path=local_path)

            logger.info(f"✅ 文件下载成功: {remote_filename}")
            return True
        except WebDavException as e:
            logger.error(f"❌ WebDAV 下载失败: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ 下载文件时出错: {e}", exc_info=True)
            return False

    def file_exists(self, remote_filename: str) -> bool:
        """Return whether a remote file exists."""
        try:
            remote_path = f"{self.base_path}/{remote_filename}"
            return self.client.check(remote_path)
        except Exception as e:
            logger.error(f"❌ 检查文件存在性失败: {e}")
            return False

    def delete_file(self, remote_filename: str) -> bool:
        """Delete a remote file."""
        try:
            remote_path = f"{self.base_path}/{remote_filename}"

            if not self.client.check(remote_path):
                logger.warning(f"⚠️ 文件不存在，无需删除: {remote_filename}")
                return True

            self.client.clean(remote_path)
            logger.info(f"✅ 文件删除成功: {remote_filename}")
            return True
        except WebDavException as e:
            logger.error(f"❌ WebDAV 删除失败: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ 删除文件时出错: {e}", exc_info=True)
            return False

    def get_file_url(self, remote_filename: str) -> str:
        """Return the full WebDAV URL for a stored file."""
        return f"{self.url.rstrip('/')}{self.base_path}/{remote_filename}"

    def test_connection(self) -> bool:
        """Test whether the WebDAV connection works."""
        try:
            self.client.list(self.base_path)
            logger.info("✅ WebDAV 连接测试成功")
            return True
        except Exception as e:
            logger.error(f"❌ WebDAV 连接测试失败: {e}")
            return False
