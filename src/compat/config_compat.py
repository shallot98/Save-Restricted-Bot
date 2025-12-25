"""
Configuration Compatibility Layer
=================================

Provides backward-compatible functions that delegate to the new Settings class.
"""

import os
from typing import Dict, Any, Set, Optional

from src.core.config import settings


# Path constants - delegate to settings
DATA_DIR = str(settings.paths.data_dir)
CONFIG_DIR = str(settings.paths.config_dir)
MEDIA_DIR = str(settings.paths.media_dir)
CONFIG_FILE = str(settings.paths.config_file)
WATCH_FILE = str(settings.paths.watch_file)
WEBDAV_CONFIG_FILE = str(settings.paths.webdav_file)
VIEWER_CONFIG_FILE = str(settings.paths.viewer_file)


def load_config() -> Dict[str, Any]:
    """Load main configuration from file or environment

    Backward compatible function that delegates to Settings.
    """
    return settings.main_config


def getenv(var: str, data: Dict[str, Any]) -> str:
    """Get configuration value, prioritizing config file over environment variables

    Backward compatible function that delegates to Settings.

    Priority:
    1. config.json (DATA) - configuration saved by setup.py
    2. Environment variables - fallback if config.json doesn't have the value

    Note: Returns empty string if value is not found or is empty.
    For STRING variable specifically, empty string means "not configured".
    """
    config_value = data.get(var)
    if config_value:
        return config_value
    # Return None if env var doesn't exist, otherwise return its value (may be empty string)
    env_value = os.environ.get(var)
    return env_value if env_value is not None else ""


def getenv_optional(var: str, data: Dict[str, Any]) -> Optional[str]:
    """Get configuration value, returning None when missing/blank.

    This helper is intended for optional secrets such as session strings where
    empty/whitespace should be treated as "not configured".
    """
    config_value = data.get(var)
    if isinstance(config_value, str) and config_value.strip():
        return config_value.strip()

    env_value = os.environ.get(var)
    if env_value is None:
        return None

    env_value = env_value.strip()
    return env_value or None


def load_watch_config() -> Dict[str, Any]:
    """Load watch configuration from file

    Backward compatible function that delegates to Settings.
    """
    from src.core.container import get_watch_service

    return get_watch_service().get_all_configs_dict()


def save_watch_config(config: Dict[str, Any], auto_reload: bool = True) -> None:
    """Save watch config to file and optionally reload monitored sources

    Backward compatible function that delegates to Settings.

    Args:
        config: Configuration dictionary to save
        auto_reload: If True, automatically reload monitored sources after save
    """
    from src.core.container import get_watch_service

    get_watch_service().save_config_dict(config)
    if auto_reload:
        get_watch_service().reload_config()
        get_watch_service().invalidate_cache()


def build_monitored_sources() -> Set[str]:
    """Build a set of all monitored source chat IDs from watch config

    Backward compatible function that delegates to Settings.
    """
    from src.core.container import get_watch_service

    return get_watch_service().get_monitored_sources()


def reload_monitored_sources() -> None:
    """Reload the monitored sources set (call after config changes)

    Backward compatible function that delegates to Settings.
    """
    from src.core.container import get_watch_service

    get_watch_service().reload_config()
    get_watch_service().invalidate_cache()


def get_monitored_sources() -> Set[str]:
    """Get the current set of monitored sources

    Backward compatible function that delegates to Settings.
    """
    from src.core.container import get_watch_service

    return get_watch_service().get_monitored_sources()


def load_webdav_config() -> Dict[str, Any]:
    """Load WebDAV configuration from file

    Backward compatible function that delegates to Settings.
    """
    return settings.webdav_config


def save_webdav_config(config: Dict[str, Any]) -> None:
    """Save WebDAV configuration to file

    Backward compatible function that delegates to Settings.
    """
    settings.save_webdav_config(config)


def load_viewer_config() -> Dict[str, Any]:
    """Load viewer website configuration from file

    Backward compatible function that delegates to Settings.
    """
    return settings.viewer_config


def save_viewer_config(config: Dict[str, Any]) -> None:
    """Save viewer website configuration to file

    Backward compatible function that delegates to Settings.
    """
    settings.save_viewer_config(config)
