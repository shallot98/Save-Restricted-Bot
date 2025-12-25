"""
Core Layer - Shared Foundations
===============================

Contains:
- config/     Configuration management
- constants/  Application constants
- exceptions/ Custom exceptions
- interfaces/ Common interfaces
- utils/      Utility functions
- container   Service container for DI
"""

from typing import Any


__all__ = ["settings", "AppConstants", "get_container", "get_note_service", "get_watch_service", "get_calibration_service"]


def __getattr__(name: str) -> Any:
    """
    Lazy attribute access to avoid importing heavy config dependencies at import time.

    This keeps `import src.core` lightweight so submodules like `src.core.exceptions`
    can be imported in isolation (e.g., during unit tests).
    """
    if name == "settings":
        from src.core.config import settings
        return settings
    if name == "AppConstants":
        from src.core.constants import AppConstants
        return AppConstants
    if name in {"get_container", "get_note_service", "get_watch_service", "get_calibration_service"}:
        from src.core.container import (
            get_container,
            get_note_service,
            get_watch_service,
            get_calibration_service,
        )
        return {
            "get_container": get_container,
            "get_note_service": get_note_service,
            "get_watch_service": get_watch_service,
            "get_calibration_service": get_calibration_service,
        }[name]
    raise AttributeError(name)
