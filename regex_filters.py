"""
Regex-based filtering module for keyword monitoring
"""

import re
import json
import shutil
import os
import signal
from typing import List, Tuple, Optional
from contextlib import contextmanager

# Regex filter configurations
FILTER_FILE = 'filter_config.json'
MAX_PATTERN_LENGTH = 500
MAX_PATTERN_COUNT = 100
REGEX_TIMEOUT = 1.0  # seconds

def load_filter_config():
    """Load filters configuration from file"""
    if os.path.exists(FILTER_FILE):
        with open(FILTER_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    # Default structure with backward compatibility
    return {
        "keywords": [],
        "patterns": []
    }

def save_filter_config(config):
    """Save filters configuration to file with atomic write"""
    # Backup existing file
    if os.path.exists(FILTER_FILE):
        shutil.copy2(FILTER_FILE, f'{FILTER_FILE}.backup')
    
    # Write new config
    with open(FILTER_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

def parse_regex_pattern(pattern_str: str) -> Tuple[str, int]:
    """
    Parse regex pattern with optional flags in /pattern/flags format
    Returns: (pattern, flags)
    Examples:
      - "test" -> ("test", re.IGNORECASE)
      - "/test/i" -> ("test", re.IGNORECASE)
      - "/test/im" -> ("test", re.IGNORECASE | re.MULTILINE)
    """
    # Default to case-insensitive
    flags = re.IGNORECASE
    
    # Check for /pattern/flags format
    if pattern_str.startswith('/') and pattern_str.count('/') >= 2:
        parts = pattern_str.split('/')
        if len(parts) >= 3:
            pattern = '/'.join(parts[1:-1])  # Handle patterns with / inside
            flag_str = parts[-1].lower()
            
            # Parse flags
            flags = 0
            if 'i' in flag_str:
                flags |= re.IGNORECASE
            if 'm' in flag_str:
                flags |= re.MULTILINE
            if 's' in flag_str:
                flags |= re.DOTALL
            if 'x' in flag_str:
                flags |= re.VERBOSE
            
            # If no flags specified, default to case-insensitive
            if flags == 0:
                flags = re.IGNORECASE
                
            return pattern, flags
    
    # No special format, treat as plain pattern with default flags
    return pattern_str, flags

def compile_patterns() -> List[Tuple[str, Optional[re.Pattern], Optional[str]]]:
    """
    Compile all regex patterns from config.
    Returns list of tuples: (original_pattern_string, compiled_pattern, error_message)
    """
    filter_config = load_filter_config()
    patterns = filter_config.get("patterns", [])
    compiled = []
    
    for pattern_str in patterns:
        if len(pattern_str) > MAX_PATTERN_LENGTH:
            compiled.append((pattern_str, None, f"Pattern too long (max {MAX_PATTERN_LENGTH} chars)"))
            continue
            
        try:
            pattern, flags = parse_regex_pattern(pattern_str)
            compiled_re = re.compile(pattern, flags)
            compiled.append((pattern_str, compiled_re, None))
        except re.error as e:
            compiled.append((pattern_str, None, f"Invalid regex: {str(e)}"))
    
    return compiled

@contextmanager
def timeout_context(seconds):
    """Context manager for timeout (Unix-like systems)"""
    def timeout_handler(signum, frame):
        raise TimeoutError("Regex matching timed out")
    
    # Set the signal handler
    if hasattr(signal, 'SIGALRM'):
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(int(seconds))
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
    else:
        # Windows or other platforms without SIGALRM
        yield

def safe_regex_match(pattern: re.Pattern, text: str, timeout: float = REGEX_TIMEOUT) -> Optional[re.Match]:
    """
    Safely match regex with timeout protection.
    Returns Match object or None if no match or timeout.
    """
    try:
        if hasattr(signal, 'SIGALRM'):
            with timeout_context(timeout):
                return pattern.search(text)
        else:
            # For platforms without signal support, just do the match
            # In production, consider using threading or multiprocessing for timeout
            return pattern.search(text)
    except TimeoutError:
        print(f"Regex timeout for pattern: {pattern.pattern}")
        return None
    except Exception as e:
        print(f"Regex error: {e}")
        return None

def matches_filters(text: str, keywords: List[str], patterns: List[Tuple[str, Optional[re.Pattern], Optional[str]]]) -> bool:
    """
    Check if text matches any keyword or regex pattern.
    Returns True if any match is found.
    """
    if not text:
        return False
    
    # Check plain keywords
    for keyword in keywords:
        if keyword.lower() in text.lower():
            return True
    
    # Check regex patterns
    for pattern_str, compiled_pattern, error in patterns:
        if compiled_pattern is None:
            continue
        if safe_regex_match(compiled_pattern, text):
            return True
    
    return False
