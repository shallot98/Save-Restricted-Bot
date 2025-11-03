"""
Unit tests for watch config v3 functionality
"""

import os
import json
import sys
import tempfile
import shutil
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from watch_manager import (
    load_watch_config,
    save_watch_config,
    add_watch,
    get_user_watches,
    get_watch_by_id,
    get_watch_by_source,
    update_watch_forward_mode,
    update_watch_preserve_source,
    update_watch_enabled,
    add_watch_keyword,
    add_watch_pattern,
    remove_watch_keyword,
    remove_watch_pattern,
    migrate_watch_config_v2_to_v3,
    WATCH_FILE
)


class TestWatchV3:
    def setup_method(self):
        """Setup test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.original_watch_file = WATCH_FILE
        # Patch WATCH_FILE to use temp directory
        import watch_manager
        watch_manager.WATCH_FILE = os.path.join(self.test_dir, 'watch_config.json')
        watch_manager.WATCH_FILE_BACKUP = os.path.join(self.test_dir, 'watch_config.json.backup')
    
    def teardown_method(self):
        """Cleanup test environment"""
        shutil.rmtree(self.test_dir, ignore_errors=True)
        # Restore original
        import watch_manager
        watch_manager.WATCH_FILE = self.original_watch_file
    
    def test_add_watch_v3(self):
        """Test adding a watch with v3 format"""
        config = load_watch_config()
        
        success, msg, watch_id = add_watch(
            config,
            user_id="123456",
            source_chat_id="-1001234567890",
            dest_chat_id="me",
            source_type="channel",
            source_title="Test Channel",
            forward_mode="full",
            preserve_source=False,
            monitor_keywords=["test", "important"],
            monitor_patterns=["/urgent/i"],
            extract_keywords=[],
            extract_patterns=[]
        )
        
        assert success, f"Failed to add watch: {msg}"
        assert watch_id is not None
        
        # Verify watch data
        config = load_watch_config()
        watch = get_watch_by_id(config, "123456", watch_id)
        
        assert watch is not None
        assert watch["forward_mode"] == "full"
        assert watch["source"]["id"] == "-1001234567890"
        assert watch["source"]["type"] == "channel"
        assert watch["source"]["title"] == "Test Channel"
        assert watch["target_chat_id"] == "me"
        assert watch["preserve_source"] == False
        assert watch["enabled"] == True
        
        # Check filters
        assert "monitor_filters" in watch
        assert "extract_filters" in watch
        assert watch["monitor_filters"]["keywords"] == ["test", "important"]
        assert watch["monitor_filters"]["patterns"] == ["/urgent/i"]
        assert watch["extract_filters"]["keywords"] == []
        assert watch["extract_filters"]["patterns"] == []
        
        print("✅ test_add_watch_v3 passed")
    
    def test_forward_mode_mutually_exclusive(self):
        """Test that forward mode is properly set and can be toggled"""
        config = load_watch_config()
        
        # Add watch in full mode
        success, msg, watch_id = add_watch(
            config,
            user_id="123456",
            source_chat_id="-1001234567890",
            dest_chat_id="me",
            source_type="channel",
            source_title="Test Channel",
            forward_mode="full"
        )
        
        assert success
        
        # Verify full mode
        config = load_watch_config()
        watch = get_watch_by_id(config, "123456", watch_id)
        assert watch["forward_mode"] == "full"
        
        # Switch to extract mode
        success, msg = update_watch_forward_mode(config, "123456", watch_id, "extract")
        assert success
        
        # Verify extract mode
        config = load_watch_config()
        watch = get_watch_by_id(config, "123456", watch_id)
        assert watch["forward_mode"] == "extract"
        
        # Try invalid mode
        success, msg = update_watch_forward_mode(config, "123456", watch_id, "invalid")
        assert not success
        
        print("✅ test_forward_mode_mutually_exclusive passed")
    
    def test_separate_filter_sets(self):
        """Test that monitor and extract filters are separate"""
        config = load_watch_config()
        
        success, msg, watch_id = add_watch(
            config,
            user_id="123456",
            source_chat_id="-1001234567890",
            dest_chat_id="me",
            source_type="channel",
            source_title="Test Channel",
            forward_mode="full"
        )
        
        assert success
        
        # Add monitor keyword
        success, msg = add_watch_keyword(config, "123456", watch_id, "monitor_kw", "monitor")
        assert success, f"Failed to add monitor keyword: {msg}"
        
        # Add extract keyword
        success, msg = add_watch_keyword(config, "123456", watch_id, "extract_kw", "extract")
        assert success, f"Failed to add extract keyword: {msg}"
        
        # Add monitor pattern
        success, msg = add_watch_pattern(config, "123456", watch_id, "/monitor/i", "monitor")
        assert success, f"Failed to add monitor pattern: {msg}"
        
        # Add extract pattern
        success, msg = add_watch_pattern(config, "123456", watch_id, "/extract/i", "extract")
        assert success, f"Failed to add extract pattern: {msg}"
        
        # Verify separation
        config = load_watch_config()
        watch = get_watch_by_id(config, "123456", watch_id)
        
        assert "monitor_kw" in watch["monitor_filters"]["keywords"]
        assert "extract_kw" in watch["extract_filters"]["keywords"]
        assert "monitor_kw" not in watch["extract_filters"]["keywords"]
        assert "extract_kw" not in watch["monitor_filters"]["keywords"]
        
        assert "/monitor/i" in watch["monitor_filters"]["patterns"]
        assert "/extract/i" in watch["extract_filters"]["patterns"]
        assert "/monitor/i" not in watch["extract_filters"]["patterns"]
        assert "/extract/i" not in watch["monitor_filters"]["patterns"]
        
        print("✅ test_separate_filter_sets passed")
    
    def test_source_types(self):
        """Test that different source types are supported"""
        config = load_watch_config()
        
        # Test channel
        success, msg, watch_id1 = add_watch(
            config, "123456", "-1001111111111", "me",
            source_type="channel", source_title="Channel"
        )
        assert success
        
        # Test supergroup
        success, msg, watch_id2 = add_watch(
            config, "123456", "-1001111111112", "me",
            source_type="supergroup", source_title="Supergroup"
        )
        assert success
        
        # Test group
        success, msg, watch_id3 = add_watch(
            config, "123456", "-1111111113", "me",
            source_type="group", source_title="Group"
        )
        assert success
        
        # Verify all types
        config = load_watch_config()
        watch1 = get_watch_by_id(config, "123456", watch_id1)
        watch2 = get_watch_by_id(config, "123456", watch_id2)
        watch3 = get_watch_by_id(config, "123456", watch_id3)
        
        assert watch1["source"]["type"] == "channel"
        assert watch2["source"]["type"] == "supergroup"
        assert watch3["source"]["type"] == "group"
        
        print("✅ test_source_types passed")
    
    def test_v2_to_v3_migration(self):
        """Test migration from v2 to v3 format"""
        # Create v2 config
        v2_config = {
            "schema_version": 2,
            "users": {
                "123456": {
                    "watch-id-1": {
                        "id": "watch-id-1",
                        "source": "-1001234567890",
                        "dest": "me",
                        "enabled": True,
                        "flags": {
                            "extract_mode": False,
                            "keywords_enabled": True,
                            "preserve_source": False
                        },
                        "filters": {
                            "keywords": ["test", "important"],
                            "patterns": ["/urgent/i"]
                        }
                    },
                    "watch-id-2": {
                        "id": "watch-id-2",
                        "source": "-1001234567891",
                        "dest": "me",
                        "enabled": True,
                        "flags": {
                            "extract_mode": True,
                            "keywords_enabled": True,
                            "preserve_source": True
                        },
                        "filters": {
                            "keywords": ["extract"],
                            "patterns": ["/pattern/i"]
                        }
                    }
                }
            }
        }
        
        # Migrate
        v3_config = migrate_watch_config_v2_to_v3(v2_config)
        
        # Verify v3 structure
        assert v3_config["schema_version"] == 3
        
        watch1 = v3_config["users"]["123456"]["watch-id-1"]
        assert watch1["forward_mode"] == "full"
        assert watch1["preserve_source"] == False
        assert "monitor_filters" in watch1
        assert "extract_filters" in watch1
        assert watch1["monitor_filters"]["keywords"] == ["test", "important"]
        assert watch1["monitor_filters"]["patterns"] == ["/urgent/i"]
        
        watch2 = v3_config["users"]["123456"]["watch-id-2"]
        assert watch2["forward_mode"] == "extract"
        assert watch2["preserve_source"] == True
        assert watch2["extract_filters"]["keywords"] == ["extract"]
        assert watch2["extract_filters"]["patterns"] == ["/pattern/i"]
        
        print("✅ test_v2_to_v3_migration passed")
    
    def test_enable_disable_watch(self):
        """Test enabling and disabling watches"""
        config = load_watch_config()
        
        success, msg, watch_id = add_watch(
            config, "123456", "-1001234567890", "me",
            source_type="channel", source_title="Test"
        )
        assert success
        
        # Verify enabled by default
        config = load_watch_config()
        watch = get_watch_by_id(config, "123456", watch_id)
        assert watch["enabled"] == True
        
        # Disable
        success, msg = update_watch_enabled(config, "123456", watch_id, False)
        assert success
        
        config = load_watch_config()
        watch = get_watch_by_id(config, "123456", watch_id)
        assert watch["enabled"] == False
        
        # Re-enable
        success, msg = update_watch_enabled(config, "123456", watch_id, True)
        assert success
        
        config = load_watch_config()
        watch = get_watch_by_id(config, "123456", watch_id)
        assert watch["enabled"] == True
        
        print("✅ test_enable_disable_watch passed")


def run_tests():
    """Run all tests"""
    test = TestWatchV3()
    
    tests = [
        test.test_add_watch_v3,
        test.test_forward_mode_mutually_exclusive,
        test.test_separate_filter_sets,
        test.test_source_types,
        test.test_v2_to_v3_migration,
        test.test_enable_disable_watch
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            test.setup_method()
            test_func()
            test.teardown_method()
            passed += 1
        except Exception as e:
            print(f"❌ {test_func.__name__} failed: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
            test.teardown_method()
    
    print(f"\n{'='*50}")
    print(f"Tests passed: {passed}/{len(tests)}")
    print(f"Tests failed: {failed}/{len(tests)}")
    print(f"{'='*50}")
    
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
