"""
Core Layer - Shared Foundations
===============================

Contains:
- config/     Configuration management
- constants/  Application constants
- exceptions/ Custom exceptions
- interfaces/ Common interfaces
- utils/      Utility functions

本层只放共享基础设施与纯抽象，不得依赖 `src.application` / `src.infrastructure`。
DI 容器已迁往组合根 `composition/container.py`（见其 docstring）；原先在此
re-export `get_container` 等工厂会把外层实现倒灌进最内层，且全仓无调用方。
"""

from typing import Any


__all__ = ["settings", "AppConstants"]


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
    raise AttributeError(name)
