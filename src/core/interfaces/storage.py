"""
Storage Interface
=================

Abstract interface for storage backends.
Supports local filesystem, WebDAV, and other storage types.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, BinaryIO, List
from dataclasses import dataclass


@dataclass
class StorageFile:
    """Represents a file in storage"""

    path: str
    name: str
    size: int
    content_type: Optional[str] = None
    modified_at: Optional[float] = None


class StorageBackend(ABC):
    """
    Abstract storage backend interface

    Implementations:
    - LocalStorage: Local filesystem
    - WebDAVStorage: WebDAV remote storage
    """

    @abstractmethod
    async def save(
        self,
        path: str,
        content: BinaryIO,
        content_type: Optional[str] = None
    ) -> StorageFile:
        """
        Save file to storage

        Args:
            path: Destination path
            content: File content stream
            content_type: MIME type

        Returns:
            StorageFile with saved file info
        """
        pass

    @abstractmethod
    async def get(self, path: str) -> Optional[BinaryIO]:
        """
        Get file from storage

        Args:
            path: File path

        Returns:
            File content stream or None if not found
        """
        pass

    @abstractmethod
    async def delete(self, path: str) -> bool:
        """
        Delete file from storage

        Args:
            path: File path

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """
        Check if file exists

        Args:
            path: File path

        Returns:
            True if exists
        """
        pass

    @abstractmethod
    async def list_files(self, directory: str) -> List[StorageFile]:
        """
        List files in directory

        Args:
            directory: Directory path

        Returns:
            List of files in directory
        """
        pass

    @abstractmethod
    async def get_url(self, path: str) -> Optional[str]:
        """
        Get public URL for file

        Args:
            path: File path

        Returns:
            Public URL or None if not available
        """
        pass
