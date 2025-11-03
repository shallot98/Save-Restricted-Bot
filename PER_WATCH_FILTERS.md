# Per-Watch Scoped Filters and Extraction Settings

## Overview

The bot now supports **per-watch** filters and settings, allowing each monitoring task (watch) to have its own independent configuration. This provides much more flexibility and control over message filtering and forwarding.

## Key Features

### 1. Independent Watch Settings

Each watch has its own:
- **Extract Mode**: Forward only matched snippets vs. full messages
- **Keywords/Regex Filtering**: Enable/disable filtering for this watch
- **Preserve Source**: Keep or remove original forwarding attribution
- **Filters**: Unique set of keywords and regex patterns

### 2. Watch Data Model

Each watch contains:

```json
{
  "id": "unique-uuid",
  "source": "source_chat_id",
  "dest": "dest_chat_id_or_me",
  "enabled": true,
  "flags": {
    "extract_mode": false,
    "keywords_enabled": true,
    "preserve_source": false
  },
  "filters": {
    "keywords": ["keyword1", "keyword2"],
    "patterns": ["/pattern1/i", "/pattern2/"]
  }
}
```

### 3. Backward Compatibility

- Automatic migration from old format (v1) to new format (v2)
- Legacy whitelist/blacklist support during migration
- Backup created before migration
- Schema versioning for future upgrades

## Command Reference

### Basic Watch Management

#### List Watches
```
/watch list
```
Shows all your watches with their settings, filter counts, and IDs.

#### Add Watch
```
/watch add <source> <dest> [options]
```

Options:
- `--extract on|off` - Enable/disable extraction mode
- `--kw on|off` - Enable/disable keyword/regex filtering
- `--preserve on|off` - Preserve original message source

Examples:
```
/watch add @channel me
/watch add @channel me --kw on --extract on
/watch add @source @dest --preserve on
```

#### Remove Watch
```
/watch remove <watch_id_or_index>
```

You can use either:
- Numeric index (e.g., `1`, `2`, `3`)
- Watch ID prefix (e.g., `abc123`)

#### Modify Watch Settings
```
/watch set <watch_id> <setting> <value>
```

Settings:
- `extract` - Extraction mode (on/off)
- `kw` - Keywords/regex filtering (on/off)
- `preserve` - Preserve source (on/off)

Examples:
```
/watch set abc123 extract on
/watch set 1 kw off
/watch set abc123 preserve on
```

### Filter Management

#### Keywords

Add keyword:
```
/watch keywords add <watch_id> <keyword>
```

Remove keyword:
```
/watch keywords del <watch_id> <index_or_keyword>
```

List keywords:
```
/watch keywords list <watch_id>
```

Examples:
```
/watch keywords add abc123 urgent
/watch keywords add abc123 important news
/watch keywords del abc123 1
/watch keywords del abc123 urgent
/watch keywords list abc123
```

#### Regex Patterns

Add pattern:
```
/watch regex add <watch_id> <pattern>
```

Remove pattern:
```
/watch regex del <watch_id> <index_or_pattern>
```

List patterns:
```
/watch regex list <watch_id>
```

Examples:
```
/watch regex add abc123 /bitcoin|crypto/i
/watch regex add abc123 /\d{3}-\d{4}/
/watch regex del abc123 1
/watch regex list abc123
```

### Testing

#### Preview Extraction
```
/watch preview <watch_id> <test_text>
```

Tests how a message would be filtered and extracted for a specific watch.

Example:
```
/watch preview abc123 This is an urgent message about bitcoin
```

## Usage Scenarios

### Scenario 1: Basic Forwarding

Forward all messages from a channel:
```
/watch add @source_channel me
```

No filtering, all messages forwarded as-is.

### Scenario 2: Keyword-Based Filtering

Forward only messages containing specific keywords:
```
/watch add @source me --kw on
/watch keywords add <ID> urgent
/watch keywords add <ID> important
/watch keywords add <ID> breaking news
```

Only messages matching keywords will be forwarded.

### Scenario 3: Extraction Mode

Forward only matched snippets instead of full messages:
```
/watch add @source me --kw on --extract on
/watch keywords add <ID> bitcoin
/watch keywords add <ID> crypto
/watch regex add <ID> /\$\d+/
```

Only extracted snippets around matches will be forwarded.

### Scenario 4: Regex Pattern Filtering

Filter messages using regex patterns:
```
/watch add @source me --kw on
/watch regex add <ID> /urgent|important/i
/watch regex add <ID> /\d{3}-\d{4}/
/watch regex add <ID> /bitcoin|ethereum|crypto/i
```

Messages matching any pattern will be forwarded.

### Scenario 5: Multiple Watches with Different Settings

Monitor the same source with different filters:
```
# Watch 1: All urgent messages, extracted
/watch add @news me --kw on --extract on
/watch keywords add <ID1> urgent
/watch keywords add <ID1> breaking

# Watch 2: All crypto news, full messages
/watch add @news @crypto_group --kw on
/watch keywords add <ID2> bitcoin
/watch keywords add <ID2> ethereum
/watch keywords add <ID2> crypto
```

### Scenario 6: Preserve Source Attribution

Keep original forwarding information:
```
/watch add @source @dest --preserve on
```

Useful when you want to maintain attribution chain.

## Filtering Logic

### When Filtering is Disabled (`keywords_enabled = false`)

- All messages are forwarded
- No keyword or regex matching performed
- Extract mode has no effect

### When Filtering is Enabled (`keywords_enabled = true`)

1. **No filters defined**: All messages forwarded (no filtering)
2. **Filters defined**: Only matching messages forwarded

Message matches if:
- ANY keyword matches (case-insensitive), OR
- ANY regex pattern matches

### Extract Mode Behavior

When `extract_mode = true` and message matches:
- Extract snippets around matched keywords/patterns
- Merge overlapping snippets
- Format with metadata (author, channel, link)
- Send as formatted HTML messages
- Split if exceeds Telegram's 4096 char limit

When `extract_mode = false`:
- Forward complete message as-is
- Preserve media attachments
- Use copy or forward based on `preserve_source` flag

## Limits and Safety

### Per-Watch Limits
- **Max patterns**: 100 per watch
- **Max pattern length**: 500 characters
- **Max keywords**: Unlimited (but reasonable)

### Regex Safety
- Compilation timeout: 1 second
- Invalid patterns rejected at add time
- Pattern validation before saving

### Config Safety
- Atomic writes with temp files
- Automatic backups before saves
- Schema versioning for migrations
- Validation on load

## Migration from Old Format

### Automatic Migration

When the bot detects an old format config, it:
1. Creates a backup (`watch_config.json.backup`)
2. Migrates all watches to new format
3. Preserves legacy whitelist/blacklist as `_legacy_*` fields
4. Enables `keywords_enabled` if whitelist/blacklist present
5. Sets `extract_mode = false` (backward compatible)
6. Generates UUIDs for all watches

### Legacy Whitelist/Blacklist

During migration:
- **Whitelist** → Combined into `keywords`, checked with AND logic
- **Blacklist** → Stored separately, checked to skip messages
- Both preserved in `_legacy_whitelist` and `_legacy_blacklist` fields

In forwarding logic:
- Legacy whitelist checked first (any match = continue)
- Legacy blacklist checked next (any match = skip)
- Then per-watch filters applied

## Technical Details

### Config File Structure

```json
{
  "schema_version": 2,
  "users": {
    "user_id": {
      "watch_id": {
        "id": "uuid",
        "source": "chat_id",
        "dest": "chat_id_or_me",
        "enabled": true,
        "flags": {
          "extract_mode": false,
          "keywords_enabled": false,
          "preserve_source": false
        },
        "filters": {
          "keywords": [],
          "patterns": []
        }
      }
    }
  }
}
```

### Watch ID Format

- Generated using UUID4
- Displayed as first 8 characters in UI
- Can be matched by prefix in commands

### Pattern Compilation

Per-watch patterns are:
- Compiled on-demand during forwarding
- Cached during single message processing
- Validated at add time
- Support same format as global patterns: `/pattern/flags`

### Message Routing

1. Incoming message from channel/group
2. Look up watch by source chat ID
3. Check if watch is enabled
4. Apply legacy filters (if present)
5. Apply per-watch filters (if enabled)
6. Extract snippets (if extract mode on)
7. Forward message or snippets to destination

## Best Practices

### Organization

- Use descriptive watch IDs (first 8 chars usually enough)
- Keep filter counts reasonable (< 50 per watch)
- Test with `/watch preview` before deploying

### Performance

- Limit regex complexity (avoid catastrophic backtracking)
- Use keywords when possible (faster than regex)
- Disable filtering when not needed

### Maintenance

- Regularly review watches with `/watch list`
- Remove unused watches
- Update keywords/patterns as needs change
- Use extraction mode to reduce message spam

### Security

- Don't share watch IDs publicly
- Be careful with preserve_source flag
- Validate regex patterns before adding
- Review extracted snippets for sensitive data

## Troubleshooting

### Watch not forwarding messages

1. Check if watch is enabled: `/watch list`
2. Verify filters: `/watch keywords list <ID>` and `/watch regex list <ID>`
3. Test with sample text: `/watch preview <ID> <text>`
4. Check if keywords_enabled is on when filters exist

### Extract mode not working

1. Ensure `extract_mode = on`: `/watch set <ID> extract on`
2. Ensure `keywords_enabled = on`: `/watch set <ID> kw on`
3. Verify filters are defined
4. Test extraction with `/watch preview <ID> <text>`

### Pattern not matching

1. Test pattern with global `/testre <pattern> <text>`
2. Check pattern syntax (use `/pattern/flags` format)
3. Verify case sensitivity (use `/i` flag if needed)
4. Ensure pattern not too complex (timeout = 1s)

### Migration issues

1. Check backup file exists: `watch_config.json.backup`
2. Review migrated config: `/watch list`
3. Manually restore from backup if needed
4. Report issues with config structure

## API Reference

See `watch_manager.py` for full API:

- `load_watch_config()` - Load and migrate if needed
- `save_watch_config()` - Atomic save with backup
- `add_watch()` - Create new watch
- `remove_watch()` - Delete watch
- `update_watch_flag()` - Modify watch settings
- `add_watch_keyword()` - Add keyword filter
- `remove_watch_keyword()` - Remove keyword filter
- `add_watch_pattern()` - Add regex filter
- `remove_watch_pattern()` - Remove regex filter
- `get_watch_by_id()` - Look up watch
- `get_watch_by_source()` - Find watch by source chat
- `validate_watch_config()` - Validate config structure

## Examples

See `test_per_watch_filters.py` for comprehensive examples of:
- Adding/removing watches
- Updating flags
- Managing keywords and patterns
- Migration testing
- Filtering logic testing
