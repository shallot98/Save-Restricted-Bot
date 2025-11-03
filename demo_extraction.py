#!/usr/bin/env python3
"""
Demo script for extraction mode feature
Shows how the extraction mode works with various examples
"""

import re
import sys
import os

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from regex_filters import (
    extract_matches,
    format_snippets_for_telegram,
    parse_regex_pattern
)

def demo_keyword_extraction():
    """Demonstrate keyword extraction"""
    print("=" * 60)
    print("DEMO 1: Keyword Extraction")
    print("=" * 60)
    
    keywords = ["urgent", "important"]
    patterns = []
    
    message = """
    Good morning everyone. This is an important announcement about the 
    upcoming company meeting. All employees must attend. 
    
    In other news, we have an urgent update regarding the project timeline.
    Please review the attached documents.
    
    Have a great day!
    """
    
    print("\n📥 Original Message:")
    print(message)
    
    has_matches, snippets = extract_matches(message, keywords, patterns)
    
    print(f"\n✅ Matches Found: {has_matches}")
    print(f"📊 Number of Snippets: {len(snippets)}")
    
    if snippets:
        print("\n📤 Extracted Snippets:")
        for i, snippet in enumerate(snippets, 1):
            print(f"\n{i}. {snippet}")
    
    # Format for Telegram
    metadata = {
        "author": "John Smith",
        "chat_title": "Company Announcements",
        "link": "https://t.me/company_channel/123"
    }
    
    messages = format_snippets_for_telegram(snippets, metadata, include_metadata=True)
    
    print("\n📨 Formatted Telegram Message:")
    print("-" * 60)
    for msg in messages:
        print(msg)
    print("-" * 60)


def demo_regex_extraction():
    """Demonstrate regex extraction"""
    print("\n\n" + "=" * 60)
    print("DEMO 2: Regex Pattern Extraction")
    print("=" * 60)
    
    keywords = []
    
    # Pattern to match prices
    pattern_str = r"/\$\d+(?:,\d{3})*(?:\.\d{2})?/i"
    pattern, flags = parse_regex_pattern(pattern_str)
    compiled = re.compile(pattern, flags)
    patterns = [(pattern_str, compiled, None)]
    
    message = """
    Q4 Financial Report:
    
    Revenue: $125,000.00
    Expenses: $87,500.50
    Net Profit: $37,499.50
    
    Year-to-date total: $450,000
    
    Great performance this quarter!
    """
    
    print("\n📥 Original Message:")
    print(message)
    
    has_matches, snippets = extract_matches(message, keywords, patterns)
    
    print(f"\n✅ Matches Found: {has_matches}")
    print(f"📊 Number of Snippets: {len(snippets)}")
    
    if snippets:
        print("\n📤 Extracted Snippets:")
        for i, snippet in enumerate(snippets, 1):
            print(f"\n{i}. {snippet}")


def demo_combined_extraction():
    """Demonstrate combined keyword and regex extraction"""
    print("\n\n" + "=" * 60)
    print("DEMO 3: Combined Keyword and Regex Extraction")
    print("=" * 60)
    
    keywords = ["bitcoin", "crypto"]
    
    # Pattern to match prices
    pattern_str = r"/\$\d+/i"
    pattern, flags = parse_regex_pattern(pattern_str)
    compiled = re.compile(pattern, flags)
    patterns = [(pattern_str, compiled, None)]
    
    message = """
    Market Update - January 15, 2024
    
    Bitcoin reached a new high today at $52000. Analysts are optimistic 
    about continued growth in the crypto market.
    
    Ethereum also saw gains, trading at $3200. The overall market cap 
    increased by $100 billion in the last 24 hours.
    
    Investment Tip: Always do your own research before investing in 
    cryptocurrency. The market is highly volatile.
    """
    
    print("\n📥 Original Message:")
    print(message)
    
    has_matches, snippets = extract_matches(message, keywords, patterns)
    
    print(f"\n✅ Matches Found: {has_matches}")
    print(f"📊 Number of Snippets: {len(snippets)}")
    
    if snippets:
        print("\n📤 Extracted Snippets:")
        for i, snippet in enumerate(snippets, 1):
            print(f"\n{i}. {snippet}")
    
    # Format for Telegram with metadata
    metadata = {
        "author": "Crypto News Bot",
        "chat_title": "Crypto Updates",
        "link": "https://t.me/crypto_updates/456"
    }
    
    messages = format_snippets_for_telegram(snippets, metadata, include_metadata=True)
    
    print("\n📨 Formatted Telegram Message:")
    print("-" * 60)
    for msg in messages:
        print(msg)
    print("-" * 60)


def demo_no_match():
    """Demonstrate no match scenario"""
    print("\n\n" + "=" * 60)
    print("DEMO 4: No Match Scenario")
    print("=" * 60)
    
    keywords = ["urgent", "important"]
    patterns = []
    
    message = "This is just a regular message with no special keywords."
    
    print("\n📥 Original Message:")
    print(message)
    
    has_matches, snippets = extract_matches(message, keywords, patterns)
    
    print(f"\n✅ Matches Found: {has_matches}")
    
    if not has_matches:
        print("⏭️  Message would be skipped (not forwarded)")


def demo_sentence_extraction():
    """Demonstrate smart sentence extraction"""
    print("\n\n" + "=" * 60)
    print("DEMO 5: Smart Sentence Extraction")
    print("=" * 60)
    
    keywords = ["alert"]
    patterns = []
    
    message = """
    System Status Report:
    
    All services are running normally. Database backup completed successfully.
    Security alert: Unusual login attempt detected from IP 192.168.1.100.
    Please review the security logs. System will automatically block after 3 attempts.
    
    Next scheduled maintenance: Friday at 2 AM.
    """
    
    print("\n📥 Original Message:")
    print(message)
    print("\n🔍 Looking for: 'alert'")
    
    has_matches, snippets = extract_matches(message, keywords, patterns)
    
    print(f"\n✅ Matches Found: {has_matches}")
    
    if snippets:
        print("\n📤 Extracted Snippet (full sentence):")
        for snippet in snippets:
            print(f"\n{snippet}")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("EXTRACTION MODE DEMONSTRATION")
    print("=" * 60)
    print("\nThis demo shows how extraction mode works with different")
    print("types of content and filters.\n")
    
    try:
        demo_keyword_extraction()
        demo_regex_extraction()
        demo_combined_extraction()
        demo_no_match()
        demo_sentence_extraction()
        
        print("\n\n" + "=" * 60)
        print("DEMO COMPLETED SUCCESSFULLY")
        print("=" * 60)
        print("\nTo use extraction mode in the bot:")
        print("1. Add filters: /addre <pattern>")
        print("2. Enable mode: /mode extract on")
        print("3. Test it: /preview <text>")
        print("4. Set up watch: /watch add @source me")
        print("\nSee EXTRACTION_MODE.md for full documentation.")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
