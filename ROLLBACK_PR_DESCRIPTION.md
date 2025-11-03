# Rollback: Revert to Pre-Regex Version (Post-PR #6)

## Overview

This PR rolls back the Save-Restricted-Bot to the code state immediately after **PR #6** (`feat-kwlist-add-preserve-forward-source-remove-forward-keyword-info`) and before **PR #7** (regex features) was merged.

## Motivation

This rollback removes complex features (regex, extraction mode, inline UI) to return the bot to a simpler, more stable state focused on core functionality.

## Changes Summary

### Reverted PRs (via hard reset to f2c1331)
- ❌ PR #13: Fix regex semantics for full/extract modes  
- ❌ PR #12: Monitor/extract filters with callback router  
- ❌ PR #11: Fix inline keyboard and peer resolution errors  
- ❌ PR #10: Watch-scoped modes with inline UI  
- ❌ PR #9: Per-watch scoped filters and extraction settings  
- ❌ PR #8: Forward only matched content (extraction mode)  
- ❌ PR #7: Add regex-based keyword monitoring  

### Statistics
- **Python files**: 19 → 6 (68% reduction)
- **Total project files**: 64 → 34 (47% reduction)
- **Main module**: Consolidated all logic into single main.py (547 lines)

### Removed Files
**Modules**: watch_manager.py, regex_filters.py, inline_ui.py, inline_ui_v2.py, callback_router.py, peer_utils.py, demo_extraction.py

**Tests**: test_watch_v3.py, test_inline_keyboard.py, test_inline_ui_v2.py, test_callback_router.py, test_per_watch_filters.py, test_regex_filters.py, test_regex_integration.py, test_regex_semantics.py, test_extraction_mode.py

**Docs**: CALLBACK_ROUTER.md, EXTRACTION_MODE.md, INLINE_KEYBOARD_FIX.md, PER_WATCH_FILTERS.md, REGEX_FILTERS.md, and 9+ more feature-specific docs

### Removed Features
**Commands**: /addre, /delre, /listre, /testre, /mode, /preview, /iktest

**Functionality**:
- Regex-based pattern matching
- Extraction mode (snippet forwarding)
- Per-watch scoped filters
- Inline keyboard UI
- Callback router system
- Peer resolution utilities

### Retained Features (from PR #6 and earlier)
**Core**:
- ✅ Message forwarding from Telegram links
- ✅ Public, private, and bot chat support
- ✅ Multi-post range downloads
- ✅ Real-time progress tracking
- ✅ Auto Session String generation (setup.py)
- ✅ Chinese UI

**Watch System**:
- ✅ /watch list (plain text)
- ✅ /watch add <source> <target> [options]
- ✅ /watch remove <id>

**Filtering**:
- ✅ Keyword whitelist/blacklist (simple, no regex)
- ✅ Case-insensitive matching
- ✅ preserve_source option (PR #6 feature)

## Configuration Schema

### Simplified watch_config.json
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

**Backward Compatibility**: Configs with newer fields (monitor_filters, extract_filters, forward_mode, etc.) will work but those fields will be ignored.

## Testing

All tests pass:
- ✅ test_changes.py - 8/8 tests passed
- ✅ test_feature.py - All structure validation passed
- ✅ verify_changes.py - All core checks passed
- ✅ Syntax checks - main.py, app.py validated

## Deployment

The bot is ready for immediate deployment:
```bash
# Docker Compose (recommended)
docker-compose up -d

# Python directly
python main.py
```

## Migration Notes

Users with newer config files: The bot will safely ignore unknown fields (monitor_filters, extract_filters, forward_mode, enabled, source). Back up your config before upgrading if you want to revert later.

## Tag Created

- **pre-rollback**: Points to main branch before rollback (commit 4ef01b5)
  - Can be used to restore regex/extraction features if needed in the future

## Documentation

- Added: ROLLBACK_CHANGELOG.md (detailed changes)
- Added: ROLLBACK_SUMMARY.md (statistics and testing results)
- Retained: All original docs (README, SETUP_GUIDE, etc.)
- Retained: CHANGES.md, CHANGELOG.md (document PR #5/#6 features)

## Benefits

1. **Simplicity**: Single-file architecture (main.py)
2. **Maintainability**: 68% fewer files, easier to debug
3. **Stability**: Well-tested keyword filtering
4. **Performance**: No regex compilation overhead
5. **User Experience**: Simpler command set, no regex syntax to learn

## Commits in this PR

1. `f2c1331` - Merge PR #6 (target state)
2. `ef6c2d3` - docs: add rollback changelog
3. `7b76f7b` - docs: add rollback summary with statistics

## Checklist

- [x] Hard reset to commit f2c1331 (post-PR #6)
- [x] Verified all removed files are gone
- [x] Verified no imports of removed modules
- [x] Tested all remaining functionality
- [x] All tests pass
- [x] Documentation updated
- [x] Created pre-rollback tag
- [x] Ready for deployment

## References

- Target commit: f2c1331
- Branch: rollback-pre-regex-post-pr6
- Issue: Rollback to pre-regex version (revert PRs #7-#11)
