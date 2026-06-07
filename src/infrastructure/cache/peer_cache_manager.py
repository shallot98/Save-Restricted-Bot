"""Cache manager for Telegram peer data."""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .cache_manager_base import BaseCacheManager
from .unified import UnifiedCache


@dataclass(frozen=True)
class PeerCacheRequest:
    peer_id: int
    peer_type: str
    peer_info: Dict[str, Any]


class PeerCacheManager(BaseCacheManager):
    """Cache manager for Telegram peers, usernames, and cached markers."""

    def __init__(self, cache: Optional[UnifiedCache] = None):
        super().__init__(
            cache=cache,
            key_prefix="peer",
            default_ttl=3600.0,
        )

    def cache_peer(
        self,
        request: PeerCacheRequest | int | None = None,
        *legacy_args: Any,
        peer_type: Optional[str] = None,
        peer_info: Optional[Dict[str, Any]] = None,
        ttl: Optional[float] = None,
        **legacy_fields: Any,
    ) -> None:
        request = _peer_cache_request(
            request,
            legacy_args,
            peer_type=peer_type,
            peer_info=peer_info,
            legacy_fields=legacy_fields,
        )
        key = f"{request.peer_type}:{request.peer_id}"
        self.set(key, request.peer_info, ttl)

    def get_peer(self, peer_id: int, peer_type: str) -> Optional[Dict[str, Any]]:
        key = f"{peer_type}:{peer_id}"
        return self.get(key)

    def cache_peer_by_username(
        self,
        username: str,
        peer_info: Dict[str, Any],
        ttl: Optional[float] = None,
    ) -> None:
        key = f"username:{username.lower()}"
        self.set(key, peer_info, ttl)

    def get_peer_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        key = f"username:{username.lower()}"
        return self.get(key)

    def invalidate_peer(self, peer_id: int, peer_type: str) -> bool:
        key = f"{peer_type}:{peer_id}"
        return self.delete(key)

    def mark_peer_cached(self, peer_id: int) -> None:
        key = f"cached:{peer_id}"
        self.set(key, True, ttl=86400.0)

    def is_peer_cached(self, peer_id: int) -> bool:
        key = f"cached:{peer_id}"
        return self.get(key) is True


def _peer_cache_request(
    request: PeerCacheRequest | int | None,
    legacy_args: tuple[Any, ...],
    *,
    peer_type: Optional[str],
    peer_info: Optional[Dict[str, Any]],
    legacy_fields: dict[str, Any],
) -> PeerCacheRequest:
    fields = dict(legacy_fields)
    if isinstance(request, PeerCacheRequest):
        if legacy_args or fields or peer_type is not None or peer_info is not None:
            raise TypeError("cache_peer received both request and legacy fields")
        return request
    if request is None:
        if "peer_id" not in fields:
            raise TypeError("cache_peer requires peer_id")
        request = fields.pop("peer_id")
    if len(legacy_args) > 2:
        raise TypeError("cache_peer accepts at most 3 legacy positional arguments")
    if legacy_args:
        if peer_type is not None:
            raise TypeError("cache_peer received duplicate peer_type values")
        peer_type = legacy_args[0]
    if len(legacy_args) == 2:
        if peer_info is not None:
            raise TypeError("cache_peer received duplicate peer_info values")
        peer_info = legacy_args[1]
    if peer_type is None and "peer_type" in fields:
        peer_type = fields.pop("peer_type")
    if peer_info is None and "peer_info" in fields:
        peer_info = fields.pop("peer_info")
    if fields:
        unknown = ", ".join(sorted(fields))
        raise TypeError(f"cache_peer got unexpected keyword argument(s): {unknown}")
    if peer_type is None or peer_info is None:
        raise TypeError("cache_peer requires peer_type and peer_info")
    return PeerCacheRequest(int(request), peer_type, peer_info)
