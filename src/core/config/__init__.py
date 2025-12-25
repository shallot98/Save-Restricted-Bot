"""
Configuration Management Module
===============================

Provides centralized configuration management with:
- Environment variable support
- JSON file persistence
- Thread-safe access
- Hot reload capability
- Pydantic-based type validation
"""

def _ensure_typing_extensions_sentinel() -> None:
    """
    Ensure `typing_extensions.Sentinel` exists for pydantic-core compatibility.

    Some environments ship an older `typing_extensions` missing `Sentinel`,
    which causes `pydantic_core` import to fail at runtime.
    """
    try:
        import typing_extensions

        if hasattr(typing_extensions, "Sentinel"):
            return

        class Sentinel:  # type: ignore[no-redef]
            __slots__ = ("name",)

            def __init__(self, name: str):
                self.name = name

            def __repr__(self) -> str:
                return self.name

        typing_extensions.Sentinel = Sentinel  # type: ignore[attr-defined]
    except Exception:
        # Best-effort: if patching fails, let the original import error surface.
        return


_ensure_typing_extensions_sentinel()

from src.core.config.settings import Settings, settings
from src.core.config.models import (
    PathConfig,
    MainConfig,
    WatchConfig,
    WebDAVConfig,
    ViewerConfig,
)
from src.core.config.manager import (
    ConfigManager,
    ConfigValidator,
    ConfigChangeCallback,
)

__all__ = [
    # Legacy settings (保持向后兼容)
    "Settings",
    "settings",
    # Configuration models (新配置模型)
    "PathConfig",
    "MainConfig",
    "WatchConfig",
    "WebDAVConfig",
    "ViewerConfig",
    # Configuration manager interface (配置管理器接口)
    "ConfigManager",
    "ConfigValidator",
    "ConfigChangeCallback",
]
