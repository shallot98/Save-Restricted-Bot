"""
Watch configuration management module with per-watch filters and settings
"""

import json
import os
import shutil
import uuid
from typing import Dict, List, Optional, Any, Tuple
from regex_filters import compile_pattern_list, MAX_PATTERN_COUNT, MAX_PATTERN_LENGTH

WATCH_FILE = 'watch_config.json'
WATCH_FILE_BACKUP = 'watch_config.json.backup'
CURRENT_SCHEMA_VERSION = 2


def generate_watch_id() -> str:
    """Generate a unique watch ID"""
    return str(uuid.uuid4())


def load_watch_config() -> Dict[str, Any]:
    """
    Load watch configuration with automatic migration support.
    Returns config in new format (schema v2).
    """
    if not os.path.exists(WATCH_FILE):
        return {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "users": {}
        }
    
    with open(WATCH_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Check if migration is needed
    if "schema_version" not in config:
        # Old format detected, migrate
        config = migrate_watch_config_v1_to_v2(config)
    
    return config


def migrate_watch_config_v1_to_v2(old_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Migrate watch config from v1 (old format) to v2 (new format).
    
    Old format:
    {
      "user_id": {
        "source_chat_id": {
          "dest": "dest_chat_id",
          "whitelist": [...],
          "blacklist": [...],
          "preserve_forward_source": bool
        }
      }
    }
    
    New format:
    {
      "schema_version": 2,
      "users": {
        "user_id": {
          "watch_id": {
            "id": "watch_id",
            "source": "source_chat_id",
            "dest": "dest_chat_id",
            "enabled": true,
            "flags": {
              "extract_mode": false,
              "keywords_enabled": true,
              "preserve_source": bool
            },
            "filters": {
              "keywords": [...whitelist + blacklist...],
              "patterns": []
            },
            "_legacy_whitelist": [...],
            "_legacy_blacklist": [...]
          }
        }
      }
    }
    """
    print("Migrating watch config from v1 to v2...")
    
    # Create backup
    if os.path.exists(WATCH_FILE):
        shutil.copy2(WATCH_FILE, WATCH_FILE_BACKUP)
        print(f"Backup created: {WATCH_FILE_BACKUP}")
    
    new_config = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "users": {}
    }
    
    for user_id, watches in old_config.items():
        new_config["users"][user_id] = {}
        
        for source_chat_id, watch_data in watches.items():
            watch_id = generate_watch_id()
            
            # Handle both old dict format and simple string format
            if isinstance(watch_data, dict):
                dest = watch_data.get("dest", "unknown")
                whitelist = watch_data.get("whitelist", [])
                blacklist = watch_data.get("blacklist", [])
                preserve_source = watch_data.get("preserve_forward_source", False)
            else:
                # Very old format: just a destination string
                dest = watch_data
                whitelist = []
                blacklist = []
                preserve_source = False
            
            # Combine whitelist and blacklist into keywords
            # Note: In the new system, we'll need to check if ALL keywords match
            # The old system had whitelist (any match = forward) and blacklist (any match = skip)
            # For now, we'll preserve both separately and handle in the forwarding logic
            all_keywords = list(set(whitelist + blacklist))
            
            new_watch = {
                "id": watch_id,
                "source": source_chat_id,
                "dest": dest,
                "enabled": True,
                "flags": {
                    "extract_mode": False,
                    "keywords_enabled": bool(whitelist or blacklist),
                    "preserve_source": preserve_source
                },
                "filters": {
                    "keywords": all_keywords,
                    "patterns": []
                },
                # Keep legacy info for compatibility
                "_legacy_whitelist": whitelist,
                "_legacy_blacklist": blacklist
            }
            
            new_config["users"][user_id][watch_id] = new_watch
    
    # Save migrated config
    save_watch_config(new_config)
    print(f"Migration complete. Migrated {sum(len(watches) for watches in new_config['users'].values())} watches.")
    
    return new_config


def save_watch_config(config: Dict[str, Any], create_backup: bool = True):
    """Save watch configuration with atomic write and backup"""
    if create_backup and os.path.exists(WATCH_FILE):
        shutil.copy2(WATCH_FILE, WATCH_FILE_BACKUP)
    
    # Write to temporary file first
    temp_file = WATCH_FILE + '.tmp'
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
    
    # Atomic rename
    os.replace(temp_file, WATCH_FILE)


def get_user_watches(config: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Get all watches for a user"""
    return config.get("users", {}).get(user_id, {})


def get_watch_by_id(config: Dict[str, Any], user_id: str, watch_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific watch by ID"""
    user_watches = get_user_watches(config, user_id)
    return user_watches.get(watch_id)


def get_watch_by_source(config: Dict[str, Any], source_chat_id: str) -> Optional[Tuple[str, str, Dict[str, Any]]]:
    """
    Find watch by source chat ID across all users.
    Returns (user_id, watch_id, watch_data) or None
    """
    for user_id, watches in config.get("users", {}).items():
        for watch_id, watch_data in watches.items():
            if watch_data.get("source") == source_chat_id:
                return user_id, watch_id, watch_data
    return None


def add_watch(
    config: Dict[str, Any],
    user_id: str,
    source_chat_id: str,
    dest_chat_id: str,
    extract_mode: bool = False,
    keywords_enabled: bool = True,
    preserve_source: bool = False,
    keywords: Optional[List[str]] = None,
    patterns: Optional[List[str]] = None
) -> Tuple[bool, str, Optional[str]]:
    """
    Add a new watch.
    Returns (success, message, watch_id)
    """
    # Check if source already being watched by this user
    user_watches = get_user_watches(config, user_id)
    for watch_id, watch_data in user_watches.items():
        if watch_data.get("source") == source_chat_id:
            return False, "该来源频道已经在监控中", None
    
    # Generate new watch ID
    watch_id = generate_watch_id()
    
    # Create watch entry
    new_watch = {
        "id": watch_id,
        "source": source_chat_id,
        "dest": dest_chat_id,
        "enabled": True,
        "flags": {
            "extract_mode": extract_mode,
            "keywords_enabled": keywords_enabled,
            "preserve_source": preserve_source
        },
        "filters": {
            "keywords": keywords or [],
            "patterns": patterns or []
        }
    }
    
    # Initialize user if needed
    if "users" not in config:
        config["users"] = {}
    if user_id not in config["users"]:
        config["users"][user_id] = {}
    
    # Add watch
    config["users"][user_id][watch_id] = new_watch
    
    # Save config
    save_watch_config(config)
    
    return True, "监控任务添加成功", watch_id


def remove_watch(config: Dict[str, Any], user_id: str, watch_id: str) -> Tuple[bool, str]:
    """
    Remove a watch.
    Returns (success, message)
    """
    user_watches = get_user_watches(config, user_id)
    
    if watch_id not in user_watches:
        return False, "找不到该监控任务"
    
    # Remove watch
    del config["users"][user_id][watch_id]
    
    # Clean up empty user entry
    if not config["users"][user_id]:
        del config["users"][user_id]
    
    # Save config
    save_watch_config(config)
    
    return True, "监控任务已删除"


def update_watch_flag(
    config: Dict[str, Any],
    user_id: str,
    watch_id: str,
    flag_name: str,
    value: bool
) -> Tuple[bool, str]:
    """
    Update a watch flag (extract_mode, keywords_enabled, preserve_source).
    Returns (success, message)
    """
    watch = get_watch_by_id(config, user_id, watch_id)
    
    if not watch:
        return False, "找不到该监控任务"
    
    valid_flags = ["extract_mode", "keywords_enabled", "preserve_source"]
    if flag_name not in valid_flags:
        return False, f"无效的标志名称。有效选项: {', '.join(valid_flags)}"
    
    watch["flags"][flag_name] = value
    
    save_watch_config(config)
    
    return True, f"已更新 {flag_name} 为 {value}"


def add_watch_keyword(
    config: Dict[str, Any],
    user_id: str,
    watch_id: str,
    keyword: str
) -> Tuple[bool, str]:
    """
    Add a keyword to a watch.
    Returns (success, message)
    """
    watch = get_watch_by_id(config, user_id, watch_id)
    
    if not watch:
        return False, "找不到该监控任务"
    
    keywords = watch["filters"].get("keywords", [])
    
    if keyword in keywords:
        return False, "关键词已存在"
    
    keywords.append(keyword)
    watch["filters"]["keywords"] = keywords
    
    save_watch_config(config)
    
    return True, f"已添加关键词: {keyword}"


def remove_watch_keyword(
    config: Dict[str, Any],
    user_id: str,
    watch_id: str,
    keyword_or_index: str
) -> Tuple[bool, str]:
    """
    Remove a keyword from a watch (by keyword string or index).
    Returns (success, message)
    """
    watch = get_watch_by_id(config, user_id, watch_id)
    
    if not watch:
        return False, "找不到该监控任务"
    
    keywords = watch["filters"].get("keywords", [])
    
    if not keywords:
        return False, "该监控任务没有关键词"
    
    # Try as index first
    try:
        index = int(keyword_or_index)
        if 1 <= index <= len(keywords):
            removed = keywords.pop(index - 1)
            watch["filters"]["keywords"] = keywords
            save_watch_config(config)
            return True, f"已删除关键词: {removed}"
        else:
            return False, f"索引超出范围 (1-{len(keywords)})"
    except ValueError:
        # Not an index, try as keyword string
        if keyword_or_index in keywords:
            keywords.remove(keyword_or_index)
            watch["filters"]["keywords"] = keywords
            save_watch_config(config)
            return True, f"已删除关键词: {keyword_or_index}"
        else:
            return False, "找不到该关键词"


def add_watch_pattern(
    config: Dict[str, Any],
    user_id: str,
    watch_id: str,
    pattern: str
) -> Tuple[bool, str]:
    """
    Add a regex pattern to a watch.
    Returns (success, message)
    """
    watch = get_watch_by_id(config, user_id, watch_id)
    
    if not watch:
        return False, "找不到该监控任务"
    
    patterns = watch["filters"].get("patterns", [])
    
    # Check limits
    if len(pattern) > MAX_PATTERN_LENGTH:
        return False, f"模式太长 (最大 {MAX_PATTERN_LENGTH} 字符)"
    
    if len(patterns) >= MAX_PATTERN_COUNT:
        return False, f"已达到最大模式数量 (最大 {MAX_PATTERN_COUNT})"
    
    if pattern in patterns:
        return False, "模式已存在"
    
    # Try to compile the pattern to validate it
    compiled = compile_pattern_list([pattern])
    if compiled and compiled[0][2]:  # Has error
        return False, f"无效的正则表达式: {compiled[0][2]}"
    
    patterns.append(pattern)
    watch["filters"]["patterns"] = patterns
    
    save_watch_config(config)
    
    return True, f"已添加正则表达式模式: {pattern}"


def remove_watch_pattern(
    config: Dict[str, Any],
    user_id: str,
    watch_id: str,
    pattern_or_index: str
) -> Tuple[bool, str]:
    """
    Remove a regex pattern from a watch (by pattern string or index).
    Returns (success, message)
    """
    watch = get_watch_by_id(config, user_id, watch_id)
    
    if not watch:
        return False, "找不到该监控任务"
    
    patterns = watch["filters"].get("patterns", [])
    
    if not patterns:
        return False, "该监控任务没有正则表达式模式"
    
    # Try as index first
    try:
        index = int(pattern_or_index)
        if 1 <= index <= len(patterns):
            removed = patterns.pop(index - 1)
            watch["filters"]["patterns"] = patterns
            save_watch_config(config)
            return True, f"已删除模式: {removed}"
        else:
            return False, f"索引超出范围 (1-{len(patterns)})"
    except ValueError:
        # Not an index, try as pattern string
        if pattern_or_index in patterns:
            patterns.remove(pattern_or_index)
            watch["filters"]["patterns"] = patterns
            save_watch_config(config)
            return True, f"已删除模式: {pattern_or_index}"
        else:
            return False, "找不到该模式"


def validate_watch_config(config: Dict[str, Any]) -> List[str]:
    """
    Validate watch configuration.
    Returns list of error messages (empty if valid).
    """
    errors = []
    
    if "schema_version" not in config:
        errors.append("Missing schema_version")
    
    if "users" not in config:
        errors.append("Missing users field")
        return errors
    
    for user_id, watches in config["users"].items():
        if not isinstance(watches, dict):
            errors.append(f"User {user_id}: watches must be a dict")
            continue
        
        for watch_id, watch_data in watches.items():
            prefix = f"Watch {watch_id}"
            
            if "id" not in watch_data:
                errors.append(f"{prefix}: missing id")
            if "source" not in watch_data:
                errors.append(f"{prefix}: missing source")
            if "dest" not in watch_data:
                errors.append(f"{prefix}: missing dest")
            if "enabled" not in watch_data:
                errors.append(f"{prefix}: missing enabled")
            if "flags" not in watch_data:
                errors.append(f"{prefix}: missing flags")
            if "filters" not in watch_data:
                errors.append(f"{prefix}: missing filters")
            
            # Validate filters
            if "filters" in watch_data:
                filters = watch_data["filters"]
                if "keywords" in filters and len(filters["keywords"]) > 1000:
                    errors.append(f"{prefix}: too many keywords")
                if "patterns" in filters:
                    if len(filters["patterns"]) > MAX_PATTERN_COUNT:
                        errors.append(f"{prefix}: too many patterns")
                    for pattern in filters["patterns"]:
                        if len(pattern) > MAX_PATTERN_LENGTH:
                            errors.append(f"{prefix}: pattern too long: {pattern[:50]}...")
    
    return errors
