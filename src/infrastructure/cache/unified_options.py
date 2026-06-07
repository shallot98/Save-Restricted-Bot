"""Compatibility parsing for UnifiedCache construction."""

from dataclasses import dataclass
from typing import Any, Optional

from .interface import InvalidationStrategy


@dataclass(frozen=True)
class UnifiedCacheOptions:
    default_ttl: float = 300.0
    max_size: int = 10000
    cleanup_interval: float = 60.0
    invalidation_strategy: InvalidationStrategy = InvalidationStrategy.TIME_BASED
    name: str = "default"


@dataclass(frozen=True)
class UnifiedCacheOverrideFields:
    default_ttl: Optional[float] = None
    max_size: Optional[int] = None
    cleanup_interval: Optional[float] = None
    invalidation_strategy: Optional[InvalidationStrategy] = None
    name: Optional[str] = None

    @property
    def values(self) -> tuple[Any, ...]:
        return (
            self.default_ttl,
            self.max_size,
            self.cleanup_interval,
            self.invalidation_strategy,
            self.name,
        )


def unified_cache_options(
    options: UnifiedCacheOptions | float | None,
    legacy_args: tuple[Any, ...],
    *,
    default_ttl: Optional[float],
    max_size: Optional[int],
    cleanup_interval: Optional[float],
    invalidation_strategy: Optional[InvalidationStrategy],
    name: Optional[str],
) -> UnifiedCacheOptions:
    overrides = UnifiedCacheOverrideFields(
        default_ttl=default_ttl,
        max_size=max_size,
        cleanup_interval=cleanup_interval,
        invalidation_strategy=invalidation_strategy,
        name=name,
    )
    if isinstance(options, UnifiedCacheOptions):
        _reject_mixed_options(legacy_args, overrides)
        return options

    values = _legacy_unified_cache_values(options, legacy_args)
    _apply_unified_cache_overrides(values, overrides)
    return _build_unified_cache_options(values)


def _reject_mixed_options(
    legacy_args: tuple[Any, ...],
    overrides: UnifiedCacheOverrideFields,
) -> None:
    if legacy_args or any(value is not None for value in overrides.values):
        raise TypeError("UnifiedCache received both options object and legacy fields")


def _legacy_unified_cache_values(
    first_value: float | None,
    legacy_args: tuple[Any, ...],
) -> list[Any]:
    if len(legacy_args) > 4:
        raise TypeError("UnifiedCache accepts at most 5 legacy positional arguments")
    values: list[Any] = [None, None, None, None, None]
    if first_value is not None:
        values[0] = first_value
    for index, value in enumerate(legacy_args, start=1):
        values[index] = value
    return values


def _apply_unified_cache_overrides(
    values: list[Any],
    overrides: UnifiedCacheOverrideFields,
) -> None:
    names = ("default_ttl", "max_size", "cleanup_interval", "invalidation_strategy", "name")
    for index, override in enumerate(overrides.values):
        if override is not None:
            if values[index] is not None:
                raise TypeError(f"UnifiedCache received duplicate {names[index]}")
            values[index] = override


def _build_unified_cache_options(values: list[Any]) -> UnifiedCacheOptions:
    return UnifiedCacheOptions(
        default_ttl=values[0] if values[0] is not None else 300.0,
        max_size=values[1] if values[1] is not None else 10000,
        cleanup_interval=values[2] if values[2] is not None else 60.0,
        invalidation_strategy=values[3] or InvalidationStrategy.TIME_BASED,
        name=values[4] or "default",
    )
