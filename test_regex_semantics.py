#!/usr/bin/env python3
"""
Test script for regex semantics in full/extract modes
"""

import re
from regex_filters import (
    compile_pattern_list,
    matches_regex_only,
    matches_keywords_only,
    extract_regex_only,
    extract_matches
)

def test_regex_compilation():
    """Test that regex patterns compile correctly"""
    print("=" * 60)
    print("TEST: Regex Compilation")
    print("=" * 60)
    
    patterns = [
        "/test/i",
        "/urgent|important/i",
        r"/\d{3}-\d{4}/",
        "bitcoin",
        "/invalid[/i"  # This should fail
    ]
    
    for pattern in patterns:
        compiled = compile_pattern_list([pattern])
        if compiled:
            pattern_str, compiled_re, error = compiled[0]
            if error:
                print(f"❌ Pattern: {pattern}")
                print(f"   Error: {error}")
            else:
                print(f"✅ Pattern: {pattern}")
                print(f"   Compiled: {compiled_re.pattern if compiled_re else 'None'}")
        print()

def test_matches_regex_only():
    """Test regex-only matching"""
    print("=" * 60)
    print("TEST: Regex-Only Matching")
    print("=" * 60)
    
    text = "This is an URGENT message about bitcoin: 123-4567"
    
    patterns = [
        "/urgent/i",
        "/bitcoin/",
        r"/\d{3}-\d{4}/"
    ]
    
    compiled = compile_pattern_list(patterns)
    
    print(f"Text: {text}")
    print(f"Patterns: {patterns}")
    print(f"Match result: {matches_regex_only(text, compiled)}")
    print()
    
    # Test with non-matching pattern
    patterns2 = ["/ethereum/i"]
    compiled2 = compile_pattern_list(patterns2)
    print(f"Patterns (non-matching): {patterns2}")
    print(f"Match result: {matches_regex_only(text, compiled2)}")
    print()

def test_matches_keywords_only():
    """Test keyword-only matching"""
    print("=" * 60)
    print("TEST: Keyword-Only Matching")
    print("=" * 60)
    
    text = "This is an URGENT message about bitcoin"
    keywords = ["urgent", "critical"]
    
    print(f"Text: {text}")
    print(f"Keywords: {keywords}")
    print(f"Match result: {matches_keywords_only(text, keywords)}")
    print()
    
    # Test with non-matching keywords
    keywords2 = ["ethereum", "solana"]
    print(f"Keywords (non-matching): {keywords2}")
    print(f"Match result: {matches_keywords_only(text, keywords2)}")
    print()

def test_extract_regex_only():
    """Test regex-only extraction"""
    print("=" * 60)
    print("TEST: Regex-Only Extraction")
    print("=" * 60)
    
    text = "Alert: Price of bitcoin is $50000 and ethereum is $3000. Contact: 123-4567"
    
    patterns = [
        "/bitcoin/i",
        r"/\d{3}-\d{4}/",
        "/ethereum/i"
    ]
    
    compiled = compile_pattern_list(patterns)
    has_matches, snippets = extract_regex_only(text, compiled)
    
    print(f"Text: {text}")
    print(f"Patterns: {patterns}")
    print(f"Has matches: {has_matches}")
    print(f"Snippets extracted: {len(snippets)}")
    for i, snippet in enumerate(snippets, 1):
        print(f"  {i}. {snippet}")
    print()

def test_priority_logic():
    """Test that regex has priority over keywords in full mode logic"""
    print("=" * 60)
    print("TEST: Priority Logic (Full Mode Simulation)")
    print("=" * 60)
    
    text = "This message contains ethereum but not our target"
    
    # Scenario 1: Has regex patterns - should only use regex
    monitor_patterns = ["/bitcoin/i", "/urgent/i"]
    monitor_keywords = ["ethereum", "message"]  # These should be ignored
    
    compiled = compile_pattern_list(monitor_patterns)
    has_regex_match = matches_regex_only(text, compiled)
    has_keyword_match = matches_keywords_only(text, monitor_keywords)
    
    print("Scenario 1: Regex patterns exist")
    print(f"Text: {text}")
    print(f"Regex patterns: {monitor_patterns}")
    print(f"Keywords (should be ignored): {monitor_keywords}")
    print(f"Regex match: {has_regex_match}")
    print(f"Keyword match: {has_keyword_match}")
    print(f"Should forward: {has_regex_match}")  # Only use regex
    print()
    
    # Scenario 2: No regex, only keywords
    monitor_patterns2 = []
    monitor_keywords2 = ["ethereum", "message"]
    
    compiled2 = compile_pattern_list(monitor_patterns2)
    has_keyword_match2 = matches_keywords_only(text, monitor_keywords2)
    
    print("Scenario 2: No regex, only keywords")
    print(f"Text: {text}")
    print(f"Regex patterns: {monitor_patterns2} (empty)")
    print(f"Keywords: {monitor_keywords2}")
    print(f"Keyword match: {has_keyword_match2}")
    print(f"Should forward: {has_keyword_match2}")
    print()

def test_extract_mode_logic():
    """Test extract mode logic (regex only, no keywords)"""
    print("=" * 60)
    print("TEST: Extract Mode Logic")
    print("=" * 60)
    
    text = "URGENT: Bitcoin price alert! Contact: 123-4567"
    
    # Extract mode should ONLY use regex, ignore keywords
    extract_patterns = ["/urgent/i", r"/\d{3}-\d{4}/"]
    extract_keywords = ["bitcoin", "alert"]  # Should be ignored
    
    compiled = compile_pattern_list(extract_patterns)
    has_matches, snippets = extract_regex_only(text, compiled)
    
    print(f"Text: {text}")
    print(f"Extract patterns: {extract_patterns}")
    print(f"Extract keywords (should be ignored): {extract_keywords}")
    print(f"Has matches: {has_matches}")
    print(f"Snippets extracted: {len(snippets)}")
    for i, snippet in enumerate(snippets, 1):
        print(f"  {i}. {snippet}")
    print()
    
    # Verify keywords are NOT used
    print("Verifying keywords are ignored:")
    has_matches_mixed, snippets_mixed = extract_matches(text, extract_keywords, compiled)
    print(f"Using extract_matches (old function with keywords): {len(snippets_mixed)} snippets")
    print(f"Using extract_regex_only (new function): {len(snippets)} snippets")
    print(f"Difference shows keywords were included in old function: {len(snippets_mixed) > len(snippets)}")
    print()

if __name__ == "__main__":
    test_regex_compilation()
    test_matches_regex_only()
    test_matches_keywords_only()
    test_extract_regex_only()
    test_priority_logic()
    test_extract_mode_logic()
    
    print("=" * 60)
    print("ALL TESTS COMPLETED")
    print("=" * 60)
