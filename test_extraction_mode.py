#!/usr/bin/env python3
"""
Test script for extraction mode functionality
"""

import re
import json
import os
import sys

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_extract_sentence():
    """Test sentence extraction"""
    from regex_filters import extract_sentence
    
    print("Testing extract_sentence...")
    
    # Test basic sentence
    text = "This is the first sentence. This is the second. And third."
    start, end = extract_sentence(text, 10, 15)  # "first"
    assert text[start:end] == "This is the first sentence."
    print("✓ Basic sentence extraction works")
    
    # Test sentence with multiple delimiters
    text = "Question? Answer! Statement."
    start, end = extract_sentence(text, 10, 15)  # "Answer"
    assert "Answer!" in text[start:end]
    print("✓ Multiple delimiters work")
    
    # Test newline delimiter
    text = "Line 1\nLine 2\nLine 3"
    start, end = extract_sentence(text, 10, 12)  # "Line 2"
    assert text[start:end] == "Line 2"
    print("✓ Newline delimiter works")
    
    return True


def test_extract_context():
    """Test context window extraction"""
    from regex_filters import extract_context
    
    print("\nTesting extract_context...")
    
    # Test basic context
    text = "A" * 50 + "TARGET" + "B" * 50
    start, end = extract_context(text, 50, 56, window_size=20)
    assert 30 <= start <= 40
    assert 66 <= end <= 76
    print("✓ Basic context extraction works")
    
    # Test word boundary breaking
    text = "This is a very long text with many words and the TARGET word is here with more words"
    start, end = extract_context(text, 50, 56, window_size=20)
    extracted = text[start:end]
    # Should break at word boundaries
    assert not extracted[0].isspace() or start == 0
    print("✓ Word boundary breaking works")
    
    return True


def test_extract_keyword_snippets():
    """Test keyword snippet extraction"""
    from regex_filters import extract_keyword_snippets
    
    print("\nTesting extract_keyword_snippets...")
    
    # Test single keyword
    text = "This is an urgent message about important matters."
    snippets = extract_keyword_snippets(text, ["urgent"])
    assert len(snippets) > 0
    start, end, keyword = snippets[0]
    assert text[start:end] == "This is an urgent message about important matters."
    print("✓ Single keyword extraction works")
    
    # Test multiple keywords
    snippets = extract_keyword_snippets(text, ["urgent", "important"])
    assert len(snippets) >= 2
    print("✓ Multiple keywords extraction works")
    
    # Test case insensitive
    snippets = extract_keyword_snippets(text, ["URGENT"])
    assert len(snippets) > 0
    print("✓ Case insensitive matching works")
    
    # Test multiple occurrences
    text = "urgent urgent urgent"
    snippets = extract_keyword_snippets(text, ["urgent"])
    assert len(snippets) == 3
    print("✓ Multiple occurrences detected")
    
    return True


def test_extract_regex_snippets():
    """Test regex snippet extraction"""
    from regex_filters import extract_regex_snippets, parse_regex_pattern
    
    print("\nTesting extract_regex_snippets...")
    
    # Test simple regex
    text = "Call me at 123-4567 or 987-6543"
    pattern_str = r"\d{3}-\d{4}"
    pattern, flags = parse_regex_pattern(pattern_str)
    compiled = re.compile(pattern, flags)
    patterns = [(pattern_str, compiled, None)]
    
    snippets = extract_regex_snippets(text, patterns)
    assert len(snippets) == 2
    assert text[snippets[0][0]:snippets[0][1]] == "123-4567"
    assert text[snippets[1][0]:snippets[1][1]] == "987-6543"
    print("✓ Simple regex extraction works")
    
    # Test with flags
    text = "Bitcoin and BITCOIN"
    pattern_str = "/bitcoin/i"
    pattern, flags = parse_regex_pattern(pattern_str)
    compiled = re.compile(pattern, flags)
    patterns = [(pattern_str, compiled, None)]
    
    snippets = extract_regex_snippets(text, patterns)
    assert len(snippets) == 2
    print("✓ Regex with flags works")
    
    return True


def test_merge_overlapping_spans():
    """Test merging of overlapping spans"""
    from regex_filters import merge_overlapping_spans
    
    print("\nTesting merge_overlapping_spans...")
    
    # Test non-overlapping (far apart)
    snippets = [(0, 10, "kw1"), (30, 40, "kw2")]
    merged = merge_overlapping_spans(snippets)
    assert len(merged) == 2
    print("✓ Non-overlapping spans preserved")
    
    # Test overlapping
    snippets = [(0, 15, "kw1"), (10, 25, "kw2")]
    merged = merge_overlapping_spans(snippets)
    assert len(merged) == 1
    assert merged[0][0] == 0
    assert merged[0][1] == 25
    assert "kw1" in merged[0][2] and "kw2" in merged[0][2]
    print("✓ Overlapping spans merged")
    
    # Test adjacent spans (within threshold)
    snippets = [(0, 10, "kw1"), (15, 25, "kw2")]  # 5 chars apart, should merge
    merged = merge_overlapping_spans(snippets)
    assert len(merged) == 1
    print("✓ Adjacent spans merged")
    
    # Test at threshold boundary
    snippets = [(0, 10, "kw1"), (20, 30, "kw2")]  # exactly 10 chars apart
    merged = merge_overlapping_spans(snippets)
    # At threshold, should merge
    assert len(merged) == 1
    print("✓ Threshold boundary spans merged")
    
    return True


def test_escape_html():
    """Test HTML escaping"""
    from regex_filters import escape_html
    
    print("\nTesting escape_html...")
    
    # Test special characters
    text = "<script>alert('test')</script>"
    escaped = escape_html(text)
    assert "&lt;" in escaped
    assert "&gt;" in escaped
    assert "script" in escaped
    print("✓ HTML escaping works")
    
    # Test ampersand
    text = "AT&T"
    escaped = escape_html(text)
    assert "&amp;" in escaped
    print("✓ Ampersand escaping works")
    
    return True


def test_format_snippets_for_telegram():
    """Test Telegram formatting"""
    from regex_filters import format_snippets_for_telegram
    
    print("\nTesting format_snippets_for_telegram...")
    
    # Test basic formatting
    snippets = ["This is snippet 1", "This is snippet 2"]
    messages = format_snippets_for_telegram(snippets, include_metadata=False)
    assert len(messages) > 0
    print("✓ Basic formatting works")
    
    # Test with metadata
    metadata = {
        "author": "Test User",
        "chat_title": "Test Channel",
        "link": "https://t.me/test/123"
    }
    messages = format_snippets_for_telegram(snippets, metadata, include_metadata=True)
    assert len(messages) > 0
    assert "Test User" in messages[0]
    assert "Test Channel" in messages[0]
    print("✓ Metadata inclusion works")
    
    # Test HTML escaping
    snippets = ["<b>test</b> & special chars"]
    messages = format_snippets_for_telegram(snippets, include_metadata=False)
    assert "&lt;" in messages[0]
    assert "&gt;" in messages[0]
    assert "&amp;" in messages[0]
    print("✓ HTML escaping in formatting works")
    
    # Test long message splitting
    long_snippet = "A" * 4000
    snippets = [long_snippet, "Short snippet"]
    messages = format_snippets_for_telegram(snippets, include_metadata=False)
    assert len(messages) >= 2
    print("✓ Long message splitting works")
    
    # Test max snippets limit
    snippets = [f"Snippet {i}" for i in range(20)]
    messages = format_snippets_for_telegram(snippets, include_metadata=False)
    # Should include warning about truncation
    assert any("显示了前" in msg for msg in messages)
    print("✓ Max snippets limit works")
    
    return True


def test_extract_matches():
    """Test the main extract_matches function"""
    from regex_filters import extract_matches, parse_regex_pattern
    
    print("\nTesting extract_matches...")
    
    # Test with keywords only
    text = "This is an urgent message about important stuff. More text here."
    keywords = ["urgent", "important"]
    patterns = []
    
    has_matches, snippets = extract_matches(text, keywords, patterns)
    assert has_matches
    assert len(snippets) > 0
    print("✓ Keyword-only extraction works")
    
    # Test with patterns only
    text = "Call me at 123-4567"
    keywords = []
    pattern_str = r"\d{3}-\d{4}"
    pattern, flags = parse_regex_pattern(pattern_str)
    compiled = re.compile(pattern, flags)
    patterns = [(pattern_str, compiled, None)]
    
    has_matches, snippets = extract_matches(text, keywords, patterns)
    assert has_matches
    assert "123-4567" in snippets[0]
    print("✓ Pattern-only extraction works")
    
    # Test with both keywords and patterns
    text = "This is urgent! Call 123-4567 now!"
    keywords = ["urgent"]
    has_matches, snippets = extract_matches(text, keywords, patterns)
    assert has_matches
    # Should merge into one snippet
    assert len(snippets) >= 1
    print("✓ Combined keyword and pattern extraction works")
    
    # Test no matches
    text = "Nothing interesting here"
    keywords = ["urgent"]
    patterns = []
    has_matches, snippets = extract_matches(text, keywords, patterns)
    assert not has_matches
    assert len(snippets) == 0
    print("✓ No matches returns correctly")
    
    return True


def test_filter_config_with_extract_mode():
    """Test filter config with extract_mode field"""
    from regex_filters import load_filter_config, save_filter_config, FILTER_FILE
    
    print("\nTesting filter config with extract_mode...")
    
    # Clean up existing config
    if os.path.exists(FILTER_FILE):
        os.remove(FILTER_FILE)
    
    # Test default config includes extract_mode
    config = load_filter_config()
    assert "extract_mode" in config
    assert config["extract_mode"] is False
    print("✓ Default config includes extract_mode=False")
    
    # Test saving and loading extract_mode
    config["extract_mode"] = True
    save_filter_config(config)
    
    loaded_config = load_filter_config()
    assert loaded_config["extract_mode"] is True
    print("✓ Extract mode persists correctly")
    
    # Cleanup
    if os.path.exists(FILTER_FILE):
        os.remove(FILTER_FILE)
    if os.path.exists(f"{FILTER_FILE}.backup"):
        os.remove(f"{FILTER_FILE}.backup")
    
    return True


def test_integration_scenario():
    """Test a realistic integration scenario"""
    from regex_filters import (
        extract_matches, 
        format_snippets_for_telegram,
        parse_regex_pattern,
        load_filter_config,
        save_filter_config,
        FILTER_FILE
    )
    
    print("\nTesting integration scenario...")
    
    # Clean up
    if os.path.exists(FILTER_FILE):
        os.remove(FILTER_FILE)
    
    # Setup: configure keywords and patterns
    config = {
        "keywords": ["urgent", "important"],
        "patterns": ["/bitcoin|crypto/i", r"/\$\d+/"],
        "extract_mode": True
    }
    save_filter_config(config)
    
    # Simulate receiving a message
    message_text = """
    This is an urgent announcement! We have important news about Bitcoin.
    The price has reached $50000 today. This is a significant milestone for crypto.
    Please check your accounts immediately.
    """
    
    # Compile patterns
    compiled_patterns = []
    for pattern_str in config["patterns"]:
        try:
            pattern, flags = parse_regex_pattern(pattern_str)
            compiled = re.compile(pattern, flags)
            compiled_patterns.append((pattern_str, compiled, None))
        except:
            pass
    
    # Extract matches
    has_matches, snippets = extract_matches(message_text, config["keywords"], compiled_patterns)
    
    assert has_matches
    assert len(snippets) > 0
    print(f"✓ Found {len(snippets)} snippet(s)")
    
    # Format for Telegram
    metadata = {
        "author": "John Doe",
        "chat_title": "Crypto News",
        "link": "https://t.me/crypto_news/123"
    }
    
    messages = format_snippets_for_telegram(snippets, metadata, include_metadata=True)
    assert len(messages) > 0
    
    # Check that formatted message contains metadata
    first_message = messages[0]
    assert "John Doe" in first_message
    assert "Crypto News" in first_message
    print("✓ Integration scenario works end-to-end")
    
    # Cleanup
    if os.path.exists(FILTER_FILE):
        os.remove(FILTER_FILE)
    if os.path.exists(f"{FILTER_FILE}.backup"):
        os.remove(f"{FILTER_FILE}.backup")
    
    return True


if __name__ == "__main__":
    print("Running extraction mode tests...\n")
    print("=" * 50)
    
    try:
        test_extract_sentence()
        test_extract_context()
        test_extract_keyword_snippets()
        test_extract_regex_snippets()
        test_merge_overlapping_spans()
        test_escape_html()
        test_format_snippets_for_telegram()
        test_extract_matches()
        test_filter_config_with_extract_mode()
        test_integration_scenario()
        
        print("\n" + "=" * 50)
        print("All extraction mode tests passed! ✓")
        print("=" * 50)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
