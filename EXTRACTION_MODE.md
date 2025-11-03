# Extraction Mode Feature

## Overview

The Extraction Mode feature allows the bot to forward only the matched snippets from messages instead of the entire message content. This is useful when you want to focus on specific keywords or patterns within long messages.

## Features

- **Selective Forwarding**: Forward only the text portions that match your filters
- **Smart Context Extraction**: Automatically extracts surrounding sentences or context windows
- **Multiple Match Handling**: Combines multiple matches smartly, merging overlapping snippets
- **Metadata Inclusion**: Each forwarded snippet includes author, chat title, and message link
- **HTML Formatting**: Properly formatted messages with HTML entities escaped
- **Message Splitting**: Automatically splits long messages to fit Telegram's 4096 character limit
- **Named Group Support**: Regex patterns with named groups are extracted intelligently

## Configuration

### Enable/Disable Extraction Mode

```
/mode extract on   # Enable extraction mode
/mode extract off  # Disable extraction mode (default)
/mode show        # View current mode status
```

The extraction mode setting is persisted in `filter_config.json` and survives bot restarts.

## How It Works

### When Extraction Mode is OFF (Default)

The bot forwards complete messages as before:
- Full message text
- Media with captions intact
- All formatting preserved

### When Extraction Mode is ON

The bot extracts and forwards only matched portions:

1. **Keyword Matching**: Extracts the sentence or context window around matched keywords
2. **Regex Matching**: Extracts the exact regex match or named groups if present
3. **Merging**: Overlapping or adjacent matches (within 10 characters) are merged into single snippets
4. **Formatting**: Each snippet is formatted with:
   - Author information
   - Chat/channel title
   - Original message link
   - Match number and snippet text

## Usage Examples

### Basic Keyword Extraction

**Setup:**
```
/watch add @news_channel me whitelist:important,urgent
/mode extract on
```

**Original Message:**
```
Today's weather is nice. This is an important announcement about the meeting. 
Tomorrow will be sunny. We have an urgent update about project X.
```

**Forwarded Message:**
```
👤 作者: John Doe
💬 频道: @news_channel
🔗 链接: https://t.me/news_channel/123

──────────────────────────────

📌 匹配 #1:
This is an important announcement about the meeting.

📌 匹配 #2:
We have an urgent update about project X.
```

### Regex Pattern Extraction

**Setup:**
```
/addre /\$\d+/
/mode extract on
```

**Original Message:**
```
Our company revenue is growing. We made $50000 last quarter and expect 
$75000 next quarter. The market is doing well.
```

**Forwarded Message:**
```
👤 作者: Finance Bot
💬 频道: @finance_news
🔗 链接: https://t.me/finance_news/456

──────────────────────────────

📌 匹配 #1:
$50000

📌 匹配 #2:
$75000
```

### Named Group Extraction

**Setup:**
```
/addre /Price: (?P<amount>\$\d+)/i
/mode extract on
```

With named groups, the bot extracts the captured group content intelligently.

## Preview Command

Test your extraction setup before going live:

```
/preview This is an urgent message about bitcoin reaching $50000 today!
```

This will show you:
- How many matches were found
- What snippets would be extracted
- How they would be formatted
- How many messages would be sent

## Technical Details

### Context Extraction

**For Keywords:**
- First tries to extract the complete sentence (delimited by `.`, `!`, `?`, or newlines)
- If sentence is too long (> 200 chars), extracts a 100-character context window around the keyword
- Attempts to break at word boundaries for readability

**For Regex:**
- Extracts exact match by default
- If pattern has named groups, extracts those instead
- Maintains positional accuracy in the original text

### Snippet Merging

Snippets are merged if:
- They overlap in the text
- They are within 10 characters of each other

This prevents fragmenting closely related matches and improves readability.

### Message Limits

- Maximum 10 snippets per message (prevents spam)
- Maximum 4096 characters per Telegram message
- Automatically splits into multiple messages if needed
- Shows warning if snippets were truncated

### HTML Escaping

All text is properly HTML-escaped to prevent:
- XSS-like issues
- Telegram HTML parsing errors
- Special character display problems

## Compatibility

### Works With:
- Per-watch keyword filters (whitelist/blacklist)
- Global keyword filters
- Global regex filters
- Document filename filtering

### Applies To:
- Text messages
- Messages with captions (photos, videos, documents)
- Channel posts
- Group messages

### Does Not Apply To:
- Media-only messages (no caption)
- When global filters are not configured
- When no matches are found (message is skipped silently)

## Configuration Files

### filter_config.json

```json
{
    "keywords": ["important", "urgent"],
    "patterns": ["/bitcoin|crypto/i", "/\\$\\d+/"],
    "extract_mode": true
}
```

- `keywords`: Global keyword filters (applies to all watches)
- `patterns`: Global regex patterns (applies to all watches)  
- `extract_mode`: Whether extraction mode is enabled (true/false)

## Best Practices

1. **Start with Preview**: Use `/preview` to test your filters before enabling extraction mode
2. **Use Specific Patterns**: More specific keywords/patterns = better quality snippets
3. **Monitor Length**: If getting too many long snippets, refine your patterns
4. **Combine Filters**: Use both whitelist and global filters for fine-tuned control
5. **Test with Real Data**: Enable on one watch first, verify output, then expand

## Troubleshooting

### No Snippets Forwarded

**Possible causes:**
- Extraction mode is off (`/mode show` to check)
- No global filters configured (`/listre` to check patterns)
- Message doesn't match any filters
- Message has no text/caption

### Snippets Too Long

**Solutions:**
- Use more specific regex patterns
- Adjust patterns to match shorter strings
- Keywords will extract full sentences - use regex for precise control

### Snippets Too Short

**Solutions:**
- Keywords extract full sentences by default
- If sentence detection fails, check for proper punctuation
- Context window is 100 chars by default

### Missing Metadata

**Check:**
- Message is from a channel (not anonymous)
- Channel has username or is public
- Author information is available

## Performance Notes

- Regex patterns have 1-second timeout on Unix systems
- Maximum 100 patterns allowed
- Maximum 500 characters per pattern
- Snippet extraction is optimized for speed
- No significant overhead for normal message volumes

## Future Enhancements

Possible future additions (not yet implemented):
- Configurable context window size per watch
- Snippet highlighting with bold/italic
- Custom metadata format templates
- Per-watch extraction mode override
- Snippet deduplication across messages
- Export snippets to file/database

## API for Developers

### Key Functions in `regex_filters.py`

```python
# Extract matches and get snippets
has_matches, snippets = extract_matches(text, keywords, compiled_patterns)

# Format for Telegram
messages = format_snippets_for_telegram(snippets, metadata, include_metadata=True)

# Send each message
for msg in messages:
    bot.send_message(chat_id, msg, parse_mode="html")
```

### Testing

Run tests with:
```bash
python3 test_extraction_mode.py
```

Tests cover:
- Sentence extraction
- Context window extraction
- Keyword snippet extraction
- Regex snippet extraction
- Span merging
- HTML escaping
- Telegram formatting
- Integration scenarios

## Support

For issues or questions:
1. Check this documentation
2. Use `/preview` to test your setup
3. Review test files for examples
4. Check logs for error messages

## Version History

### v1.0.0 (Current)
- Initial extraction mode implementation
- Smart context extraction for keywords
- Named group support for regex
- Automatic snippet merging
- HTML formatting and escaping
- Message splitting for long content
- Preview command for testing
- Comprehensive test coverage
