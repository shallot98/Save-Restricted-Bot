"""
Regex-based filtering module for keyword monitoring
"""

import re
import json
import shutil
import os
import signal
import html
from typing import List, Tuple, Optional, Dict, Any
from contextlib import contextmanager

# Regex filter configurations
FILTER_FILE = 'filter_config.json'
MAX_PATTERN_LENGTH = 500
MAX_PATTERN_COUNT = 100
REGEX_TIMEOUT = 1.0  # seconds
MAX_SNIPPETS_PER_MESSAGE = 10
CONTEXT_WINDOW_SIZE = 100
TELEGRAM_MAX_MESSAGE_LENGTH = 4096

def load_filter_config():
    """Load filters configuration from file"""
    if os.path.exists(FILTER_FILE):
        with open(FILTER_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    # Default structure with backward compatibility
    return {
        "keywords": [],
        "patterns": [],
        "extract_mode": False
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


def compile_pattern_list(patterns: List[str]) -> List[Tuple[str, Optional[re.Pattern], Optional[str]]]:
    """
    Compile a list of regex patterns (for per-watch use).
    Returns list of tuples: (original_pattern_string, compiled_pattern, error_message)
    """
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


def extract_sentence(text: str, start: int, end: int) -> Tuple[int, int]:
    """
    Extract sentence boundaries around the given position.
    Returns (sentence_start, sentence_end) indices.
    """
    # Sentence delimiters
    delimiters = ['.', '!', '?', '\n', '\r']
    
    # Find sentence start
    sentence_start = 0
    for i in range(start - 1, -1, -1):
        if text[i] in delimiters:
            sentence_start = i + 1
            break
    
    # Find sentence end
    sentence_end = len(text)
    for i in range(end, len(text)):
        if text[i] in delimiters:
            sentence_end = i + 1
            break
    
    # Trim whitespace
    while sentence_start < len(text) and text[sentence_start].isspace():
        sentence_start += 1
    while sentence_end > 0 and text[sentence_end - 1].isspace():
        sentence_end -= 1
    
    return sentence_start, sentence_end


def extract_context(text: str, start: int, end: int, window_size: int = CONTEXT_WINDOW_SIZE) -> Tuple[int, int]:
    """
    Extract context window around the given position.
    Returns (context_start, context_end) indices.
    """
    context_start = max(0, start - window_size)
    context_end = min(len(text), end + window_size)
    
    # Try to break at word boundaries
    if context_start > 0:
        # Find previous space
        for i in range(context_start, max(0, context_start - 20), -1):
            if text[i].isspace():
                context_start = i + 1
                break
    
    if context_end < len(text):
        # Find next space
        for i in range(context_end, min(len(text), context_end + 20)):
            if text[i].isspace():
                context_end = i
                break
    
    return context_start, context_end


def extract_keyword_snippets(text: str, keywords: List[str]) -> List[Tuple[int, int, str]]:
    """
    Extract snippets containing keywords.
    Returns list of (start, end, keyword) tuples.
    """
    if not text or not keywords:
        return []
    
    snippets = []
    text_lower = text.lower()
    
    for keyword in keywords:
        keyword_lower = keyword.lower()
        start_pos = 0
        
        while True:
            pos = text_lower.find(keyword_lower, start_pos)
            if pos == -1:
                break
            
            # Try to extract full sentence first
            sentence_start, sentence_end = extract_sentence(text, pos, pos + len(keyword))
            
            # If sentence is too long, use context window
            if sentence_end - sentence_start > CONTEXT_WINDOW_SIZE * 2:
                snippet_start, snippet_end = extract_context(text, pos, pos + len(keyword))
            else:
                snippet_start, snippet_end = sentence_start, sentence_end
            
            snippets.append((snippet_start, snippet_end, keyword))
            start_pos = pos + 1
    
    return snippets


def extract_regex_snippets(text: str, patterns: List[Tuple[str, Optional[re.Pattern], Optional[str]]]) -> List[Tuple[int, int, str]]:
    """
    Extract snippets matching regex patterns.
    Returns list of (start, end, pattern_str) tuples.
    """
    if not text or not patterns:
        return []
    
    snippets = []
    
    for pattern_str, compiled_pattern, error in patterns:
        if compiled_pattern is None:
            continue
        
        # Find all matches
        try:
            if hasattr(signal, 'SIGALRM'):
                with timeout_context(REGEX_TIMEOUT):
                    matches = compiled_pattern.finditer(text)
                    for match in matches:
                        # Check for named groups first
                        if match.groupdict():
                            # Use named groups
                            for group_name, group_value in match.groupdict().items():
                                if group_value:
                                    group_start = text.find(group_value, match.start())
                                    if group_start != -1:
                                        snippets.append((group_start, group_start + len(group_value), pattern_str))
                        else:
                            # Use full match
                            snippets.append((match.start(), match.end(), pattern_str))
            else:
                matches = compiled_pattern.finditer(text)
                for match in matches:
                    if match.groupdict():
                        for group_name, group_value in match.groupdict().items():
                            if group_value:
                                group_start = text.find(group_value, match.start())
                                if group_start != -1:
                                    snippets.append((group_start, group_start + len(group_value), pattern_str))
                    else:
                        snippets.append((match.start(), match.end(), pattern_str))
        except TimeoutError:
            print(f"Regex timeout for pattern: {pattern_str}")
        except Exception as e:
            print(f"Regex error: {e}")
    
    return snippets


def merge_overlapping_spans(snippets: List[Tuple[int, int, str]]) -> List[Tuple[int, int, List[str]]]:
    """
    Merge overlapping or adjacent snippets.
    Returns list of (start, end, [sources]) tuples where sources are keywords/patterns that matched.
    """
    if not snippets:
        return []
    
    # Sort by start position
    sorted_snippets = sorted(snippets, key=lambda x: x[0])
    
    merged = []
    current_start, current_end, sources = sorted_snippets[0][0], sorted_snippets[0][1], [sorted_snippets[0][2]]
    
    for start, end, source in sorted_snippets[1:]:
        # If overlapping or adjacent (within 10 chars)
        if start <= current_end + 10:
            current_end = max(current_end, end)
            if source not in sources:
                sources.append(source)
        else:
            merged.append((current_start, current_end, sources[:]))
            current_start, current_end, sources = start, end, [source]
    
    merged.append((current_start, current_end, sources))
    
    return merged


def escape_html(text: str) -> str:
    """Escape HTML entities for Telegram HTML mode"""
    return html.escape(text)


def format_snippets_for_telegram(
    snippets: List[str],
    metadata: Optional[Dict[str, Any]] = None,
    include_metadata: bool = True
) -> List[str]:
    """
    Format snippets for Telegram with HTML formatting.
    Returns list of message strings, each under 4096 chars.
    """
    if not snippets:
        return []
    
    messages = []
    current_message = ""
    
    # Add metadata header if provided
    if include_metadata and metadata:
        header = ""
        if metadata.get("author"):
            header += f"👤 <b>作者:</b> {escape_html(metadata['author'])}\n"
        if metadata.get("chat_title"):
            header += f"💬 <b>频道:</b> {escape_html(metadata['chat_title'])}\n"
        if metadata.get("link"):
            header += f"🔗 <b>链接:</b> {metadata['link']}\n"
        if header:
            header += "\n" + "─" * 30 + "\n\n"
            current_message = header
    
    # Add snippets
    for idx, snippet in enumerate(snippets[:MAX_SNIPPETS_PER_MESSAGE], 1):
        snippet_text = f"📌 <b>匹配 #{idx}:</b>\n{escape_html(snippet)}\n\n"
        
        # Check if adding this snippet would exceed limit
        if len(current_message) + len(snippet_text) > TELEGRAM_MAX_MESSAGE_LENGTH - 100:
            if current_message:
                messages.append(current_message.strip())
            current_message = snippet_text
        else:
            current_message += snippet_text
    
    # Add remaining message
    if current_message:
        messages.append(current_message.strip())
    
    # If too many snippets, add warning
    if len(snippets) > MAX_SNIPPETS_PER_MESSAGE:
        warning = f"\n\n⚠️ <i>显示了前 {MAX_SNIPPETS_PER_MESSAGE} 个匹配，共 {len(snippets)} 个</i>"
        if messages:
            if len(messages[-1]) + len(warning) <= TELEGRAM_MAX_MESSAGE_LENGTH:
                messages[-1] += warning
            else:
                messages.append(warning)
    
    return messages


def extract_matches(
    text: str,
    keywords: List[str],
    patterns: List[Tuple[str, Optional[re.Pattern], Optional[str]]]
) -> Tuple[bool, List[str]]:
    """
    Extract matched snippets from text.
    Returns (has_matches, [snippet_strings]) tuple.
    """
    if not text:
        return False, []
    
    # Extract keyword snippets
    keyword_snippets = extract_keyword_snippets(text, keywords)
    
    # Extract regex snippets
    regex_snippets = extract_regex_snippets(text, patterns)
    
    # Combine all snippets
    all_snippets = keyword_snippets + regex_snippets
    
    if not all_snippets:
        return False, []
    
    # Merge overlapping spans
    merged_spans = merge_overlapping_spans(all_snippets)
    
    # Extract text for each span
    extracted_texts = []
    for start, end, sources in merged_spans:
        snippet_text = text[start:end].strip()
        if snippet_text:
            extracted_texts.append(snippet_text)
    
    return True, extracted_texts
