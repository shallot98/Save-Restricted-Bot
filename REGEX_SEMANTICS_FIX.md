# Regex Semantics Fix for Full/Extract Modes

## Overview

This document describes the implementation of the regex semantics fix that addresses the requirements for proper regex behavior in both full and extract forwarding modes.

## Changes Summary

### 1. Regex Priority in Full Mode

**Before**: Both keywords and regex patterns were checked simultaneously using `extract_matches()`, with no prioritization.

**After**: Regex patterns now take strict priority over keywords:
- If `monitor_filters.patterns` exists and is non-empty → use **ONLY** regex patterns (keywords ignored)
- If no regex patterns but `monitor_filters.keywords` exists → use keywords
- If no filters at all → forward all messages

**Code**: `main.py` lines 1452-1473

### 2. Extract Mode: Regex Only

**Before**: Extract mode used both keywords and regex patterns from `extract_filters`.

**After**: Extract mode now uses **ONLY** regex patterns:
- `extract_filters.patterns` is the sole source for extraction
- `extract_filters.keywords` is completely ignored
- If no regex patterns → don't forward anything
- `preserve_source` setting is ignored in extract mode (snippets never preserve source)

**Code**: `main.py` lines 1491-1550

### 3. New Utility Functions

Added three new functions to `regex_filters.py`:

#### `matches_regex_only(text, patterns)`
- Checks if text matches any regex pattern
- Keywords are not considered
- Used in full mode when regex patterns exist

#### `matches_keywords_only(text, keywords)`
- Checks if text matches any keyword
- Patterns are not considered
- Used in full mode when no regex patterns exist

#### `extract_regex_only(text, patterns)`
- Extracts snippets using ONLY regex patterns
- Keywords are completely ignored
- Used in extract mode

### 4. UI Changes

Updated `inline_ui_v2.py` to reflect extract-only-regex behavior:

#### Filter Menu (`get_filter_menu_keyboard`)
- **Monitor section (m)**: Shows both "添加关键词" and "添加正则" buttons
- **Extract section (e)**: Shows **ONLY** "添加正则" button (keywords hidden)

#### Filter Menu Text (`handle_filter_menu`)
- **Monitor filters**: Explains priority logic (regex > keywords > all messages)
- **Extract filters**: States clearly "仅使用正则表达式" and "不支持关键词匹配"

#### Watch Detail Display (`get_watch_detail_keyboard`)
- Monitor filters: Shows count as "关键词+正则" (e.g., "3+2")
- Extract filters: Shows count as "正则" only (e.g., "5 正则")

### 5. Enhanced Validation

Improved regex pattern validation in `inline_ui_v2.py` (`handle_user_input`):
- Check pattern length against `MAX_PATTERN_LENGTH` (500 chars)
- Compile pattern to verify syntax before adding
- Provide detailed error messages:
  - "❌ 正则表达式过长（最大 500 字符）"
  - "❌ 正则表达式语法错误: {error}"
  - "❌ 正则表达式无效: {error}"

### 6. Updated Help Text

Modified `/help` command output in `main.py` to explain:
- Full mode priority logic (regex > keywords > all)
- Extract mode regex-only behavior
- preserve_source only works in full mode
- Pattern limits and syntax

### 7. Logging Improvements

Added debug-level logging for forwarding decisions:
- `logger.debug(f"Full mode: No regex match for watch {watch_id}, skipping")`
- `logger.debug(f"Extract mode: No regex patterns for watch {watch_id}, skipping")`
- `logger.info(f"Full mode: Forwarded message from {source_chat_id} to {target_chat_id}")`
- `logger.info(f"Extract mode: Sent {len(snippets)} snippets from {source_chat_id} to {target_chat_id}")`

## Technical Details

### Full Mode Forwarding Logic

```python
if monitor_patterns:
    # Regex patterns exist: use ONLY regex (ignore keywords)
    compiled_monitor = compile_pattern_list(monitor_patterns)
    has_match = matches_regex_only(message_text, compiled_monitor)
    if not has_match:
        return  # No match, don't forward
elif monitor_kw:
    # No regex, but keywords exist: use keywords
    has_match = matches_keywords_only(message_text, monitor_kw)
    if not has_match:
        return  # No match, don't forward
# else: no filters at all, forward everything

# Forward full message with preserve_source support
```

### Extract Mode Forwarding Logic

```python
# Extract mode: use ONLY regex patterns (ignore keywords)
extract_patterns = extract_filters.get("patterns", [])

if not extract_patterns:
    return  # No extract regex patterns defined

# Check for matches and extract snippets using ONLY regex
compiled_extract = compile_pattern_list(extract_patterns)
has_matches, snippets = extract_regex_only(message_text, compiled_extract)

if not has_matches:
    return  # No matches

# Format and send snippets (preserve_source ignored)
```

### Regex Engine Features

- **Syntax**: Supports `/pattern/flags` format (e.g., `/urgent/i`)
- **Default**: Case-insensitive matching if no flags specified
- **Compilation**: Patterns compiled on startup and updates; cached per watch
- **Validation**: Patterns validated before adding with detailed error messages
- **Timeout**: 1-second timeout protection on Unix systems (SIGALRM)
- **Limits**:
  - Max pattern length: 500 characters
  - Max patterns per filter set: 100
  - Max snippets per message: 10
- **Named Groups**: Supported for precise extraction

## Testing

Created comprehensive test suite in `test_regex_semantics.py`:

### Test Cases

1. **Regex Compilation**: Verifies pattern parsing and compilation with error handling
2. **Regex-Only Matching**: Tests `matches_regex_only()` function
3. **Keyword-Only Matching**: Tests `matches_keywords_only()` function
4. **Regex-Only Extraction**: Tests `extract_regex_only()` function
5. **Priority Logic**: Simulates full mode with priority rules
6. **Extract Mode Logic**: Verifies keywords are ignored in extract mode

### Running Tests

```bash
python3 test_regex_semantics.py
python3 test_regex_filters.py
python3 test_extraction_mode.py
python3 test_watch_v3.py
```

All existing tests continue to pass, ensuring backward compatibility.

## Backward Compatibility

- V2 and V1 watch configs automatically migrate to V3 format
- Legacy whitelist/blacklist still supported
- Old inline UI callbacks fall back gracefully
- Existing watches with keywords continue to work
- Extract mode keywords (if present in config) are simply ignored

## User-Facing Changes

### What Users Will Notice

1. **Full Mode**:
   - If you add regex patterns, keywords are ignored
   - Clear UI feedback explaining priority
   - Better matching precision

2. **Extract Mode**:
   - Keyword buttons removed from extract filter UI
   - Only regex patterns can be added
   - Clearer messaging about regex-only behavior
   - More consistent extraction results

3. **Help Documentation**:
   - Updated `/help` command with detailed explanations
   - Examples showing priority logic
   - Clear indication of pattern limits

### Migration Notes

- Existing extract keywords (if any) remain in config but are ignored
- No data loss occurs
- Users can manually remove old keywords via UI if desired
- Monitor keywords continue to work if no regex is defined

## Files Modified

1. `regex_filters.py`: Added 3 new functions, enhanced extraction logic
2. `main.py`: Updated imports, rewrote forwarding logic, updated help text
3. `inline_ui_v2.py`: Modified UI for extract filters, enhanced validation
4. `test_regex_semantics.py`: New comprehensive test suite

## Performance Considerations

- No performance degradation; priority check is O(1)
- Regex compilation still cached per watch
- Timeout protection prevents runaway patterns
- Pattern count limits prevent memory issues

## Error Handling

All error paths provide clear, actionable messages:
- Invalid patterns: Shows specific regex error
- Pattern too long: Shows max length (500)
- Too many patterns: Shows max count (100)
- Compilation failures: Detailed syntax error messages
- Network errors: User-friendly explanations

## Future Enhancements

Potential improvements for future versions:
- Pattern testing interface in UI
- Pattern performance metrics
- Pattern sharing between watches
- Regex pattern library/templates
- Visual regex builder

## Conclusion

These changes provide:
- **Clarity**: Clear semantics for both modes
- **Control**: Regex priority gives users precise control
- **Simplicity**: Extract mode simplified to regex-only
- **Robustness**: Enhanced validation and error handling
- **Documentation**: Comprehensive help and inline hints

The implementation follows best practices:
- Comprehensive testing
- Backward compatibility
- Clear error messages
- Detailed logging
- Updated documentation
