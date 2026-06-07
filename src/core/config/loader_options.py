"""Compatibility parsing for ConfigLoader options."""

from pathlib import Path
from typing import Any, Dict, Optional


def load_validate_options(
    legacy_args: tuple[Any, ...],
    *,
    file_path: Optional[Path],
    env_prefix: str,
    default_config: Optional[Dict[str, Any]],
) -> tuple[Optional[Path], str, Optional[Dict[str, Any]]]:
    if len(legacy_args) > 3:
        raise TypeError("load_and_validate accepts at most 3 legacy positional options")
    if not legacy_args:
        return file_path, env_prefix, default_config

    values = [file_path, env_prefix, default_config]
    names = ("file_path", "env_prefix", "default_config")
    defaults = [None, "", None]
    for index, value in enumerate(legacy_args):
        if values[index] != defaults[index]:
            raise TypeError(f"load_and_validate received duplicate {names[index]}")
        values[index] = value
    return values[0], values[1], values[2]
