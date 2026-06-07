"""Lazy exports for bot service modules."""

from __future__ import annotations

import importlib
from typing import Any, Dict, Tuple

__all__ = [
    "initialize_peer_cache_on_startup_with_retry",
    "cache_peer_if_needed",
    "import_watch_config_on_startup",
]

_LAZY_IMPORTS: Dict[str, Tuple[str, str]] = {
    "initialize_peer_cache_on_startup_with_retry": (
        "bot.services.peer_cache",
        "initialize_peer_cache_on_startup_with_retry",
    ),
    "cache_peer_if_needed": ("bot.services.peer_cache", "cache_peer_if_needed"),
    "import_watch_config_on_startup": (
        "bot.services.config_import",
        "import_watch_config_on_startup",
    ),
}


def __getattr__(name: str) -> Any:
    target = _LAZY_IMPORTS.get(name)
    if not target:
        raise AttributeError(f"module 'bot.services' has no attribute '{name}'")

    module_name, attr_name = target
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(__all__))
