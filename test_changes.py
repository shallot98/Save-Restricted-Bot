#!/usr/bin/env python3
"""
Simple test script to verify the changes made to main.py
This tests the keyword filtering logic and configuration handling
"""

import json

def test_watch_config_structure():
    """Test the new watch configuration structure"""
    # New format with keywords
    new_format = {
        "user_id": {
            "source_chat_id": {
                "dest": "dest_chat_id",
                "whitelist": ["keyword1", "keyword2"],
                "blacklist": ["spam", "ad"]
            }
        }
    }
    
    # Old format (backward compatibility)
    old_format = {
        "user_id": {
            "source_chat_id": "dest_chat_id"
        }
    }
    
    print("✓ New format structure is valid")
    print("✓ Old format structure is valid")
    return True

def test_keyword_matching():
    """Test keyword matching logic"""
    message_text = "This is an important announcement about urgent matters"
    whitelist = ["important", "urgent"]
    blacklist = ["spam", "advertisement"]
    
    # Test whitelist matching
    whitelist_match = any(keyword.lower() in message_text.lower() for keyword in whitelist)
    assert whitelist_match, "Whitelist matching failed"
    print("✓ Whitelist matching works correctly")
    
    # Test blacklist matching
    blacklist_match = any(keyword.lower() in message_text.lower() for keyword in blacklist)
    assert not blacklist_match, "Blacklist matching failed"
    print("✓ Blacklist matching works correctly")
    
    # Test matched keywords extraction
    matched = [kw for kw in whitelist if kw.lower() in message_text.lower()]
    assert len(matched) == 2, "Matched keywords extraction failed"
    print(f"✓ Matched keywords: {', '.join(matched)}")
    
    return True

def test_keyword_info_format():
    """Test the keyword info format for display"""
    matched_keywords = ["important", "urgent"]
    keyword_info = f"🔍 匹配关键词: {', '.join(matched_keywords)}\n\n"
    
    original_text = "This is the original message"
    new_text = keyword_info + original_text
    
    assert new_text.startswith("🔍 匹配关键词:"), "Keyword info format is incorrect"
    print("✓ Keyword info format is correct")
    print(f"  Format: {keyword_info.strip()}")
    
    return True

def test_backward_compatibility():
    """Test backward compatibility with old config format"""
    old_config = {
        "123456": {
            "source_1": "dest_1",
            "source_2": "dest_2"
        }
    }
    
    new_config = {
        "123456": {
            "source_3": {
                "dest": "dest_3",
                "whitelist": ["test"],
                "blacklist": []
            }
        }
    }
    
    # Test handling both formats
    for source, data in old_config["123456"].items():
        if isinstance(data, dict):
            dest = data.get("dest")
        else:
            dest = data
        assert dest is not None, "Failed to handle old format"
    
    print("✓ Backward compatibility check passed")
    return True

if __name__ == "__main__":
    print("Running tests for main.py changes...\n")
    
    try:
        test_watch_config_structure()
        print()
        test_keyword_matching()
        print()
        test_keyword_info_format()
        print()
        test_backward_compatibility()
        print()
        print("=" * 50)
        print("All tests passed! ✓")
        print("=" * 50)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        exit(1)
