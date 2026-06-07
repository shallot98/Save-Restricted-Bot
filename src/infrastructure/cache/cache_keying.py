"""Cache key generation helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class CacheKeyContext:
    func: Callable
    args: tuple
    kwargs: dict
    key_prefix: str = ""
    key_builder: Optional[Callable[..., str]] = None


def build_cache_key(context: CacheKeyContext) -> str:
    if context.key_builder is not None:
        return context.key_builder(*context.args, **context.kwargs)

    key_parts = _base_key_parts(context)
    key_parts.extend(_argument_key_parts(context.func, context.args, context.kwargs))
    return ":".join(key_parts)


def _base_key_parts(context: CacheKeyContext) -> list[str]:
    parts = []
    if context.key_prefix:
        parts.append(context.key_prefix)
    parts.append(context.func.__module__)
    parts.append(context.func.__name__)
    return parts


def _argument_key_parts(func: Callable, args: tuple, kwargs: dict) -> list[str]:
    parts = []
    serialized_args = _serialized_args(func, args)
    if serialized_args:
        parts.append(":".join(serialized_args))
    if kwargs:
        sorted_kwargs = sorted(kwargs.items())
        parts.append(",".join(f"{k}={serialize_cache_arg(v)}" for k, v in sorted_kwargs))
    return parts


def _serialized_args(func: Callable, args: tuple) -> list[str]:
    processed_args = []
    for index, arg in enumerate(args):
        if _should_skip_method_owner(func, index, arg):
            continue
        processed_args.append(serialize_cache_arg(arg))
    return processed_args


def _should_skip_method_owner(func: Callable, index: int, arg: Any) -> bool:
    return index == 0 and hasattr(arg, "__class__") and hasattr(func, "__self__")


def serialize_cache_arg(arg: Any) -> str:
    if arg is None:
        return "None"
    if isinstance(arg, (str, int, float, bool)):
        return str(arg)
    if isinstance(arg, (list, tuple)):
        return f"[{','.join(serialize_cache_arg(item) for item in arg)}]"
    if isinstance(arg, dict):
        return _serialize_dict_arg(arg)
    if hasattr(arg, "id"):
        return f"{arg.__class__.__name__}:{arg.id}"
    if hasattr(arg, "__dict__"):
        return _serialize_object_arg(arg)
    return str(arg)


def _serialize_dict_arg(arg: dict) -> str:
    items = sorted(arg.items())
    return f"{{{','.join(f'{key}:{serialize_cache_arg(value)}' for key, value in items)}}}"


def _serialize_object_arg(arg: Any) -> str:
    try:
        obj_str = json.dumps(arg.__dict__, sort_keys=True, default=str)
        return hashlib.md5(obj_str.encode()).hexdigest()[:8]
    except (TypeError, ValueError):
        return str(id(arg))
