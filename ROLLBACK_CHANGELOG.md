# Rollback Changelog

## Rollback to Pre-Regex Version (Post-PR #6)

**Date**: November 3, 2024
**Branch**: `rollback-pre-regex-post-pr6`

### Summary

This rollback reverts the codebase to the state immediately after PR #6 was merged, removing all regex, extraction, and inline UI features introduced in PRs #7-#11.

### Reverted PRs

The following PRs have been reverted by resetting to commit `f2c1331`:

1. **PR #13**: Fix regex semantics for full/extract modes
2. **PR #12**: Monitor/extract filters with callback router
3. **PR #11**: Fix inline keyboard not showing and peer resolution errors
4. **PR #10**: Watch-scoped modes with inline UI (channels & groups)
5. **PR #9**: Per-watch scoped filters and extraction settings
6. **PR #8**: Forward only matched content (extraction mode)
7. **PR #7**: Add regex-based keyword monitoring

### Removed Features

#### Commands Removed
- `/addre` - Add regex pattern (global)
- `/delre` - Delete regex pattern (global)
- `/listre` - List regex patterns (global)
- `/testre` - Test regex patterns (global)
- `/mode` - Switch watch mode (full/extract)
- `/preview` - Preview source channel
- `/iktest` - Inline keyboard diagnostic

#### Functionality Removed
- Regex-based pattern matching
- Extraction mode (forward only matched snippets)
- Per-watch scoped filters (monitor_filters, extract_filters)
- Per-watch forward modes (full/extract)
- Inline keyboard UI for watch management
- Callback router system
- Peer resolution utilities
- Session persistence for peer cache

#### Files Removed
- `watch_manager.py` - Watch configuration management module
- `regex_filters.py` - Regex filtering and extraction engine
- `inline_ui.py` - Legacy inline keyboard UI
- `inline_ui_v2.py` - New inline keyboard UI with callback router
- `callback_router.py` - Centralized callback query router
- `peer_utils.py` - Peer resolution utilities
- `demo_extraction.py` - Interactive extraction demo
- Test files:
  - `test_watch_v3.py`
  - `test_inline_keyboard.py`
  - `test_inline_ui_v2.py`
  - `test_callback_router.py`
  - `test_per_watch_filters.py`
  - `test_regex_filters.py`
  - `test_regex_integration.py`
  - `test_regex_semantics.py`
  - `test_extraction_mode.py`
- Documentation files:
  - `CALLBACK_ROUTER.md`
  - `EXTRACTION_MODE.md`
  - `EXTRACTION_MODE_QUICKSTART.md`
  - `INLINE_KEYBOARD_FIX.md`
  - `INLINE_UI_V2_MIGRATION.md`
  - `PER_WATCH_FILTERS.md`
  - `REGEX_FILTERS.md`
  - `REGEX_IMPLEMENTATION_SUMMARY.md`
  - `REGEX_SEMANTICS_FIX.md`
  - `CHANGES_INLINE_KEYBOARD.md`
  - `CHANGES_SUMMARY.md`
  - `IMPLEMENTATION_CHECKLIST.md`
  - `IMPLEMENTATION_SUMMARY.md`
  - `TASK_SUMMARY.md`

### Retained Features (from PR #6 and earlier)

#### Core Functionality
- Basic message forwarding from Telegram links
- Support for public, private, and bot chats
- Multi-post range downloads
- Real-time download/upload progress tracking
- Auto Session String generation via `setup.py`

#### Watch System
- `/watch list` - List all watch tasks (plain text output)
- `/watch add <source> <target> [whitelist:kw1,kw2] [blacklist:kw3,kw4] [preserve_source:true/false]` - Add watch task
- `/watch remove <id>` - Remove watch task

#### Keyword Filtering
- **Whitelist**: Only forward messages containing specified keywords
- **Blacklist**: Don't forward messages containing specified keywords
- Case-insensitive keyword matching
- Multiple keywords separated by commas

#### Watch Options
- **preserve_source**: Preserve original forward source info (default: false)
  - `true`: Use `forward_messages()` to preserve source
  - `false`: Use `copy_message()` to remove source

#### Other Features
- Chinese UI and help text
- Silent forwarding (no error messages to users on failures)
- Docker and Docker Compose support
- Heroku deployment support

### Configuration Schema

#### watch_config.json (Simplified)
```json
{
  "user_id": {
    "source_chat_id": {
      "dest": "dest_chat_id",
      "whitelist": ["keyword1", "keyword2"],
      "blacklist": ["keyword3"],
      "preserve_forward_source": false
    }
  }
}
```

**Schema Changes from Later Versions:**
- No `monitor_filters` or `extract_filters` objects
- No `forward_mode` field
- No `enabled` flag
- No `source` metadata object
- Simplified structure with direct source_chat_id as key

### Migration Notes

#### For Users with Newer Config Files

If you have a `watch_config.json` file from a newer version (with regex/extraction features), the bot will still work but will ignore unknown fields:

**Ignored Fields:**
- `monitor_filters` (patterns, keywords within object)
- `extract_filters` (patterns, keywords within object)
- `forward_mode`
- `enabled`
- `source` (id, type, title)

**Used Fields:**
- `dest` or `target_chat_id` (both supported for backward compatibility)
- `whitelist` (from root level only)
- `blacklist` (from root level only)
- `preserve_forward_source` (from root level only)

**Recommendation**: Back up your current `watch_config.json` before downgrading. You can manually convert it to the simplified format if needed.

### Testing

All existing tests pass:
- ✅ `test_changes.py` - Tests for preserve_forward_source and keyword filtering
- ✅ `test_feature.py` - Tests for config structure and backward compatibility
- ✅ `verify_changes.py` - Verification of core functionality

### Deployment

The bot is ready to deploy using:

**Docker Compose** (Recommended):
```bash
docker-compose up -d
```

**Direct Python**:
```bash
python main.py
```

**Heroku**:
Use the included `Procfile` and set environment variables in Heroku dashboard.

### Rationale

This rollback removes complex features that were causing maintenance overhead and returns the bot to a simpler, more stable state focused on core functionality:

1. **Simplicity**: Single file (`main.py`) contains all logic
2. **Stability**: Well-tested keyword-based filtering
3. **Maintainability**: Less code, fewer dependencies, easier to debug
4. **Performance**: No regex compilation, no complex pattern matching

### Future Considerations

If regex/extraction features are needed again in the future:
1. A tag `pre-rollback` has been created at the commit before this rollback for easy restoration
2. The removed features can be cherry-picked from commits after `f2c1331`
3. Consider a modular architecture if re-implementing these features

### References

- **Target Commit**: `f2c1331` - Merge pull request #6
- **Branch**: `rollback-pre-regex-post-pr6`
- **Original Feature Branch**: PR #6 `feat-kwlist-add-preserve-forward-source-remove-forward-keyword-info`

### Contact

If you encounter any issues after this rollback or need help migrating your configuration, please open an issue on the repository.
