"""
Common Interfaces Module
========================

Abstract base classes and protocols for dependency inversion.
"""

from src.core.interfaces.repository import Repository
from src.core.interfaces.service import Service
from src.core.interfaces.storage import StorageBackend

__all__ = [
    "Repository",
    "Service",
    "StorageBackend",
]
