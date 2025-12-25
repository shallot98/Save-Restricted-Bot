"""
WebDAV Storage Backend
======================

WebDAV implementation of StorageBackend interface.
"""

import logging
from typing import Optional

from src.core.interfaces.storage import StorageBackend, StorageFile
from src.infrastructure.external.webdav.client import WebDAVClient

logger = logging.getLogger(__name__)


class WebDAVStorageBackend(StorageBackend):
    """WebDAV storage backend implementation"""

    def __init__(
        self,
        url: str,
        username: str,
        password: str,
        base_path: str = "/telegram_media"
    ):
        """
        Initialize WebDAV storage

        Args:
            url: WebDAV server URL
            username: Username
            password: Password
            base_path: Base path for storage
        """
        self.client = WebDAVClient(url, username, password, base_path)
        self.url = url
        self.base_path = base_path

        if not self.client.test_connection():
            raise ConnectionError(f"Cannot connect to WebDAV server: {url}")

        logger.info(f"WebDAV storage initialized: {url}{base_path}")

    async def save(self, path: str, content, content_type: Optional[str] = None) -> StorageFile:
        """Save file to WebDAV"""
        # For WebDAV, we need a local file path
        # This is a simplified implementation
        raise NotImplementedError("Use upload_file method for WebDAV")

    async def get(self, path: str):
        """Get file from WebDAV"""
        raise NotImplementedError("Use download_file method for WebDAV")

    async def delete(self, path: str) -> bool:
        """Delete file from WebDAV"""
        return self.client.delete_file(path)

    async def exists(self, path: str) -> bool:
        """Check if file exists"""
        return self.client.file_exists(path)

    async def list_files(self, directory: str):
        """List files in directory"""
        raise NotImplementedError("List files not implemented for WebDAV")

    async def get_url(self, path: str) -> Optional[str]:
        """Get file URL"""
        return self.client.get_file_url(path)

    def upload_file(self, local_path: str, remote_filename: str) -> bool:
        """Upload file to WebDAV (sync method)"""
        return self.client.upload_file(local_path, remote_filename)

    def download_file(self, remote_filename: str, local_path: str) -> bool:
        """Download file from WebDAV (sync method)"""
        return self.client.download_file(remote_filename, local_path)
