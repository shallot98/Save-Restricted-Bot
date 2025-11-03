# Regex-Based Keyword Monitoring

This document describes the regex-based keyword monitoring feature added to the bot.

## Overview

The bot now supports regular expression patterns in addition to plain keyword filtering. This allows for more sophisticated message filtering and monitoring capabilities.

## Features

- **Plain Keywords**: Simple substring matching (case-insensitive)
- **Regex Patterns**: Full Python regex support with optional flags
- **Safety**: Pattern timeout protection and length/count limits
- **Persistence**: All filters are stored in `filter_config.json`
- **Commands**: Easy management via bot commands

## Bot Commands

### `/addre <pattern>`
Add a new regex pattern to the filter list.

**Examples:**
```
/addre /urgent|important/i
/addre bitcoin
/addre /\d{3}-\d{4}/
/addre /price.*\$\d+/i
```

### `/delre <index>`
Remove a regex pattern by its index number.

**Example:**
```
/delre 1
```

### `/listre`
List all regex patterns with their indices and compilation status.

### `/testre <pattern> <text>`
Test a regex pattern against sample text to verify it works as expected.

**Examples:**
```
/testre /\d{3}-\d{4}/ Call me at 123-4567
/testre bitcoin This is a bitcoin message
/testre /urgent|important/i URGENT: Read this
```

## Pattern Syntax

### Basic Patterns
Simply provide a pattern string:
```
bitcoin
urgent
```
These will be compiled with case-insensitive flag by default.

### Pattern with Flags
Use the `/pattern/flags` syntax:
```
/pattern/i     - case-insensitive
/pattern/m     - multiline
/pattern/s     - dotall (. matches newline)
/pattern/x     - verbose
/pattern/im    - multiple flags
```

### Supported Regex Features

All standard Python regex features are supported:

- **Alternation**: `/bitcoin|crypto|btc/i` matches any of the alternatives
- **Character classes**: `/[A-Z]\d{3}/` matches a letter followed by 3 digits
- **Quantifiers**: `/\d{3,5}/` matches 3 to 5 digits
- **Groups**: `/(urgent|important).*(message|alert)/i`
- **Anchors**: `/^start/` matches at beginning, `/end$/` at end
- **Escape sequences**: `/\d/` for digits, `/\w/` for word chars, `/\s/` for whitespace

### Examples

**Match cryptocurrency mentions:**
```
/bitcoin|crypto|btc|eth|ethereum/i
```

**Match price patterns:**
```
/\$\d+(\.\d{2})?/
```

**Match URLs:**
```
/https?:\/\/[^\s]+/
```

**Match phone numbers:**
```
/\d{3}-\d{3}-\d{4}/
```

**Match email addresses:**
```
/[\w\.-]+@[\w\.-]+\.\w+/
```

## How Filtering Works

When a message is received in a monitored channel:

1. **Per-Watch Filters** (whitelist/blacklist from `/watch add`) are checked first
2. **Global Filters** (keywords and regex patterns from `/addre`) are then checked
3. A message passes if it matches:
   - The per-watch whitelist (and not the blacklist), OR
   - Any global keyword or regex pattern

This allows for flexible filtering:
- Use per-watch filters for channel-specific rules
- Use global filters for patterns you want to apply everywhere

## Configuration File

Filters are stored in `filter_config.json`:

```json
{
    "keywords": [
        "urgent",
        "important",
        "bitcoin"
    ],
    "patterns": [
        "/urgent|important/i",
        "/bitcoin|crypto|btc/i",
        "/\\d{3}-\\d{4}/",
        "/price.*\\$\\d+/i"
    ]
}
```

### Backup
Every time the config is updated, a backup is created at `filter_config.json.backup`.

## Safety Features

### Pattern Length Limit
Maximum pattern length: **500 characters**

Prevents overly complex patterns that could cause performance issues.

### Pattern Count Limit
Maximum number of patterns: **100**

Prevents excessive memory usage.

### Timeout Protection
Regex matching has a **1-second timeout** (on Unix-like systems).

This prevents catastrophic backtracking attacks from malicious or poorly-written patterns.

### Error Handling
Invalid patterns are:
- Caught at add time and rejected with a clear error message
- Marked with an error in `/listre` output
- Skipped during message evaluation

## Integration with Watch System

The regex filtering works seamlessly with the existing `/watch` system:

```bash
# Monitor a channel with per-watch whitelist
/watch add @source_channel me whitelist:urgent,important

# Add global regex patterns that apply to all watches
/addre /bitcoin|crypto/i
/addre /\$\d+/

# Now messages matching either:
# - "urgent" or "important" keywords, OR
# - The bitcoin or price regex patterns
# will be forwarded
```

## Testing Patterns

Before adding a pattern to your filters, test it with `/testre`:

```bash
/testre /bitcoin|crypto/i I bought some Bitcoin today
# Result: ✅ Match found

/testre /\d{3}-\d{4}/ My number is 123-4567
# Result: ✅ Match found at position 13-20

/testre /urgent/i This is a normal message
# Result: ❌ No match
```

## Best Practices

1. **Test First**: Always use `/testre` before adding a pattern
2. **Start Simple**: Begin with simple patterns and add complexity as needed
3. **Use Flags**: Remember to use `/pattern/i` for case-insensitive matching
4. **Escape Special Chars**: Use `\\` to escape special regex characters like `$`, `.`, `*`, etc.
5. **Avoid Greedy Patterns**: Patterns like `.*` can be slow; prefer `.*?` or more specific patterns
6. **Document Complex Patterns**: If a pattern is complex, note what it does

## Troubleshooting

### Pattern Not Matching

**Check case-sensitivity:**
```
/addre /bitcoin/i    ✅ Matches "Bitcoin", "BITCOIN", "bitcoin"
/addre /bitcoin/     ✅ Matches only "bitcoin" (default is case-insensitive)
```

**Test the pattern:**
```
/testre /your-pattern/i Some sample text
```

### Invalid Regex Error

Common issues:
- Unmatched parentheses: `/(abc` should be `/(abc)/`
- Unmatched brackets: `[abc` should be `[abc]`
- Invalid escape: `\x` should be `\\x` or just `x`
- Unclosed group: `(abc|def` should be `(abc|def)`

### Pattern Too Slow

If a pattern times out:
- Avoid nested quantifiers: `(a+)+` is dangerous
- Use possessive quantifiers when possible
- Simplify the pattern or make it more specific

## API / Module Usage

The filtering functions can be imported from `regex_filters.py`:

```python
from regex_filters import (
    load_filter_config,
    save_filter_config,
    compile_patterns,
    matches_filters,
    parse_regex_pattern
)

# Load config
config = load_filter_config()

# Compile patterns
compiled = compile_patterns()

# Check if text matches
if matches_filters("some text", config["keywords"], compiled):
    print("Match found!")
```

## Future Enhancements

Potential features for future versions:
- Per-watch regex patterns (not just global)
- Pattern statistics (match counts, performance)
- Pattern categories/tags
- Import/export pattern libraries
- Pattern templates for common use cases
- Negative lookahead/lookbehind support documentation
