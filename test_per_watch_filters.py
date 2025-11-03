#!/usr/bin/env python3
"""
Test script for per-watch filters and settings
"""

import os
import sys
import json
import uuid

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from watch_manager import (
    load_watch_config,
    save_watch_config,
    migrate_watch_config_v1_to_v2,
    get_user_watches,
    get_watch_by_id,
    get_watch_by_source,
    add_watch,
    remove_watch,
    update_watch_flag,
    add_watch_keyword,
    remove_watch_keyword,
    add_watch_pattern,
    remove_watch_pattern,
    validate_watch_config,
    WATCH_FILE,
    WATCH_FILE_BACKUP,
    CURRENT_SCHEMA_VERSION
)

from regex_filters import compile_pattern_list, extract_matches


def cleanup_test_files():
    """Clean up test configuration files"""
    for filename in [WATCH_FILE, WATCH_FILE_BACKUP, WATCH_FILE + '.tmp']:
        if os.path.exists(filename):
            os.remove(filename)


def test_new_config_structure():
    """Test new watch config structure"""
    print("Testing new config structure...")
    
    cleanup_test_files()
    
    # Create new config
    config = load_watch_config()
    assert config["schema_version"] == CURRENT_SCHEMA_VERSION
    assert "users" in config
    assert config["users"] == {}
    
    print("✓ New config structure is correct")
    return True


def test_add_watch():
    """Test adding a watch"""
    print("\nTesting add_watch...")
    
    cleanup_test_files()
    
    config = load_watch_config()
    user_id = "123456"
    source_id = "-100123456789"
    dest_id = "me"
    
    # Add watch
    success, msg, watch_id = add_watch(
        config, user_id, source_id, dest_id,
        extract_mode=True,
        keywords_enabled=True,
        preserve_source=False,
        keywords=["test", "important"],
        patterns=["/urgent/i"]
    )
    
    assert success
    assert watch_id is not None
    
    # Verify watch was added
    user_watches = get_user_watches(config, user_id)
    assert len(user_watches) == 1
    assert watch_id in user_watches
    
    watch = user_watches[watch_id]
    assert watch["source"] == source_id
    assert watch["dest"] == dest_id
    assert watch["enabled"] == True
    assert watch["flags"]["extract_mode"] == True
    assert watch["flags"]["keywords_enabled"] == True
    assert watch["flags"]["preserve_source"] == False
    assert "test" in watch["filters"]["keywords"]
    assert "important" in watch["filters"]["keywords"]
    assert "/urgent/i" in watch["filters"]["patterns"]
    
    print("✓ Add watch works correctly")
    return True


def test_duplicate_watch():
    """Test adding duplicate watch (same source)"""
    print("\nTesting duplicate watch...")
    
    cleanup_test_files()
    
    config = load_watch_config()
    user_id = "123456"
    source_id = "-100123456789"
    dest_id = "me"
    
    # Add first watch
    success1, msg1, watch_id1 = add_watch(config, user_id, source_id, dest_id)
    assert success1
    
    # Try to add duplicate
    success2, msg2, watch_id2 = add_watch(config, user_id, source_id, dest_id)
    assert not success2
    assert "已经在监控中" in msg2
    
    print("✓ Duplicate watch detection works")
    return True


def test_remove_watch():
    """Test removing a watch"""
    print("\nTesting remove_watch...")
    
    cleanup_test_files()
    
    config = load_watch_config()
    user_id = "123456"
    source_id = "-100123456789"
    dest_id = "me"
    
    # Add and then remove watch
    success1, msg1, watch_id = add_watch(config, user_id, source_id, dest_id)
    assert success1
    
    config = load_watch_config()  # Reload
    success2, msg2 = remove_watch(config, user_id, watch_id)
    assert success2
    
    # Verify watch was removed
    config = load_watch_config()
    user_watches = get_user_watches(config, user_id)
    assert len(user_watches) == 0
    
    print("✓ Remove watch works correctly")
    return True


def test_update_watch_flag():
    """Test updating watch flags"""
    print("\nTesting update_watch_flag...")
    
    cleanup_test_files()
    
    config = load_watch_config()
    user_id = "123456"
    source_id = "-100123456789"
    dest_id = "me"
    
    # Add watch with default flags
    success, msg, watch_id = add_watch(config, user_id, source_id, dest_id)
    assert success
    
    # Update extract_mode
    config = load_watch_config()
    success, msg = update_watch_flag(config, user_id, watch_id, "extract_mode", True)
    assert success
    
    # Verify flag was updated
    config = load_watch_config()
    watch = get_watch_by_id(config, user_id, watch_id)
    assert watch["flags"]["extract_mode"] == True
    
    # Update keywords_enabled
    success, msg = update_watch_flag(config, user_id, watch_id, "keywords_enabled", True)
    assert success
    
    config = load_watch_config()
    watch = get_watch_by_id(config, user_id, watch_id)
    assert watch["flags"]["keywords_enabled"] == True
    
    print("✓ Update watch flag works correctly")
    return True


def test_watch_keywords():
    """Test managing watch keywords"""
    print("\nTesting watch keywords...")
    
    cleanup_test_files()
    
    config = load_watch_config()
    user_id = "123456"
    source_id = "-100123456789"
    dest_id = "me"
    
    # Add watch
    success, msg, watch_id = add_watch(config, user_id, source_id, dest_id)
    assert success
    
    # Add keywords
    config = load_watch_config()
    success1, msg1 = add_watch_keyword(config, user_id, watch_id, "urgent")
    assert success1
    
    config = load_watch_config()
    success2, msg2 = add_watch_keyword(config, user_id, watch_id, "important")
    assert success2
    
    # Verify keywords
    config = load_watch_config()
    watch = get_watch_by_id(config, user_id, watch_id)
    keywords = watch["filters"]["keywords"]
    assert "urgent" in keywords
    assert "important" in keywords
    
    # Remove keyword by name
    success3, msg3 = remove_watch_keyword(config, user_id, watch_id, "urgent")
    assert success3
    
    config = load_watch_config()
    watch = get_watch_by_id(config, user_id, watch_id)
    keywords = watch["filters"]["keywords"]
    assert "urgent" not in keywords
    assert "important" in keywords
    
    # Remove keyword by index
    success4, msg4 = remove_watch_keyword(config, user_id, watch_id, "1")
    assert success4
    
    config = load_watch_config()
    watch = get_watch_by_id(config, user_id, watch_id)
    keywords = watch["filters"]["keywords"]
    assert len(keywords) == 0
    
    print("✓ Watch keywords management works correctly")
    return True


def test_watch_patterns():
    """Test managing watch regex patterns"""
    print("\nTesting watch patterns...")
    
    cleanup_test_files()
    
    config = load_watch_config()
    user_id = "123456"
    source_id = "-100123456789"
    dest_id = "me"
    
    # Add watch
    success, msg, watch_id = add_watch(config, user_id, source_id, dest_id)
    assert success
    
    # Add patterns
    config = load_watch_config()
    success1, msg1 = add_watch_pattern(config, user_id, watch_id, "/bitcoin|crypto/i")
    assert success1
    
    config = load_watch_config()
    success2, msg2 = add_watch_pattern(config, user_id, watch_id, r"/\d{3}-\d{4}/")
    assert success2
    
    # Verify patterns
    config = load_watch_config()
    watch = get_watch_by_id(config, user_id, watch_id)
    patterns = watch["filters"]["patterns"]
    assert "/bitcoin|crypto/i" in patterns
    assert r"/\d{3}-\d{4}/" in patterns
    
    # Try to add invalid pattern
    success3, msg3 = add_watch_pattern(config, user_id, watch_id, "[[invalid")
    assert not success3
    assert "无效" in msg3
    
    # Remove pattern by index
    config = load_watch_config()
    success4, msg4 = remove_watch_pattern(config, user_id, watch_id, "1")
    assert success4
    
    config = load_watch_config()
    watch = get_watch_by_id(config, user_id, watch_id)
    patterns = watch["filters"]["patterns"]
    assert len(patterns) == 1
    
    print("✓ Watch patterns management works correctly")
    return True


def test_get_watch_by_source():
    """Test finding watch by source ID"""
    print("\nTesting get_watch_by_source...")
    
    cleanup_test_files()
    
    config = load_watch_config()
    user_id = "123456"
    source_id = "-100123456789"
    dest_id = "me"
    
    # Add watch
    success, msg, watch_id = add_watch(config, user_id, source_id, dest_id)
    assert success
    
    # Find watch by source
    config = load_watch_config()
    result = get_watch_by_source(config, source_id)
    assert result is not None
    
    found_user_id, found_watch_id, found_watch_data = result
    assert found_user_id == user_id
    assert found_watch_id == watch_id
    assert found_watch_data["source"] == source_id
    
    # Try non-existent source
    result2 = get_watch_by_source(config, "-999999999")
    assert result2 is None
    
    print("✓ Get watch by source works correctly")
    return True


def test_migration_v1_to_v2():
    """Test migration from old format to new format"""
    print("\nTesting migration from v1 to v2...")
    
    cleanup_test_files()
    
    # Create old format config
    old_config = {
        "123456": {
            "-100123456789": {
                "dest": "me",
                "whitelist": ["urgent", "important"],
                "blacklist": ["spam"],
                "preserve_forward_source": True
            },
            "-100987654321": "me"  # Very old format (just destination)
        }
    }
    
    # Save old format
    with open(WATCH_FILE, 'w', encoding='utf-8') as f:
        json.dump(old_config, f)
    
    # Load (should trigger migration)
    new_config = load_watch_config()
    
    # Verify migration
    assert new_config["schema_version"] == CURRENT_SCHEMA_VERSION
    assert "users" in new_config
    assert "123456" in new_config["users"]
    
    user_watches = new_config["users"]["123456"]
    assert len(user_watches) == 2
    
    # Check first watch (with whitelist/blacklist)
    watch1 = None
    for watch_id, watch_data in user_watches.items():
        if watch_data["source"] == "-100123456789":
            watch1 = watch_data
            break
    
    assert watch1 is not None
    assert watch1["dest"] == "me"
    assert watch1["flags"]["preserve_source"] == True
    assert watch1["flags"]["keywords_enabled"] == True
    assert "_legacy_whitelist" in watch1
    assert "urgent" in watch1["_legacy_whitelist"]
    assert "_legacy_blacklist" in watch1
    assert "spam" in watch1["_legacy_blacklist"]
    
    # Check second watch (simple format)
    watch2 = None
    for watch_id, watch_data in user_watches.items():
        if watch_data["source"] == "-100987654321":
            watch2 = watch_data
            break
    
    assert watch2 is not None
    assert watch2["dest"] == "me"
    assert watch2["flags"]["keywords_enabled"] == False
    
    # Verify backup was created
    assert os.path.exists(WATCH_FILE_BACKUP)
    
    print("✓ Migration from v1 to v2 works correctly")
    return True


def test_per_watch_filtering():
    """Test per-watch filtering logic"""
    print("\nTesting per-watch filtering...")
    
    # Test message with keywords
    text1 = "This is an urgent message about important matters"
    keywords1 = ["urgent", "important"]
    patterns1 = []
    
    compiled1 = compile_pattern_list(patterns1)
    has_matches1, snippets1 = extract_matches(text1, keywords1, compiled1)
    
    assert has_matches1
    assert len(snippets1) > 0
    
    # Test message without keywords
    text2 = "This is a normal message"
    has_matches2, snippets2 = extract_matches(text2, keywords1, compiled1)
    
    assert not has_matches2
    
    # Test message with regex
    text3 = "Call me at 123-4567 about urgent matter"
    keywords3 = ["urgent"]
    patterns3 = [r"/\d{3}-\d{4}/"]
    
    compiled3 = compile_pattern_list(patterns3)
    has_matches3, snippets3 = extract_matches(text3, keywords3, compiled3)
    
    assert has_matches3
    assert len(snippets3) > 0
    
    print("✓ Per-watch filtering works correctly")
    return True


def test_validate_watch_config():
    """Test watch config validation"""
    print("\nTesting validate_watch_config...")
    
    # Valid config
    valid_config = {
        "schema_version": 2,
        "users": {
            "123456": {
                "watch_id": {
                    "id": "watch_id",
                    "source": "-100123",
                    "dest": "me",
                    "enabled": True,
                    "flags": {
                        "extract_mode": False,
                        "keywords_enabled": False,
                        "preserve_source": False
                    },
                    "filters": {
                        "keywords": [],
                        "patterns": []
                    }
                }
            }
        }
    }
    
    errors = validate_watch_config(valid_config)
    assert len(errors) == 0
    
    # Invalid config - missing fields
    invalid_config = {
        "schema_version": 2,
        "users": {
            "123456": {
                "watch_id": {
                    "id": "watch_id",
                    "source": "-100123"
                    # Missing required fields
                }
            }
        }
    }
    
    errors = validate_watch_config(invalid_config)
    assert len(errors) > 0
    
    print("✓ Config validation works correctly")
    return True


def test_config_persistence():
    """Test that config persists across save/load"""
    print("\nTesting config persistence...")
    
    cleanup_test_files()
    
    # Create and save config
    config1 = load_watch_config()
    user_id = "123456"
    source_id = "-100123456789"
    dest_id = "me"
    
    success, msg, watch_id = add_watch(
        config1, user_id, source_id, dest_id,
        extract_mode=True,
        keywords_enabled=True,
        preserve_source=False,
        keywords=["test"],
        patterns=["/test/i"]
    )
    assert success
    
    # Load config again
    config2 = load_watch_config()
    
    # Verify data persisted
    watch = get_watch_by_id(config2, user_id, watch_id)
    assert watch is not None
    assert watch["source"] == source_id
    assert watch["flags"]["extract_mode"] == True
    assert watch["flags"]["keywords_enabled"] == True
    assert "test" in watch["filters"]["keywords"]
    assert "/test/i" in watch["filters"]["patterns"]
    
    print("✓ Config persistence works correctly")
    return True


if __name__ == "__main__":
    print("Running per-watch filters tests...\n")
    print("=" * 50)
    
    try:
        test_new_config_structure()
        test_add_watch()
        test_duplicate_watch()
        test_remove_watch()
        test_update_watch_flag()
        test_watch_keywords()
        test_watch_patterns()
        test_get_watch_by_source()
        test_migration_v1_to_v2()
        test_per_watch_filtering()
        test_validate_watch_config()
        test_config_persistence()
        
        print("\n" + "=" * 50)
        print("All per-watch filters tests passed! ✓")
        print("=" * 50)
        
        # Cleanup
        cleanup_test_files()
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        
        # Cleanup on failure
        cleanup_test_files()
        
        exit(1)
