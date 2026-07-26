"""
Storage Interface
=================

Abstract interface for storage backends.
Supports local filesystem, WebDAV, and other storage types.
"""

from abc import ABC, abstractmethod
from typing import (
    BinaryIO,
    Callable,
    List,
    Optional,
    Protocol,
    runtime_checkable,
)
from dataclasses import dataclass


@runtime_checkable
class MediaStorage(Protocol):
    """
    Narrow port for note media deletion.

    `src.application` 删除笔记时只需要「按存储位置删文件」这一个动作；
    具体实现是 `bot/storage/storage_manager.py:StorageManager`（本地 + WebDAV），
    由组合根 `composition/wiring.py` 装配注入。
    """

    def delete_file(self, storage_location: str) -> bool:
        """Delete a stored media file. Returns True when removed."""
        ...


#: 组合根注入的惰性提供者：未装配时返回 None，调用方必须显式处理。
MediaStorageProvider = Callable[[], Optional[MediaStorage]]


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
