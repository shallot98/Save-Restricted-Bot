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
WEBDAV_CONFIG_FILE = os.path.join(CONFIG_DIR, 'webdav_config.json')
VIEWER_CONFIG_FILE = os.path.join(CONFIG_DIR, 'viewer_config.json')

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
    try:
        watch_config = load_watch_config()
        logger.info(f"📂 读取watch_config文件: {WATCH_FILE}")
        logger.info(f"   配置文件状态: {'有内容' if watch_config else '为空'}")
    except Exception as e:
        logger.error(f"❌ 加载watch_config失败: {e}")
        return set()
    
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
    """Get the current set of monitored sources

    Note: This function now returns the pre-loaded set instead of lazy loading.
    The set is initialized at startup by reload_monitored_sources().
    If the set is empty, it will attempt to reload once.
    """
    global _monitored_sources

    # 如果集合为空，尝试重新加载一次（懒加载机制）
    if not _monitored_sources:
        logger.warning("⚠️ 监控源集合为空，尝试重新加载...")
        reload_monitored_sources()

        # 再次检查
        if not _monitored_sources:
            logger.warning("⚠️ 重新加载后监控源仍为空！")
            logger.warning("   请检查 watch_config.json 文件是否存在且格式正确。")
            logger.warning("   如果问题持续，请尝试重新添加监控配置。")

    return _monitored_sources


def save_watch_config(config: Dict[str, Any], auto_reload: bool = True):
    """Save watch config to file and optionally reload monitored sources

    Args:
        config: Configuration dictionary to save
        auto_reload: If True, automatically reload monitored sources after save (default: True)
    """
    logger.info(f"💾 保存监控配置到文件: {WATCH_FILE}")
    logger.info(f"   配置包含 {len(config)} 个用户的监控任务")

    with open(WATCH_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())

    logger.info("✅ 配置文件保存成功")

    # Automatically reload monitored sources to keep them in sync
    if auto_reload:
        logger.info("🔄 自动重新加载监控源...")
        reload_monitored_sources()
    else:
        logger.warning("⚠️ 跳过自动重载（auto_reload=False），监控源可能不同步")


# 初始化为空集合，将在启动时通过 reload_monitored_sources() 加载
# 不再使用懒加载机制，避免竞态条件
_monitored_sources = set()


def load_webdav_config() -> Dict[str, Any]:
    """Load WebDAV configuration from file"""
    if os.path.exists(WEBDAV_CONFIG_FILE):
        try:
            with open(WEBDAV_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"❌ 加载 WebDAV 配置失败: {e}")

    # 返回默认配置
    default_config = {
        "enabled": False,
        "url": "",
        "username": "",
        "password": "",
        "base_path": "/telegram_media",
        "keep_local_copy": False
    }

    # 保存默认配置
    save_webdav_config(default_config)
    return default_config


def save_webdav_config(config: Dict[str, Any]):
    """Save WebDAV configuration to file

    Args:
        config: Configuration dictionary to save
    """
    logger.info(f"💾 保存 WebDAV 配置到文件: {WEBDAV_CONFIG_FILE}")

    with open(WEBDAV_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())

    logger.info("✅ WebDAV 配置文件保存成功")


def load_viewer_config() -> Dict[str, Any]:
    """Load viewer website configuration from file"""
    if os.path.exists(VIEWER_CONFIG_FILE):
        try:
            with open(VIEWER_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"❌ 加载观看网站配置失败: {e}")

    # 返回默认配置
    default_config = {
        "viewer_url": "https://example.com/watch?dn="
    }

    # 保存默认配置
    save_viewer_config(default_config)
    return default_config


def save_viewer_config(config: Dict[str, Any]):
    """Save viewer website configuration to file

    Args:
        config: Configuration dictionary to save
    """
    logger.info(f"💾 保存观看网站配置到文件: {VIEWER_CONFIG_FILE}")

    with open(VIEWER_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())

    logger.info("✅ 观看网站配置文件保存成功")
