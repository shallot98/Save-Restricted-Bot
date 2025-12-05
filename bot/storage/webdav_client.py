"""
WebDAV Client and Storage Manager for cloud storage support
"""

import os
import requests
from typing import Optional


class WebDAVClient:
    """Simple WebDAV client for cloud storage"""
    
    def __init__(self, url: str, username: str, password: str, base_path: str = '/telegram_media'):
        self.url = url.rstrip('/')
        self.username = username
        self.password = password
        self.base_path = base_path.rstrip('/')
    
    def test_connection(self) -> bool:
        """Test WebDAV connection"""
        try:
            response = requests.request(
                'PROPFIND',
                f"{self.url}{self.base_path}",
                auth=(self.username, self.password),
                timeout=10
            )
            return response.status_code in [200, 207, 404]  # 404 means path doesn't exist but connection works
        except Exception:
            return False
    
    def upload_file(self, local_path: str, remote_path: str) -> bool:
        """Upload file to WebDAV"""
        try:
            with open(local_path, 'rb') as f:
                response = requests.put(
                    f"{self.url}{self.base_path}{remote_path}",
                    data=f,
                    auth=(self.username, self.password),
                    timeout=30
                )
            return response.status_code in [200, 201, 204]
        except Exception:
            return False
    
    def download_file(self, remote_path: str, local_path: str) -> bool:
        """Download file from WebDAV"""
        try:
            response = requests.get(
                f"{self.url}{self.base_path}{remote_path}",
                auth=(self.username, self.password),
                timeout=30,
                stream=True
            )
            if response.status_code == 200:
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                with open(local_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                return True
            return False
        except Exception:
            return False


class StorageManager:
    """Storage manager for handling local and cloud storage"""
    
    def __init__(self, media_dir: str, webdav_client: Optional[WebDAVClient] = None):
        self.media_dir = media_dir
        self.webdav_client = webdav_client
    
    def get_file_path(self, filename: str) -> Optional[str]:
        """Get file path (local or remote URL)"""
        local_path = os.path.join(self.media_dir, filename)
        
        if self.webdav_client and os.path.exists(local_path):
            # Return remote URL for WebDAV
            return f"{self.webdav_client.url}{self.webdav_client.base_path}/{filename}"
        elif os.path.exists(local_path):
            # Return local path
            return local_path
        
        return None
    
    def save_file(self, filename: str, content: bytes) -> bool:
        """Save file to storage"""
        local_path = os.path.join(self.media_dir, filename)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        try:
            with open(local_path, 'wb') as f:
                f.write(content)
            
            # If WebDAV is enabled, also upload to cloud
            if self.webdav_client:
                self.webdav_client.upload_file(local_path, filename)
            
            return True
        except Exception:
            return False