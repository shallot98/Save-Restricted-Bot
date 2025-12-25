"""
Custom Exceptions Module
========================

Centralized exception definitions for the application.
"""

from src.core.exceptions.base import (
    AppException,
    ConfigurationError,
    ValidationError,
    NotFoundError,
    AuthorizationError,
    ExternalServiceError,
    RateLimitError,
    StorageError,
    DatabaseError,
)

__all__ = [
    "AppException",
    "ConfigurationError",
    "ValidationError",
    "NotFoundError",
    "AuthorizationError",
    "ExternalServiceError",
    "RateLimitError",
    "StorageError",
    "DatabaseError",
]
