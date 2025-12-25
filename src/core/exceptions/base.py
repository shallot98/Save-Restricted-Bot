"""
Base Exception Classes
======================

Hierarchical exception structure for the application.
"""

from typing import Optional, Any, Dict


class AppException(Exception):
    """
    Base exception for all application exceptions

    Attributes:
        message: Human-readable error message
        code: Error code for programmatic handling
        details: Additional error details
    """

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__
        self.details = details or {}

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses"""
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details
        }


# ==================== Configuration Exceptions ====================

class ConfigurationError(AppException):
    """Raised when configuration is invalid or missing"""

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        **kwargs
    ) -> None:
        details = kwargs.pop("details", {})
        if config_key:
            details["config_key"] = config_key
        super().__init__(message, details=details, **kwargs)


# ==================== Validation Exceptions ====================

class ValidationError(AppException):
    """Raised when input validation fails"""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        **kwargs
    ) -> None:
        details = kwargs.pop("details", {})
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)
        super().__init__(message, details=details, **kwargs)


# ==================== Resource Exceptions ====================

class NotFoundError(AppException):
    """Raised when a requested resource is not found"""

    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[Any] = None,
        **kwargs
    ) -> None:
        details = kwargs.pop("details", {})
        if resource_type:
            details["resource_type"] = resource_type
        if resource_id is not None:
            details["resource_id"] = str(resource_id)
        super().__init__(message, details=details, **kwargs)


class AuthorizationError(AppException):
    """Raised when user is not authorized to perform an action"""

    def __init__(
        self,
        message: str = "Unauthorized access",
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        **kwargs
    ) -> None:
        details = kwargs.pop("details", {})
        if user_id:
            details["user_id"] = user_id
        if action:
            details["action"] = action
        super().__init__(message, details=details, **kwargs)


# ==================== External Service Exceptions ====================

class ExternalServiceError(AppException):
    """Raised when an external service call fails"""

    def __init__(
        self,
        message: str,
        service_name: Optional[str] = None,
        status_code: Optional[int] = None,
        **kwargs
    ) -> None:
        details = kwargs.pop("details", {})
        if service_name:
            details["service"] = service_name
        if status_code:
            details["status_code"] = status_code
        super().__init__(message, details=details, **kwargs)


class RateLimitError(ExternalServiceError):
    """Raised when rate limit is exceeded"""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        **kwargs
    ) -> None:
        details = kwargs.pop("details", {})
        if retry_after:
            details["retry_after"] = retry_after
        super().__init__(message, details=details, **kwargs)


# ==================== Storage Exceptions ====================

class StorageError(AppException):
    """Raised when storage operation fails"""

    def __init__(
        self,
        message: str,
        storage_type: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs
    ) -> None:
        details = kwargs.pop("details", {})
        if storage_type:
            details["storage_type"] = storage_type
        if operation:
            details["operation"] = operation
        super().__init__(message, details=details, **kwargs)


class DatabaseError(StorageError):
    """Raised when database operation fails"""

    def __init__(
        self,
        message: str,
        query: Optional[str] = None,
        **kwargs
    ) -> None:
        kwargs.setdefault("storage_type", "database")
        details = kwargs.pop("details", {})
        if query:
            details["query"] = query[:200]  # Truncate for safety
        super().__init__(message, details=details, **kwargs)
