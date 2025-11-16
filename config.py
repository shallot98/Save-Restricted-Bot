"""
Configuration management module
Handles loading, saving, and accessing configuration files
"""
import os
import json
import logging
from typing import Dict, Any, Set

logger = logging.getLogger(__name__)

# Data directory configuration
DEFAULT_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'data'))
DATA_DIR = os.environ.get('DATA_DIR', DEFAULT_DATA_DIR)
CONFIG_DIR = os.path.join(DATA_DIR, 'config')
MEDIA_DIR = os.path.join(DATA_DIR, 'media')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')
WATCH_FILE = os.path.join(CONFIG_DIR, 'watch_config.json')

# Ensure directories exist
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(MEDIA_DIR, exist_ok=True)

# Global state
_monitored_sources: Set[str] = set()


def load_config() -> Dict[str, Any]:
    """Load main configuration from file or environment"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    
    config_data = {}
    for key in ["TOKEN", "HASH", "ID", "STRING", "OWNER_ID"]:
        value = os.environ.get(key)
        if value:
            config_data[key] = value
    
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=4, ensure_ascii=False)
    
    return config_data


def getenv(var: str, data: Dict[str, Any]) -> str:
    """Get configuration value, prioritizing config file over environment variables
    
    Priority:
    1. config.json (DATA) - configuration saved by setup.py
    2. Environment variables - fallback if config.json doesn't have the value
    """
    config_value = data.get(var)
    if config_value:
        return config_value
    return os.environ.get(var)


def load_watch_config() -> Dict[str, Any]:
    """Load watch configuration from file"""
    if os.path.exists(WATCH_FILE):
        try:
            with open(WATCH_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    
    with open(WATCH_FILE, 'w', encoding='utf-8') as f:
        json.dump({}, f, indent=4, ensure_ascii=False)
    
    return {}


def build_monitored_sources() -> Set[str]:
    """Build a set of all monitored source chat IDs from watch config"""
    watch_config = load_watch_config()
    sources = set()
    
    for user_id, watches in watch_config.items():
        for watch_key, watch_data in watches.items():
            if isinstance(watch_data, dict):
                source = watch_data.get('source')
            else:
                # Old format: key is the source
                source = watch_key
            
            # Add to set if valid (exclude None and special values like "me")
            if source and source != 'me':
                sources.add(str(source))
    
    return sources


def reload_monitored_sources():
    """Reload the monitored sources set (call after config changes)"""
    global _monitored_sources
    _monitored_sources = build_monitored_sources()
    logger.info(f"🔄 监控源已更新: {_monitored_sources if _monitored_sources else '无'}")


def get_monitored_sources() -> Set[str]:
    """Get the current set of monitored sources"""
    return _monitored_sources


def save_watch_config(config: Dict[str, Any], auto_reload: bool = True):
    """Save watch config to file and optionally reload monitored sources
    
    Args:
        config: Configuration dictionary to save
        auto_reload: If True, automatically reload monitored sources after save (default: True)
    """
    with open(WATCH_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    
    # Automatically reload monitored sources to keep them in sync
    if auto_reload:
        reload_monitored_sources()


# Initialize monitored sources on module import
_monitored_sources = build_monitored_sources()
if _monitored_sources:
    logger.info(f"📋 正在监控的源频道: {_monitored_sources}")
else:
    logger.info(f"📋 当前没有配置监控源")
