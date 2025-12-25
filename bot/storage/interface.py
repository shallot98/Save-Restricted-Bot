"""
存储层抽象接口

NOTE: This module now delegates to the new layered architecture.
      For new code, prefer using:
          from src.core.interfaces.storage import StorageBackend
          from src.infrastructure.external.webdav import WebDAVStorageBackend
"""

# Re-export from new architecture for backward compatibility
from src.core.interfaces.storage import StorageBackend, StorageFile

# Keep local implementations for backward compatibility
from abc import ABC, abstractmethod
from typing import Optional
from pathlib import Path
import logging
import shutil

logger = logging.getLogger(__name__)


class LocalStorageBackend(StorageBackend):
    """本地文件系统存储后端"""

    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"本地存储已初始化: {self.base_dir}")

    def save_file(self, file_path: str, destination: str) -> str:
        source = Path(file_path)
        dest = self.base_dir / destination
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        return str(dest.relative_to(self.base_dir))

    def get_file_url(self, storage_location: str) -> str:
        return str(self.base_dir / storage_location)

    def file_exists(self, storage_location: str) -> bool:
        return (self.base_dir / storage_location).exists()

    def delete_file(self, storage_location: str) -> bool:
        try:
            file_path = self.base_dir / storage_location
            if file_path.exists():
                file_path.unlink()
                return True
            return False
        except Exception as e:
            logger.error(f"删除文件失败: {e}")
            return False

    def get_storage_info(self) -> dict:
        total, used, free = shutil.disk_usage(self.base_dir)
        return {
            'type': 'local',
            'base_dir': str(self.base_dir),
            'total_gb': round(total / (1024**3), 2),
            'used_gb': round(used / (1024**3), 2),
            'free_gb': round(free / (1024**3), 2),
        }

    # Async interface implementation (sync wrappers)
    async def save(self, path, content, content_type=None):
        raise NotImplementedError("Use save_file for local storage")

    async def get(self, path):
        raise NotImplementedError("Use get_file_url for local storage")

    async def delete(self, path) -> bool:
        return self.delete_file(path)

    async def exists(self, path) -> bool:
        return self.file_exists(path)

    async def list_files(self, directory):
        return []

    async def get_url(self, path):
        return self.get_file_url(path)


class WebDAVStorageBackend(StorageBackend):
    """WebDAV存储后端"""

    def __init__(self, url: str, username: str, password: str, base_path: str = "/"):
        from bot.storage.webdav_client import WebDAVClient
        self.client = WebDAVClient(url, username, password, base_path)
        self.url = url
        self.base_path = base_path

        if not self.client.test_connection():
            raise ConnectionError(f"无法连接到WebDAV服务器: {url}")

    def save_file(self, file_path: str, destination: str) -> str:
        remote_path = f"{self.base_path.rstrip('/')}/{destination}"
        if not self.client.upload_file(file_path, remote_path):
            raise IOError(f"上传文件到WebDAV失败: {destination}")
        return destination

    def get_file_url(self, storage_location: str) -> str:
        return f"{self.url.rstrip('/')}{self.base_path.rstrip('/')}/{storage_location}"

    def file_exists(self, storage_location: str) -> bool:
        remote_path = f"{self.base_path.rstrip('/')}/{storage_location}"
        return self.client.file_exists(remote_path)

    def delete_file(self, storage_location: str) -> bool:
        remote_path = f"{self.base_path.rstrip('/')}/{storage_location}"
        return self.client.delete_file(remote_path)

    def get_storage_info(self) -> dict:
        return {
            'type': 'webdav',
            'url': self.url,
            'base_path': self.base_path,
            'connected': self.client.test_connection(),
        }

    async def save(self, path, content, content_type=None):
        raise NotImplementedError()

    async def get(self, path):
        raise NotImplementedError()

    async def delete(self, path) -> bool:
        return self.delete_file(path)

    async def exists(self, path) -> bool:
        return self.file_exists(path)

    async def list_files(self, directory):
        return []

    async def get_url(self, path):
        return self.get_file_url(path)


class HybridStorageBackend(StorageBackend):
    """混合存储后端"""

    def __init__(self, local: LocalStorageBackend, remote: Optional[StorageBackend] = None,
                 keep_local_copy: bool = True):
        self.local = local
        self.remote = remote
        self.keep_local_copy = keep_local_copy

    def save_file(self, file_path: str, destination: str) -> str:
        local_location = self.local.save_file(file_path, destination)

        if self.remote:
            try:
                self.remote.save_file(file_path, destination)
                if not self.keep_local_copy:
                    self.local.delete_file(local_location)
            except Exception as e:
                logger.warning(f"上传到远程存储失败: {e}")

        return local_location

    def get_file_url(self, storage_location: str) -> str:
        if self.remote and self.remote.file_exists(storage_location):
            return self.remote.get_file_url(storage_location)
        return self.local.get_file_url(storage_location)

    def file_exists(self, storage_location: str) -> bool:
        return (self.local.file_exists(storage_location) or
                (self.remote and self.remote.file_exists(storage_location)))

    def delete_file(self, storage_location: str) -> bool:
        local_deleted = self.local.delete_file(storage_location)
        remote_deleted = True
        if self.remote:
            try:
                remote_deleted = self.remote.delete_file(storage_location)
            except Exception:
                remote_deleted = False
        return local_deleted or remote_deleted

    def get_storage_info(self) -> dict:
        info = {'type': 'hybrid', 'local': self.local.get_storage_info()}
        if self.remote:
            info['remote'] = self.remote.get_storage_info()
        return info

    async def save(self, path, content, content_type=None):
        raise NotImplementedError()

    async def get(self, path):
        raise NotImplementedError()

    async def delete(self, path) -> bool:
        return self.delete_file(path)

    async def exists(self, path) -> bool:
        return self.file_exists(path)

    async def list_files(self, directory):
        return []

    async def get_url(self, path):
        return self.get_file_url(path)


__all__ = [
    "StorageBackend",
    "StorageFile",
    "LocalStorageBackend",
    "WebDAVStorageBackend",
    "HybridStorageBackend",
]
