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
CURRENT_SCHEMA_VERSION = 3


def generate_watch_id() -> str:
    """Generate a unique watch ID"""
    return str(uuid.uuid4())


def load_watch_config() -> Dict[str, Any]:
    """
    Load watch configuration with automatic migration support.
    Returns config in new format (schema v3).
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
        # Old format detected, migrate v1 -> v2
        config = migrate_watch_config_v1_to_v2(config)
    
    if config.get("schema_version", 0) < 3:
        # Migrate v2 -> v3
        config = migrate_watch_config_v2_to_v3(config)
    
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


def migrate_watch_config_v2_to_v3(old_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Migrate watch config from v2 to v3.
    
    Changes in v3:
    1. Split filters into monitor_filters and extract_filters
    2. Change extract_mode flag to forward_mode ("full" or "extract")
    3. Add source metadata (id, type, title) instead of just source ID
    4. Add target_chat_id field
    
    Old v2 format:
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
              "keywords": [...],
              "patterns": [...]
            }
          }
        }
      }
    }
    
    New v3 format:
    {
      "schema_version": 3,
      "users": {
        "user_id": {
          "watch_id": {
            "id": "watch_id",
            "source": {
              "id": "source_chat_id",
              "type": "channel|supergroup|group",
              "title": "Chat Title"
            },
            "target_chat_id": "dest_chat_id",
            "enabled": true,
            "forward_mode": "full|extract",
            "preserve_source": bool,
            "monitor_filters": {
              "keywords": [...],
              "patterns": [...]
            },
            "extract_filters": {
              "keywords": [...],
              "patterns": [...]
            }
          }
        }
      }
    }
    """
    print("Migrating watch config from v2 to v3...")
    
    # Create backup
    if os.path.exists(WATCH_FILE):
        backup_name = f"{WATCH_FILE_BACKUP}.v2"
        shutil.copy2(WATCH_FILE, backup_name)
        print(f"Backup created: {backup_name}")
    
    new_config = {
        "schema_version": 3,
        "users": {}
    }
    
    for user_id, watches in old_config.get("users", {}).items():
        new_config["users"][user_id] = {}
        
        for watch_id, watch_data in watches.items():
            old_source = watch_data.get("source", "unknown")
            old_dest = watch_data.get("dest", "unknown")
            old_flags = watch_data.get("flags", {})
            old_filters = watch_data.get("filters", {})
            
            # Determine forward_mode from extract_mode flag
            extract_mode = old_flags.get("extract_mode", False)
            forward_mode = "extract" if extract_mode else "full"
            
            # Build new source object (we don't have type/title info yet, will be populated on first message)
            new_source = {
                "id": old_source,
                "type": "channel",  # Default, will be updated dynamically
                "title": "Unknown"  # Default, will be updated dynamically
            }
            
            # In v2, filters were used for both monitoring and extraction
            # In v3, we separate them:
            # - If keywords_enabled was true, copy filters to monitor_filters
            # - If extract_mode was true, copy filters to extract_filters
            keywords_enabled = old_flags.get("keywords_enabled", False)
            old_keywords = old_filters.get("keywords", [])
            old_patterns = old_filters.get("patterns", [])
            
            monitor_filters = {"keywords": [], "patterns": []}
            extract_filters = {"keywords": [], "patterns": []}
            
            if keywords_enabled:
                # Filters were used for monitoring
                monitor_filters = {
                    "keywords": old_keywords[:],
                    "patterns": old_patterns[:]
                }
            
            if extract_mode:
                # Filters were used for extraction
                extract_filters = {
                    "keywords": old_keywords[:],
                    "patterns": old_patterns[:]
                }
            
            new_watch = {
                "id": watch_id,
                "source": new_source,
                "target_chat_id": old_dest,
                "enabled": watch_data.get("enabled", True),
                "forward_mode": forward_mode,
                "preserve_source": old_flags.get("preserve_source", False),
                "monitor_filters": monitor_filters,
                "extract_filters": extract_filters,
                # Keep v2 data for reference
                "_migrated_from_v2": True,
                "_v2_flags": old_flags
            }
            
            # Keep legacy info if present
            if "_legacy_whitelist" in watch_data:
                new_watch["_legacy_whitelist"] = watch_data["_legacy_whitelist"]
            if "_legacy_blacklist" in watch_data:
                new_watch["_legacy_blacklist"] = watch_data["_legacy_blacklist"]
            
            new_config["users"][user_id][watch_id] = new_watch
    
    # Save migrated config
    save_watch_config(new_config)
    total_watches = sum(len(watches) for watches in new_config['users'].values())
    print(f"Migration v2->v3 complete. Migrated {total_watches} watches.")
    
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
            # Support both v2 (source as string) and v3 (source as object) formats
            source = watch_data.get("source")
            if isinstance(source, dict):
                source_id = source.get("id")
            else:
                source_id = source
            
            if source_id == source_chat_id:
                return user_id, watch_id, watch_data
    return None


def add_watch(
    config: Dict[str, Any],
    user_id: str,
    source_chat_id: str,
    dest_chat_id: str,
    source_type: str = "channel",
    source_title: str = "Unknown",
    forward_mode: str = "full",
    preserve_source: bool = False,
    monitor_keywords: Optional[List[str]] = None,
    monitor_patterns: Optional[List[str]] = None,
    extract_keywords: Optional[List[str]] = None,
    extract_patterns: Optional[List[str]] = None
) -> Tuple[bool, str, Optional[str]]:
    """
    Add a new watch (v3 format).
    Returns (success, message, watch_id)
    
    Args:
        forward_mode: "full" or "extract"
        source_type: "channel", "supergroup", or "group"
    """
    # Validate forward_mode
    if forward_mode not in ["full", "extract"]:
        return False, "forward_mode 必须是 'full' 或 'extract'", None
    
    # Check if source already being watched by this user
    user_watches = get_user_watches(config, user_id)
    for watch_id, watch_data in user_watches.items():
        source = watch_data.get("source")
        existing_source_id = source.get("id") if isinstance(source, dict) else source
        if existing_source_id == source_chat_id:
            return False, "该来源频道已经在监控中", None
    
    # Generate new watch ID
    watch_id = generate_watch_id()
    
    # Create watch entry (v3 format)
    new_watch = {
        "id": watch_id,
        "source": {
            "id": source_chat_id,
            "type": source_type,
            "title": source_title
        },
        "target_chat_id": dest_chat_id,
        "enabled": True,
        "forward_mode": forward_mode,
        "preserve_source": preserve_source,
        "monitor_filters": {
            "keywords": monitor_keywords or [],
            "patterns": monitor_patterns or []
        },
        "extract_filters": {
            "keywords": extract_keywords or [],
            "patterns": extract_patterns or []
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


def update_watch_forward_mode(
    config: Dict[str, Any],
    user_id: str,
    watch_id: str,
    mode: str
) -> Tuple[bool, str]:
    """
    Update watch forward mode (v3).
    Returns (success, message)
    
    Args:
        mode: "full" or "extract"
    """
    watch = get_watch_by_id(config, user_id, watch_id)
    
    if not watch:
        return False, "找不到该监控任务"
    
    if mode not in ["full", "extract"]:
        return False, "模式必须是 'full' 或 'extract'"
    
    watch["forward_mode"] = mode
    save_watch_config(config)
    
    return True, f"已更新转发模式为 {mode}"


def update_watch_preserve_source(
    config: Dict[str, Any],
    user_id: str,
    watch_id: str,
    value: bool
) -> Tuple[bool, str]:
    """
    Update watch preserve_source flag (v3).
    Returns (success, message)
    """
    watch = get_watch_by_id(config, user_id, watch_id)
    
    if not watch:
        return False, "找不到该监控任务"
    
    watch["preserve_source"] = value
    save_watch_config(config)
    
    status = "开启" if value else "关闭"
    return True, f"已{status}保留来源"


def update_watch_enabled(
    config: Dict[str, Any],
    user_id: str,
    watch_id: str,
    enabled: bool
) -> Tuple[bool, str]:
    """
    Enable or disable a watch (v3).
    Returns (success, message)
    """
    watch = get_watch_by_id(config, user_id, watch_id)
    
    if not watch:
        return False, "找不到该监控任务"
    
    watch["enabled"] = enabled
    save_watch_config(config)
    
    status = "启用" if enabled else "禁用"
    return True, f"已{status}监控任务"


def update_watch_target(
    config: Dict[str, Any],
    user_id: str,
    watch_id: str,
    target_chat_id: str
) -> Tuple[bool, str]:
    """
    Update watch target chat (v3).
    Returns (success, message)
    """
    watch = get_watch_by_id(config, user_id, watch_id)
    
    if not watch:
        return False, "找不到该监控任务"
    
    watch["target_chat_id"] = target_chat_id
    save_watch_config(config)
    
    return True, f"已更新目标聊天为 {target_chat_id}"


def update_watch_source_info(
    config: Dict[str, Any],
    user_id: str,
    watch_id: str,
    chat_type: str,
    chat_title: str
) -> Tuple[bool, str]:
    """
    Update watch source type and title (v3).
    Called automatically when first message is received.
    Returns (success, message)
    """
    watch = get_watch_by_id(config, user_id, watch_id)
    
    if not watch:
        return False, "找不到该监控任务"
    
    if not isinstance(watch.get("source"), dict):
        return False, "此监控任务使用旧格式"
    
    watch["source"]["type"] = chat_type
    watch["source"]["title"] = chat_title
    save_watch_config(config)
    
    return True, "已更新来源信息"


def add_watch_keyword(
    config: Dict[str, Any],
    user_id: str,
    watch_id: str,
    keyword: str,
    filter_type: str = "monitor"
) -> Tuple[bool, str]:
    """
    Add a keyword to a watch (v3).
    Returns (success, message)
    
    Args:
        filter_type: "monitor" or "extract"
    """
    watch = get_watch_by_id(config, user_id, watch_id)
    
    if not watch:
        return False, "找不到该监控任务"
    
    if filter_type not in ["monitor", "extract"]:
        return False, "filter_type 必须是 'monitor' 或 'extract'"
    
    # Support both v2 and v3 formats
    if "filters" in watch:
        # v2 format
        keywords = watch["filters"].get("keywords", [])
        if keyword in keywords:
            return False, "关键词已存在"
        keywords.append(keyword)
        watch["filters"]["keywords"] = keywords
    else:
        # v3 format
        filter_key = f"{filter_type}_filters"
        if filter_key not in watch:
            watch[filter_key] = {"keywords": [], "patterns": []}
        
        keywords = watch[filter_key].get("keywords", [])
        if keyword in keywords:
            return False, "关键词已存在"
        keywords.append(keyword)
        watch[filter_key]["keywords"] = keywords
    
    save_watch_config(config)
    
    filter_name = "监控过滤器" if filter_type == "monitor" else "提取过滤器"
    return True, f"已添加关键词到{filter_name}: {keyword}"


def remove_watch_keyword(
    config: Dict[str, Any],
    user_id: str,
    watch_id: str,
    keyword_or_index: str,
    filter_type: str = "monitor"
) -> Tuple[bool, str]:
    """
    Remove a keyword from a watch (by keyword string or index) (v3).
    Returns (success, message)
    
    Args:
        filter_type: "monitor" or "extract"
    """
    watch = get_watch_by_id(config, user_id, watch_id)
    
    if not watch:
        return False, "找不到该监控任务"
    
    if filter_type not in ["monitor", "extract"]:
        return False, "filter_type 必须是 'monitor' 或 'extract'"
    
    # Support both v2 and v3 formats
    if "filters" in watch:
        # v2 format
        keywords = watch["filters"].get("keywords", [])
    else:
        # v3 format
        filter_key = f"{filter_type}_filters"
        keywords = watch.get(filter_key, {}).get("keywords", [])
    
    if not keywords:
        filter_name = "监控过滤器" if filter_type == "monitor" else "提取过滤器"
        return False, f"{filter_name}没有关键词"
    
    # Try as index first
    try:
        index = int(keyword_or_index)
        if 1 <= index <= len(keywords):
            removed = keywords.pop(index - 1)
            if "filters" in watch:
                watch["filters"]["keywords"] = keywords
            else:
                filter_key = f"{filter_type}_filters"
                watch[filter_key]["keywords"] = keywords
            save_watch_config(config)
            return True, f"已删除关键词: {removed}"
        else:
            return False, f"索引超出范围 (1-{len(keywords)})"
    except ValueError:
        # Not an index, try as keyword string
        if keyword_or_index in keywords:
            keywords.remove(keyword_or_index)
            if "filters" in watch:
                watch["filters"]["keywords"] = keywords
            else:
                filter_key = f"{filter_type}_filters"
                watch[filter_key]["keywords"] = keywords
            save_watch_config(config)
            return True, f"已删除关键词: {keyword_or_index}"
        else:
            return False, "找不到该关键词"


def add_watch_pattern(
    config: Dict[str, Any],
    user_id: str,
    watch_id: str,
    pattern: str,
    filter_type: str = "monitor"
) -> Tuple[bool, str]:
    """
    Add a regex pattern to a watch (v3).
    Returns (success, message)
    
    Args:
        filter_type: "monitor" or "extract"
    """
    watch = get_watch_by_id(config, user_id, watch_id)
    
    if not watch:
        return False, "找不到该监控任务"
    
    if filter_type not in ["monitor", "extract"]:
        return False, "filter_type 必须是 'monitor' 或 'extract'"
    
    # Support both v2 and v3 formats
    if "filters" in watch:
        # v2 format
        patterns = watch["filters"].get("patterns", [])
    else:
        # v3 format
        filter_key = f"{filter_type}_filters"
        if filter_key not in watch:
            watch[filter_key] = {"keywords": [], "patterns": []}
        patterns = watch[filter_key].get("patterns", [])
    
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
    if "filters" in watch:
        watch["filters"]["patterns"] = patterns
    else:
        filter_key = f"{filter_type}_filters"
        watch[filter_key]["patterns"] = patterns
    
    save_watch_config(config)
    
    filter_name = "监控过滤器" if filter_type == "monitor" else "提取过滤器"
    return True, f"已添加正则表达式模式到{filter_name}: {pattern}"


def remove_watch_pattern(
    config: Dict[str, Any],
    user_id: str,
    watch_id: str,
    pattern_or_index: str,
    filter_type: str = "monitor"
) -> Tuple[bool, str]:
    """
    Remove a regex pattern from a watch (by pattern string or index) (v3).
    Returns (success, message)
    
    Args:
        filter_type: "monitor" or "extract"
    """
    watch = get_watch_by_id(config, user_id, watch_id)
    
    if not watch:
        return False, "找不到该监控任务"
    
    if filter_type not in ["monitor", "extract"]:
        return False, "filter_type 必须是 'monitor' 或 'extract'"
    
    # Support both v2 and v3 formats
    if "filters" in watch:
        # v2 format
        patterns = watch["filters"].get("patterns", [])
    else:
        # v3 format
        filter_key = f"{filter_type}_filters"
        patterns = watch.get(filter_key, {}).get("patterns", [])
    
    if not patterns:
        filter_name = "监控过滤器" if filter_type == "monitor" else "提取过滤器"
        return False, f"{filter_name}没有正则表达式模式"
    
    # Try as index first
    try:
        index = int(pattern_or_index)
        if 1 <= index <= len(patterns):
            removed = patterns.pop(index - 1)
            if "filters" in watch:
                watch["filters"]["patterns"] = patterns
            else:
                filter_key = f"{filter_type}_filters"
                watch[filter_key]["patterns"] = patterns
            save_watch_config(config)
            return True, f"已删除模式: {removed}"
        else:
            return False, f"索引超出范围 (1-{len(patterns)})"
    except ValueError:
        # Not an index, try as pattern string
        if pattern_or_index in patterns:
            patterns.remove(pattern_or_index)
            if "filters" in watch:
                watch["filters"]["patterns"] = patterns
            else:
                filter_key = f"{filter_type}_filters"
                watch[filter_key]["patterns"] = patterns
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
