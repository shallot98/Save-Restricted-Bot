"""
Cache Decorators
================

Enhanced caching decorators with configurable options.
"""

from functools import wraps
from typing import Any, Callable, TypeVar

from .decorator_runtime import (
    DecoratedCall,
    cache_aside_options,
    cache_invalidate_options,
    cached_options,
    clear_function_cache,
    function_cache_key,
    run_cache_aside_call,
    run_cache_invalidate_call,
    run_cached_call,
)

F = TypeVar("F", bound=Callable[..., Any])


def cached(*decorator_args: Any, **decorator_kwargs: Any) -> Callable[[F], F]:
    """Enhanced caching decorator."""
    options = cached_options(decorator_args, decorator_kwargs)

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return run_cached_call(DecoratedCall(func, args, kwargs), options)

        wrapper.cache_clear = lambda: clear_function_cache(
            func,
            options.key_prefix,
            options.cache_instance,
        )
        wrapper.cache_key = lambda *args, **kwargs: function_cache_key(
            DecoratedCall(func, args, kwargs),
            options,
        )
        return wrapper  # type: ignore

    return decorator


def cache_invalidate(*decorator_args: Any, **decorator_kwargs: Any) -> Callable[[F], F]:
    """Decorator to invalidate cache after function execution."""
    options = cache_invalidate_options(decorator_args, decorator_kwargs)

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return run_cache_invalidate_call(DecoratedCall(func, args, kwargs), options)

        return wrapper  # type: ignore

    return decorator


def cache_aside(*decorator_args: Any, **decorator_kwargs: Any) -> Callable[[F], F]:
    """Cache-aside pattern decorator."""
    options = cache_aside_options(decorator_args, decorator_kwargs)

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return run_cache_aside_call(DecoratedCall(func, args, kwargs), options)

        return wrapper  # type: ignore

    return decorator


__all__ = [
    "cached",
    "cache_invalidate",
    "cache_aside",
]
