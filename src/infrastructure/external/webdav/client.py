"""
WebDAV Client
=============

WebDAV client for remote media storage.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class WebDAVClient:
    """WebDAV client wrapper"""

    def __init__(
        self,
        url: str,
        username: str,
        password: str,
        base_path: str = "/telegram_media"
    ):
        """
        Initialize WebDAV client

        Args:
            url: WebDAV server URL
            username: Username
            password: Password
            base_path: Base path for file storage
        """
        from webdav3.client import Client

        self.url = url
        self.username = username
        self.password = password
        self.base_path = base_path.rstrip('/')

        options = {
            'webdav_hostname': url,
            'webdav_login': username,
            'webdav_password': password,
            'webdav_timeout': 30,
        }

        try:
            self.client = Client(options)
            self._ensure_base_path()
            logger.info(f"WebDAV client initialized: {url}")
        except Exception as e:
            logger.error(f"WebDAV client initialization failed: {e}")
            raise

    def _ensure_base_path(self) -> None:
        """Ensure base path exists"""
        from webdav3.exceptions import WebDavException

        try:
            if not self.client.check(self.base_path):
                self.client.mkdir(self.base_path)
                logger.info(f"Created WebDAV base directory: {self.base_path}")
        except WebDavException as e:
            logger.warning(f"Failed to check/create base path: {e}")

    def upload_file(self, local_path: str, remote_filename: str) -> bool:
        """Upload file to WebDAV"""
        from webdav3.exceptions import WebDavException

        try:
            if not os.path.exists(local_path):
                logger.error(f"Local file not found: {local_path}")
                return False

            remote_path = f"{self.base_path}/{remote_filename}"
            self.client.upload_sync(remote_path=remote_path, local_path=local_path)

            file_size = os.path.getsize(local_path)
            logger.info(f"File uploaded: {remote_filename} ({file_size} bytes)")
            return True

        except WebDavException as e:
            logger.error(f"WebDAV upload failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Upload error: {e}", exc_info=True)
            return False

    def download_file(self, remote_filename: str, local_path: str) -> bool:
        """Download file from WebDAV"""
        from webdav3.exceptions import WebDavException

        try:
            remote_path = f"{self.base_path}/{remote_filename}"
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            self.client.download_sync(remote_path=remote_path, local_path=local_path)

            logger.info(f"File downloaded: {remote_filename}")
            return True

        except WebDavException as e:
            logger.error(f"WebDAV download failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Download error: {e}", exc_info=True)
            return False

    def file_exists(self, remote_filename: str) -> bool:
        """Check if file exists"""
        try:
            remote_path = f"{self.base_path}/{remote_filename}"
            return self.client.check(remote_path)
        except Exception as e:
            logger.error(f"File existence check failed: {e}")
            return False

    def delete_file(self, remote_filename: str) -> bool:
        """Delete remote file"""
        from webdav3.exceptions import WebDavException

        try:
            remote_path = f"{self.base_path}/{remote_filename}"

            if not self.client.check(remote_path):
                logger.warning(f"File not found, nothing to delete: {remote_filename}")
                return True

            self.client.clean(remote_path)
            logger.info(f"File deleted: {remote_filename}")
            return True

        except WebDavException as e:
            logger.error(f"WebDAV delete failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Delete error: {e}", exc_info=True)
            return False

    def get_file_url(self, remote_filename: str) -> str:
        """Get file WebDAV URL"""
        return f"{self.url.rstrip('/')}{self.base_path}/{remote_filename}"

    def test_connection(self) -> bool:
        """Test WebDAV connection"""
        try:
            self.client.list(self.base_path)
            logger.info("WebDAV connection test successful")
            return True
        except Exception as e:
            logger.error(f"WebDAV connection test failed: {e}")
            return False
