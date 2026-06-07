"""Base validator protocol for configuration values."""

from abc import ABC, abstractmethod
from typing import Any


class Validator(ABC):
    """Base class for field validators."""

    @abstractmethod
    def validate(self, field_name: str, value: Any) -> None:
        """Validate a field value."""
        pass
