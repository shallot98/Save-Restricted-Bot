"""Backward-compatible WebDAV storage exports."""

from bot.storage.storage_manager import StorageManager
from bot.storage.webdav_remote import WebDAVClient

__all__ = ["WebDAVClient", "StorageManager"]
