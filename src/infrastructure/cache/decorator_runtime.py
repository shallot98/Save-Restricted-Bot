"""Runtime helpers for cache decorators."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional

from .cache_keying import CacheKeyContext, build_cache_key
from .interface import InvalidationStrategy
from .unified import UnifiedCache, get_unified_cache

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CachedOptions:
    ttl: float = 300.0
    key_prefix: str = ""
    invalidation_strategy: InvalidationStrategy = InvalidationStrategy.TIME_BASED
    cache_instance: Optional[UnifiedCache] = None
    key_builder: Optional[Callable[..., str]] = None
    condition: Optional[Callable[..., bool]] = None
    unless: Optional[Callable[[Any], bool]] = None


@dataclass(frozen=True)
class CacheInvalidateOptions:
    key_prefix: str = ""
    key_pattern: Optional[str] = None
    cache_instance: Optional[UnifiedCache] = None


@dataclass(frozen=True)
class CacheAsideOptions:
    ttl: float = 300.0
    key_builder: Optional[Callable[..., str]] = None
    cache_instance: Optional[UnifiedCache] = None
    fallback: Optional[Callable[[], Any]] = None


@dataclass(frozen=True)
class OptionParseRequest:
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    fields: tuple[str, ...]
    defaults: Any


@dataclass(frozen=True)
class DecoratedCall:
    func: Callable[..., Any]
    args: tuple[Any, ...]
    kwargs: dict[str, Any]


def cached_options(args: tuple, kwargs: dict) -> CachedOptions:
    fields = ("ttl", "key_prefix", "invalidation_strategy", "cache_instance", "key_builder", "condition", "unless")
    values = _option_values(OptionParseRequest(args, kwargs, fields, CachedOptions()))
    return CachedOptions(**values)


def cache_invalidate_options(args: tuple, kwargs: dict) -> CacheInvalidateOptions:
    fields = ("key_prefix", "key_pattern", "cache_instance")
    values = _option_values(OptionParseRequest(args, kwargs, fields, CacheInvalidateOptions()))
    return CacheInvalidateOptions(**values)


def cache_aside_options(args: tuple, kwargs: dict) -> CacheAsideOptions:
    fields = ("ttl", "key_builder", "cache_instance", "fallback")
    values = _option_values(OptionParseRequest(args, kwargs, fields, CacheAsideOptions()))
    return CacheAsideOptions(**values)


def _option_values(request: OptionParseRequest) -> dict[str, Any]:
    args = request.args
    kwargs = request.kwargs
    fields = request.fields
    if len(args) > len(fields):
        raise TypeError(f"expected at most {len(fields)} positional arguments")

    values = request.defaults.__dict__.copy()
    for field, value in zip(fields, args):
        if field in kwargs:
            raise TypeError(f"multiple values for argument '{field}'")
        values[field] = value

    unknown = set(kwargs) - set(fields)
    if unknown:
        unknown_name = sorted(unknown)[0]
        raise TypeError(f"unexpected keyword argument '{unknown_name}'")
    values.update(kwargs)
    return values


def run_cached_call(call: DecoratedCall, options: CachedOptions) -> Any:
    cache = _resolve_cache(options.cache_instance)
    cache_key = function_cache_key(call, options)

    if options.condition is not None and not options.condition(*call.args, **call.kwargs):
        return call.func(*call.args, **call.kwargs)

    if options.unless is None:
        return _run_cached_get_or_set(cache, cache_key, call, ttl=options.ttl)

    cached_value = cache.get(cache_key)
    if cached_value is not None:
        logger.debug(f"Cache hit: {cache_key}")
        return cached_value

    logger.debug(f"Cache miss: {cache_key}")
    result = call.func(*call.args, **call.kwargs)
    if options.unless is not None and options.unless(result):
        logger.debug(f"Cache skip (unless): {cache_key}")
        return result

    cache.set(cache_key, result, options.ttl)
    logger.debug(f"Cache set: {cache_key}")
    return result


def _run_cached_get_or_set(
    cache: UnifiedCache,
    cache_key: str,
    call: DecoratedCall,
    *,
    ttl: float,
) -> Any:
    def factory() -> Any:
        logger.debug(f"Cache miss: {cache_key}")
        return call.func(*call.args, **call.kwargs)

    return cache.get_or_set(cache_key, factory, ttl)


def function_cache_key(call: DecoratedCall, options: CachedOptions) -> str:
    return build_cache_key(
        CacheKeyContext(
            func=call.func,
            args=call.args,
            kwargs=call.kwargs,
            key_prefix=options.key_prefix,
            key_builder=options.key_builder,
        )
    )


def clear_function_cache(func: Callable, key_prefix: str, cache_instance: Optional[UnifiedCache]) -> int:
    cache = _resolve_cache(cache_instance)
    if key_prefix:
        pattern = f"{key_prefix}:{func.__module__}:{func.__name__}:*"
    else:
        pattern = f"{func.__module__}:{func.__name__}:*"
    return cache.delete_pattern(pattern)


def run_cache_invalidate_call(
    call: DecoratedCall,
    options: CacheInvalidateOptions,
) -> Any:
    result = call.func(*call.args, **call.kwargs)
    cache = _resolve_cache(options.cache_instance)
    if options.key_pattern:
        deleted = cache.delete_pattern(options.key_pattern)
        logger.debug(f"Cache invalidated: pattern='{options.key_pattern}', deleted={deleted}")
    elif options.key_prefix:
        deleted = cache.delete_prefix(options.key_prefix)
        logger.debug(f"Cache invalidated: prefix='{options.key_prefix}', deleted={deleted}")
    return result


def run_cache_aside_call(call: DecoratedCall, options: CacheAsideOptions) -> Any:
    cache = _resolve_cache(options.cache_instance)
    cache_key = _cache_aside_key(call, options)

    cached_value = cache.get(cache_key)
    if cached_value is not None:
        return cached_value

    value = _load_cache_aside_value(call, options)
    if value is not None:
        cache.set(cache_key, value, options.ttl)
    return value


def _cache_aside_key(call: DecoratedCall, options: CacheAsideOptions) -> str:
    if options.key_builder:
        return options.key_builder(*call.args, **call.kwargs)
    return build_cache_key(CacheKeyContext(func=call.func, args=call.args, kwargs=call.kwargs))


def _load_cache_aside_value(call: DecoratedCall, options: CacheAsideOptions) -> Any:
    try:
        return call.func(*call.args, **call.kwargs)
    except Exception as e:
        if options.fallback is None:
            raise
        logger.warning(f"Function failed, using fallback: {e}")
        return options.fallback()


def _resolve_cache(cache_instance: Optional[UnifiedCache]) -> UnifiedCache:
    return cache_instance or get_unified_cache()
