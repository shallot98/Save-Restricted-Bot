"""
Cache Decorators
================

Enhanced caching decorators with configurable options.
"""

import logging
import hashlib
import json
from typing import Callable, Optional, Any, TypeVar, Union
from functools import wraps

from .interface import InvalidationStrategy
from .unified import UnifiedCache, get_unified_cache

logger = logging.getLogger(__name__)

F = TypeVar('F', bound=Callable[..., Any])


def _generate_cache_key(
    func: Callable,
    args: tuple,
    kwargs: dict,
    key_prefix: str = "",
    key_builder: Optional[Callable[..., str]] = None
) -> str:
    """
    Generate cache key from function and arguments

    Args:
        func: The decorated function
        args: Positional arguments
        kwargs: Keyword arguments
        key_prefix: Optional key prefix
        key_builder: Optional custom key builder function

    Returns:
        Generated cache key
    """
    if key_builder is not None:
        return key_builder(*args, **kwargs)

    # Build key parts
    key_parts = []

    if key_prefix:
        key_parts.append(key_prefix)

    key_parts.append(func.__module__)
    key_parts.append(func.__name__)

    # Handle args (skip 'self' for methods)
    if args:
        processed_args = []
        for i, arg in enumerate(args):
            # Skip self/cls for instance/class methods
            if i == 0 and hasattr(arg, '__class__') and hasattr(func, '__self__'):
                continue
            processed_args.append(_serialize_arg(arg))
        if processed_args:
            key_parts.append(":".join(processed_args))

    # Handle kwargs
    if kwargs:
        sorted_kwargs = sorted(kwargs.items())
        kwargs_str = ",".join(f"{k}={_serialize_arg(v)}" for k, v in sorted_kwargs)
        key_parts.append(kwargs_str)

    return ":".join(key_parts)


def _serialize_arg(arg: Any) -> str:
    """
    Serialize argument to string for cache key

    Args:
        arg: Argument to serialize

    Returns:
        String representation
    """
    if arg is None:
        return "None"
    if isinstance(arg, (str, int, float, bool)):
        return str(arg)
    if isinstance(arg, (list, tuple)):
        return f"[{','.join(_serialize_arg(x) for x in arg)}]"
    if isinstance(arg, dict):
        items = sorted(arg.items())
        return f"{{{','.join(f'{k}:{_serialize_arg(v)}' for k, v in items)}}}"
    if hasattr(arg, 'id'):
        return f"{arg.__class__.__name__}:{arg.id}"
    if hasattr(arg, '__dict__'):
        # Hash complex objects
        try:
            obj_str = json.dumps(arg.__dict__, sort_keys=True, default=str)
            return hashlib.md5(obj_str.encode()).hexdigest()[:8]
        except (TypeError, ValueError):
            return str(id(arg))
    return str(arg)


def cached(
    ttl: float = 300.0,
    key_prefix: str = "",
    invalidation_strategy: InvalidationStrategy = InvalidationStrategy.TIME_BASED,
    cache_instance: Optional[UnifiedCache] = None,
    key_builder: Optional[Callable[..., str]] = None,
    condition: Optional[Callable[..., bool]] = None,
    unless: Optional[Callable[[Any], bool]] = None
) -> Callable[[F], F]:
    """
    Enhanced caching decorator

    Args:
        ttl: Cache TTL in seconds
        key_prefix: Prefix for cache keys
        invalidation_strategy: Cache invalidation strategy
        cache_instance: Custom cache instance (uses global if None)
        key_builder: Custom function to build cache key
        condition: Function that returns True if result should be cached
        unless: Function that returns True if result should NOT be cached

    Returns:
        Decorator function

    Example:
        @cached(ttl=600, key_prefix="user")
        def get_user(user_id):
            return fetch_user_from_db(user_id)

        @cached(ttl=300, key_builder=lambda user_id, **kw: f"user:{user_id}")
        def get_user_profile(user_id, include_stats=False):
            return fetch_profile(user_id, include_stats)

        @cached(ttl=60, unless=lambda result: result is None)
        def get_optional_data(key):
            return maybe_fetch(key)
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Get cache instance
            cache = cache_instance or get_unified_cache()

            # Generate cache key
            cache_key = _generate_cache_key(
                func, args, kwargs, key_prefix, key_builder
            )

            # Check condition
            if condition is not None and not condition(*args, **kwargs):
                return func(*args, **kwargs)

            # Try to get from cache
            cached_value = cache.get(cache_key)

            if cached_value is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_value

            # Cache miss, execute function
            logger.debug(f"Cache miss: {cache_key}")
            result = func(*args, **kwargs)

            # Check unless condition
            if unless is not None and unless(result):
                logger.debug(f"Cache skip (unless): {cache_key}")
                return result

            # Store in cache
            cache.set(cache_key, result, ttl)
            logger.debug(f"Cache set: {cache_key}")

            return result

        # Attach cache control methods
        wrapper.cache_clear = lambda: _clear_function_cache(func, key_prefix, cache_instance)
        wrapper.cache_key = lambda *a, **kw: _generate_cache_key(func, a, kw, key_prefix, key_builder)

        return wrapper  # type: ignore
    return decorator


def _clear_function_cache(
    func: Callable,
    key_prefix: str,
    cache_instance: Optional[UnifiedCache]
) -> int:
    """Clear all cache entries for a function"""
    cache = cache_instance or get_unified_cache()
    pattern = f"{key_prefix}:{func.__module__}:{func.__name__}:*" if key_prefix else f"{func.__module__}:{func.__name__}:*"
    return cache.delete_pattern(pattern)


def cache_invalidate(
    key_prefix: str = "",
    key_pattern: Optional[str] = None,
    cache_instance: Optional[UnifiedCache] = None
) -> Callable[[F], F]:
    """
    Decorator to invalidate cache after function execution

    Use this on write operations to clear related cache entries.

    Args:
        key_prefix: Prefix of keys to invalidate
        key_pattern: Pattern of keys to invalidate (supports * wildcard)
        cache_instance: Custom cache instance

    Example:
        @cache_invalidate(key_prefix="notes:list")
        def create_note(note_data):
            return db.create(note_data)

        @cache_invalidate(key_pattern="user:*:profile")
        def update_user(user_id, data):
            return db.update(user_id, data)
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Execute function first
            result = func(*args, **kwargs)

            # Invalidate cache
            cache = cache_instance or get_unified_cache()

            if key_pattern:
                deleted = cache.delete_pattern(key_pattern)
                logger.debug(f"Cache invalidated: pattern='{key_pattern}', deleted={deleted}")
            elif key_prefix:
                deleted = cache.delete_prefix(key_prefix)
                logger.debug(f"Cache invalidated: prefix='{key_prefix}', deleted={deleted}")

            return result
        return wrapper  # type: ignore
    return decorator


def cache_aside(
    ttl: float = 300.0,
    key_builder: Callable[..., str] = None,
    cache_instance: Optional[UnifiedCache] = None,
    fallback: Optional[Callable[[], Any]] = None
) -> Callable[[F], F]:
    """
    Cache-aside pattern decorator

    Implements the cache-aside (lazy-loading) pattern:
    1. Check cache first
    2. If miss, load from source
    3. Store in cache
    4. Return value

    Args:
        ttl: Cache TTL in seconds
        key_builder: Function to build cache key
        cache_instance: Custom cache instance
        fallback: Fallback function if main function fails

    Example:
        @cache_aside(ttl=600, key_builder=lambda id: f"entity:{id}")
        def get_entity(entity_id):
            return db.get(entity_id)
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            cache = cache_instance or get_unified_cache()

            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                cache_key = _generate_cache_key(func, args, kwargs)

            # Try cache first
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Load from source
            try:
                value = func(*args, **kwargs)
            except Exception as e:
                if fallback:
                    logger.warning(f"Function failed, using fallback: {e}")
                    value = fallback()
                else:
                    raise

            # Store in cache
            if value is not None:
                cache.set(cache_key, value, ttl)

            return value
        return wrapper  # type: ignore
    return decorator


__all__ = [
    "cached",
    "cache_invalidate",
    "cache_aside",
]
