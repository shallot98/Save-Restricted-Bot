"""
WebDAV client for remote media storage
Supports uploading, downloading, and managing files on WebDAV servers
"""
import os
import logging
from typing import Optional, BinaryIO
from webdav3.client import Client
from webdav3.exceptions import WebDavException

logger = logging.getLogger(__name__)


class WebDAVClient:
    """WebDAV 客户端封装类"""

    def __init__(self, url: str, username: str, password: str, base_path: str = "/telegram_media"):
        """
        初始化 WebDAV 客户端

        Args:
            url: WebDAV 服务器地址 (如: https://dav.jianguoyun.com/dav/)
            username: 用户名
            password: 密码
            base_path: 基础路径，所有文件将存储在此路径下
        """
        self.url = url
        self.username = username
        self.password = password
        self.base_path = base_path.rstrip('/')

        # 配置 WebDAV 客户端
        options = {
            'webdav_hostname': url,
            'webdav_login': username,
            'webdav_password': password,
            'webdav_timeout': 30,
        }

        try:
            self.client = Client(options)
            self._ensure_base_path()
            logger.info(f"✅ WebDAV 客户端初始化成功: {url}")
        except Exception as e:
            logger.error(f"❌ WebDAV 客户端初始化失败: {e}")
            raise

    def _ensure_base_path(self):
        """确保基础路径存在"""
        try:
            if not self.client.check(self.base_path):
                self.client.mkdir(self.base_path)
                logger.info(f"📁 创建 WebDAV 基础目录: {self.base_path}")
        except WebDavException as e:
            logger.warning(f"⚠️ 检查/创建基础路径失败: {e}")

    def upload_file(self, local_path: str, remote_filename: str) -> bool:
        """
        上传文件到 WebDAV

        Args:
            local_path: 本地文件路径
            remote_filename: 远程文件名（不含路径）

        Returns:
            bool: 上传是否成功
        """
        try:
            if not os.path.exists(local_path):
                logger.error(f"❌ 本地文件不存在: {local_path}")
                return False

            remote_path = f"{self.base_path}/{remote_filename}"

            # 上传文件
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
        """
        从 WebDAV 下载文件

        Args:
            remote_filename: 远程文件名（不含路径）
            local_path: 本地保存路径

        Returns:
            bool: 下载是否成功
        """
        try:
            remote_path = f"{self.base_path}/{remote_filename}"

            # 确保本地目录存在
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            # 下载文件
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
        """
        检查文件是否存在

        Args:
            remote_filename: 远程文件名（不含路径）

        Returns:
            bool: 文件是否存在
        """
        try:
            remote_path = f"{self.base_path}/{remote_filename}"
            return self.client.check(remote_path)
        except Exception as e:
            logger.error(f"❌ 检查文件存在性失败: {e}")
            return False

    def delete_file(self, remote_filename: str) -> bool:
        """
        删除远程文件

        Args:
            remote_filename: 远程文件名（不含路径）

        Returns:
            bool: 删除是否成功
        """
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
        """
        获取文件的 WebDAV URL

        Args:
            remote_filename: 远程文件名（不含路径）

        Returns:
            str: 文件的完整 URL
        """
        return f"{self.url.rstrip('/')}{self.base_path}/{remote_filename}"

    def test_connection(self) -> bool:
        """
        测试 WebDAV 连接是否正常

        Returns:
            bool: 连接是否正常
        """
        try:
            # 尝试列出基础路径
            self.client.list(self.base_path)
            logger.info("✅ WebDAV 连接测试成功")
            return True
        except Exception as e:
            logger.error(f"❌ WebDAV 连接测试失败: {e}")
            return False


class StorageManager:
    """存储管理器，统一管理本地和 WebDAV 存储"""

    def __init__(self, local_dir: str, webdav_client: Optional[WebDAVClient] = None):
        """
        初始化存储管理器

        Args:
            local_dir: 本地存储目录
            webdav_client: WebDAV 客户端（可选）
        """
        self.local_dir = local_dir
        self.webdav_client = webdav_client
        self.use_webdav = webdav_client is not None

        # 确保本地目录存在
        os.makedirs(local_dir, exist_ok=True)

        if self.use_webdav:
            logger.info("📦 存储管理器：WebDAV 模式已启用")
        else:
            logger.info("📦 存储管理器：仅使用本地存储")

    def save_file(self, local_path: str, filename: str, keep_local: bool = False) -> tuple[bool, str]:
        """
        保存文件（根据配置选择本地或 WebDAV）

        Args:
            local_path: 本地临时文件路径
            filename: 文件名
            keep_local: 是否保留本地副本（WebDAV 模式下）

        Returns:
            tuple[bool, str]: (是否成功, 存储位置标识)
                存储位置标识: "local:filename" 或 "webdav:filename"
        """
        try:
            # WebDAV 模式
            if self.use_webdav:
                # 上传到 WebDAV
                success = self.webdav_client.upload_file(local_path, filename)

                if success:
                    # 如果不保留本地副本，删除临时文件
                    if not keep_local and os.path.exists(local_path):
                        try:
                            os.remove(local_path)
                            logger.debug(f"🗑️ 已删除本地临时文件: {filename}")
                        except Exception as e:
                            logger.warning(f"⚠️ 删除临时文件失败: {e}")

                    return True, f"webdav:{filename}"
                else:
                    # WebDAV 上传失败，降级到本地存储
                    logger.warning(f"⚠️ WebDAV 上传失败，降级到本地存储: {filename}")
                    return self._save_local(local_path, filename)

            # 本地存储模式
            else:
                return self._save_local(local_path, filename)

        except Exception as e:
            logger.error(f"❌ 保存文件失败: {e}", exc_info=True)
            return False, ""

    def _save_local(self, local_path: str, filename: str) -> tuple[bool, str]:
        """保存到本地存储"""
        try:
            target_path = os.path.join(self.local_dir, filename)

            # 如果源文件和目标文件不同，则复制
            if os.path.abspath(local_path) != os.path.abspath(target_path):
                import shutil
                shutil.copy2(local_path, target_path)

            logger.info(f"✅ 文件已保存到本地: {filename}")
            return True, f"local:{filename}"

        except Exception as e:
            logger.error(f"❌ 本地保存失败: {e}", exc_info=True)
            return False, ""

    def get_file_path(self, storage_location: str) -> Optional[str]:
        """
        获取文件路径或 URL

        Args:
            storage_location: 存储位置标识 ("local:filename" 或 "webdav:filename")

        Returns:
            str: 本地路径或 WebDAV URL
        """
        try:
            if not storage_location:
                return None

            # 兼容旧格式（没有前缀的视为本地文件）
            if ':' not in storage_location:
                return os.path.join(self.local_dir, storage_location)

            storage_type, filename = storage_location.split(':', 1)

            if storage_type == 'local':
                return os.path.join(self.local_dir, filename)
            elif storage_type == 'webdav':
                if self.webdav_client:
                    return self.webdav_client.get_file_url(filename)
                else:
                    logger.warning(f"⚠️ WebDAV 客户端未配置，无法获取 URL: {filename}")
                    return None
            else:
                logger.warning(f"⚠️ 未知的存储类型: {storage_type}")
                return None

        except Exception as e:
            logger.error(f"❌ 获取文件路径失败: {e}")
            return None

    def delete_file(self, storage_location: str) -> bool:
        """
        删除文件

        Args:
            storage_location: 存储位置标识

        Returns:
            bool: 是否成功
        """
        try:
            if not storage_location:
                return False

            # 兼容旧格式
            if ':' not in storage_location:
                local_path = os.path.join(self.local_dir, storage_location)
                if os.path.exists(local_path):
                    os.remove(local_path)
                    return True
                return False

            storage_type, filename = storage_location.split(':', 1)

            if storage_type == 'local':
                local_path = os.path.join(self.local_dir, filename)
                if os.path.exists(local_path):
                    os.remove(local_path)
                    logger.info(f"✅ 本地文件已删除: {filename}")
                return True

            elif storage_type == 'webdav':
                if self.webdav_client:
                    return self.webdav_client.delete_file(filename)
                else:
                    logger.warning(f"⚠️ WebDAV 客户端未配置: {filename}")
                    return False

            return False

        except Exception as e:
            logger.error(f"❌ 删除文件失败: {e}", exc_info=True)
            return False
