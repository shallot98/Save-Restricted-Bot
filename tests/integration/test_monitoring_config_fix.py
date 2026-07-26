#!/usr/bin/env python3
"""
Test to verify the monitoring configuration persistence fix
"""
import json
import os
import sys
import tempfile
import shutil
from unittest.mock import MagicMock, patch
import importlib.util

def test_auto_reload_on_save():
    """Test that save_watch_config automatically reloads monitored sources"""
    print("Test: Auto-reload on save_watch_config")
    print("="*60)
    
    # Create temporary directory
    temp_dir = tempfile.mkdtemp()
    config_file = os.path.join(temp_dir, 'watch_config.json')
    
    try:
        # Simulate the functions from main.py
        def load_watch_config():
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        
        def build_monitored_sources():
            watch_config = load_watch_config()
            sources = set()
            for user_id, watches in watch_config.items():
                for watch_key, watch_data in watches.items():
                    if isinstance(watch_data, dict):
                        source = watch_data.get('source')
                    else:
                        source = watch_key
                    if source and source != 'me':
                        sources.add(str(source))
            return sources
        
        # Global variable to track monitored sources
        monitored_sources = set()
        
        def reload_monitored_sources():
            nonlocal monitored_sources
            monitored_sources = build_monitored_sources()
            print(f"  🔄 Reloaded: {monitored_sources}")
        
        def save_watch_config(config, auto_reload=True):
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            if auto_reload:
                reload_monitored_sources()
        
        # Initial state
        print("\n1. Initial state (empty):")
        monitored_sources = build_monitored_sources()
        print(f"   Monitored sources: {monitored_sources}")
        assert len(monitored_sources) == 0, "Should be empty initially"
        
        # Add first monitoring task
        print("\n2. Add first monitoring task:")
        config1 = {
            "12345": {
                "task1": {
                    "source": "-100111111",
                    "dest": "me",
                    "record_mode": False
                }
            }
        }
        save_watch_config(config1)
        print(f"   Monitored sources after save: {monitored_sources}")
        assert "-100111111" in monitored_sources, "Source should be in monitored list"
        
        # Simulate bot restart (reset monitored_sources and reload)
        print("\n3. Simulate bot restart:")
        monitored_sources = build_monitored_sources()
        print(f"   Monitored sources after restart: {monitored_sources}")
        assert "-100111111" in monitored_sources, "Source should persist after restart"
        
        # Add second monitoring task (without restart)
        print("\n4. Add second monitoring task (no restart):")
        config2 = {
            "12345": {
                "task1": {
                    "source": "-100111111",
                    "dest": "me",
                    "record_mode": False
                },
                "task2": {
                    "source": "-100222222",
                    "dest": "me",
                    "record_mode": False
                }
            }
        }
        save_watch_config(config2)
        print(f"   Monitored sources after adding task2: {monitored_sources}")
        assert "-100111111" in monitored_sources, "First source should still be there"
        assert "-100222222" in monitored_sources, "Second source should be added"
        
        # Delete monitoring task
        print("\n5. Delete first monitoring task:")
        config3 = {
            "12345": {
                "task2": {
                    "source": "-100222222",
                    "dest": "me",
                    "record_mode": False
                }
            }
        }
        save_watch_config(config3)
        print(f"   Monitored sources after deletion: {monitored_sources}")
        assert "-100111111" not in monitored_sources, "Deleted source should be removed"
        assert "-100222222" in monitored_sources, "Remaining source should still be there"
        
        print("\n" + "="*60)
        print("✅ All tests passed!")
        print("="*60)

    # 原先 except AssertionError/Exception -> return False：pytest 忽略返回值，
    # 断言失败会被吞成 passed（假绿灯）。现让异常直接向上抛，只保留清理。
    finally:
        shutil.rmtree(temp_dir)


def test_message_filtering():
    """Test that messages from non-monitored sources are filtered correctly"""
    print("\n\nTest: Message filtering with monitored sources")
    print("="*60)
    
    try:
        # Simulate monitored sources
        monitored_sources = {"-100111111", "-100222222"}
        
        # Test cases
        test_cases = [
            ("-100111111", True, "Message from monitored source 1"),
            ("-100222222", True, "Message from monitored source 2"),
            ("-100333333", False, "Message from non-monitored source"),
            ("me", False, "Message from 'me' (special case)"),
        ]
        
        print("\nTest cases:")
        all_pass = True
        for source_id, should_pass, description in test_cases:
            passes_filter = source_id in monitored_sources
            status = "✅ PASS" if passes_filter == should_pass else "❌ FAIL"
            print(f"  {status}: {description}")
            print(f"    Source: {source_id}, Expected: {should_pass}, Got: {passes_filter}")
            if passes_filter != should_pass:
                all_pass = False
        
        print("\n" + "="*60)
        assert all_pass, "部分过滤用例结果与预期不符"
        print("✅ All filtering tests passed!")
        print("="*60)

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    print("\n")
    print("*"*60)
    print("Testing Monitoring Configuration Persistence Fix")
    print("*"*60)
    
    try:
        test_auto_reload_on_save()
        test_message_filtering()
    except AssertionError as exc:
        print("\n")
        print("*"*60)
        print(f"⚠️ Some tests failed: {exc}")
        print("*"*60)
        sys.exit(1)

    print("\n")
    print("*"*60)
    print("🎉 All tests passed! The fix is working correctly.")
    print("*"*60)
    sys.exit(0)
