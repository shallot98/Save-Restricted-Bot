"""Global UnifiedCache factory."""

import threading
from typing import Any, Optional

_unified_cache: Optional[Any] = None
_cache_lock = threading.Lock()


def get_unified_cache(
    default_ttl: float = 300.0,
    max_size: int = 10000,
    name: str = "global",
) -> Any:
    """Get global unified cache instance."""
    global _unified_cache
    if _unified_cache is None:
        with _cache_lock:
            if _unified_cache is None:
                from .unified import UnifiedCache

                _unified_cache = UnifiedCache(
                    default_ttl=default_ttl,
                    max_size=max_size,
                    name=name,
                )
    return _unified_cache
