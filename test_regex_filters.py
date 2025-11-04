#!/usr/bin/env python3
"""
Test script for regex-based keyword monitoring functionality
"""

import re
import json
import os
import sys

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_parse_regex_pattern():
    """Test regex pattern parsing with flags"""
    from regex_filters import parse_regex_pattern
    
    print("Testing parse_regex_pattern...")
    
    # Test default case-insensitive
    pattern, flags = parse_regex_pattern("test")
    assert pattern == "test"
    assert flags & re.IGNORECASE
    print("✓ Default case-insensitive works")
    
    # Test /pattern/i format
    pattern, flags = parse_regex_pattern("/test/i")
    assert pattern == "test"
    assert flags & re.IGNORECASE
    print("✓ /pattern/i format works")
    
    # Test multiple flags
    pattern, flags = parse_regex_pattern("/test/im")
    assert pattern == "test"
    assert flags & re.IGNORECASE
    assert flags & re.MULTILINE
    print("✓ Multiple flags work")
    
    # Test pattern with / inside
    pattern, flags = parse_regex_pattern("/http://test/i")
    assert pattern == "http://test"
    assert flags & re.IGNORECASE
    print("✓ Pattern with / inside works")
    
    return True


def test_compile_patterns():
    """Test pattern compilation"""
    from regex_filters import compile_patterns, save_filter_config, FILTER_FILE
    
    print("\nTesting compile_patterns...")
    
    # Create test config
    test_config = {
        "keywords": ["test", "keyword"],
        "patterns": [
            "/urgent|important/i",
            "bitcoin",
            "/\\d{3}-\\d{4}/"
        ]
    }
    
    save_filter_config(test_config)
    
    # Compile patterns
    compiled = compile_patterns()
    
    # Check all patterns compiled
    assert len(compiled) == 3
    for orig, pattern, error in compiled:
        assert error is None, f"Pattern {orig} failed: {error}"
        assert pattern is not None
    
    print(f"✓ Compiled {len(compiled)} patterns successfully")
    
    # Test invalid pattern
    test_config["patterns"].append("/[invalid(pattern/")
    save_filter_config(test_config)
    compiled = compile_patterns()
    
    # Last pattern should have error
    assert compiled[-1][2] is not None
    print("✓ Invalid pattern handling works")
    
    # Cleanup
    if os.path.exists(FILTER_FILE):
        os.remove(FILTER_FILE)
    if os.path.exists(f"{FILTER_FILE}.backup"):
        os.remove(f"{FILTER_FILE}.backup")
    
    return True


def test_safe_regex_match():
    """Test safe regex matching"""
    from regex_filters import safe_regex_match
    
    print("\nTesting safe_regex_match...")
    
    # Test simple match
    pattern = re.compile(r"test", re.IGNORECASE)
    match = safe_regex_match(pattern, "This is a TEST message")
    assert match is not None
    assert match.group() == "TEST"
    print("✓ Simple match works")
    
    # Test no match
    match = safe_regex_match(pattern, "No match here")
    assert match is None
    print("✓ No match returns None")
    
    # Test complex pattern
    pattern = re.compile(r"\d{3}-\d{4}")
    match = safe_regex_match(pattern, "Call me at 123-4567")
    assert match is not None
    assert match.group() == "123-4567"
    print("✓ Complex pattern works")
    
    return True


def test_matches_filters():
    """Test the matches_filters function"""
    from regex_filters import matches_filters, parse_regex_pattern
    
    print("\nTesting matches_filters...")
    
    # Test keyword match
    keywords = ["urgent", "important"]
    patterns = []
    
    assert matches_filters("This is urgent", keywords, patterns)
    print("✓ Keyword match works")
    
    assert not matches_filters("This is normal", keywords, patterns)
    print("✓ No keyword match works")
    
    # Test regex pattern match
    keywords = []
    pattern_str = "/bitcoin|crypto/i"
    pattern, flags = parse_regex_pattern(pattern_str)
    compiled = re.compile(pattern, flags)
    patterns = [(pattern_str, compiled, None)]
    
    assert matches_filters("I bought bitcoin today", keywords, patterns)
    print("✓ Regex pattern match works")
    
    assert matches_filters("CRYPTO is cool", keywords, patterns)
    print("✓ Case-insensitive regex works")
    
    assert not matches_filters("I bought stocks", keywords, patterns)
    print("✓ No pattern match works")
    
    # Test both keywords and patterns
    keywords = ["urgent"]
    assert matches_filters("urgent message", keywords, patterns)
    print("✓ Keyword match with patterns defined works")
    
    assert matches_filters("bitcoin news", keywords, patterns)
    print("✓ Pattern match with keywords defined works")
    
    assert not matches_filters("normal message", keywords, patterns)
    print("✓ No match with both defined works")
    
    return True


def test_filter_config_persistence():
    """Test saving and loading filter config"""
    from regex_filters import load_filter_config, save_filter_config, FILTER_FILE
    
    print("\nTesting filter config persistence...")
    
    # Test default config
    if os.path.exists(FILTER_FILE):
        os.remove(FILTER_FILE)
    
    config = load_filter_config()
    assert config == {"keywords": [], "patterns": []}
    print("✓ Default config works")
    
    # Test saving and loading
    test_config = {
        "keywords": ["test1", "test2"],
        "patterns": ["/pattern1/i", "pattern2"]
    }
    
    save_filter_config(test_config)
    loaded_config = load_filter_config()
    
    assert loaded_config == test_config
    print("✓ Save and load works")
    
    # Test backup creation
    save_filter_config(test_config)
    assert os.path.exists(f"{FILTER_FILE}.backup")
    print("✓ Backup creation works")
    
    # Cleanup
    if os.path.exists(FILTER_FILE):
        os.remove(FILTER_FILE)
    if os.path.exists(f"{FILTER_FILE}.backup"):
        os.remove(f"{FILTER_FILE}.backup")
    
    return True


def test_pattern_length_validation():
    """Test pattern length validation"""
    from regex_filters import MAX_PATTERN_LENGTH
    
    print("\nTesting pattern length validation...")
    
    # Create a pattern that's too long
    long_pattern = "a" * (MAX_PATTERN_LENGTH + 1)
    assert len(long_pattern) > MAX_PATTERN_LENGTH
    print(f"✓ Pattern length validation constant is {MAX_PATTERN_LENGTH}")
    
    return True


def test_regex_flags():
    """Test different regex flags"""
    from regex_filters import parse_regex_pattern
    
    print("\nTesting regex flags...")
    
    # Test case-insensitive
    pattern, flags = parse_regex_pattern("/test/i")
    compiled = re.compile(pattern, flags)
    assert compiled.search("TEST") is not None
    print("✓ Case-insensitive flag works")
    
    # Test multiline
    pattern, flags = parse_regex_pattern("/^test/m")
    compiled = re.compile(pattern, flags)
    text = "line1\ntest\nline3"
    assert compiled.search(text) is not None
    print("✓ Multiline flag works")
    
    # Test dotall
    pattern, flags = parse_regex_pattern("/test.end/s")
    compiled = re.compile(pattern, flags)
    assert compiled.search("test\nend") is not None
    print("✓ Dotall flag works")
    
    return True


if __name__ == "__main__":
    print("Running regex filter tests...\n")
    print("=" * 50)
    
    try:
        test_parse_regex_pattern()
        test_compile_patterns()
        test_safe_regex_match()
        test_matches_filters()
        test_filter_config_persistence()
        test_pattern_length_validation()
        test_regex_flags()
        
        print("\n" + "=" * 50)
        print("All tests passed! ✓")
        print("=" * 50)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
