# Inline Keyboard and Peer Resolution Improvements

## Overview

This document describes the improvements made to fix inline keyboard display issues and peer resolution crashes.

## Changes Made

### 1. Session Persistence

**Problem**: Sessions were not persisted across restarts, causing peer cache loss and resolution errors.

**Solution**:
- Sessions are now stored in a configurable directory (`SESSION_DIR` environment variable)
- Default location: `/data/sessions`
- Docker compose mounts this directory as a volume for persistence
- Both bot and user sessions are stored with persistent names

**Configuration**:
```bash
# Set via environment variable
export SESSION_DIR=/path/to/sessions

# Or use default: /data/sessions
```

### 2. Peer Warm-up on Startup

**Problem**: First access to channels/groups after restart would fail with "Peer id invalid" errors.

**Solution**:
- Added `warm_up_peers()` function that runs on startup
- Attempts to resolve all watch sources non-fatally
- Failures are logged but don't prevent bot from starting
- Populates Pyrogram's peer cache before users interact with the bot

**Location**: `peer_utils.py`

### 3. Decoupled UI from Network Calls

**Problem**: `/watch list` would crash if any watch source couldn't be resolved.

**Solution**:
- `get_watch_list_keyboard()` now renders purely from config data
- No `get_chat()` or `resolve_peer()` calls during list rendering
- Source titles and IDs are read from stored watch configuration
- Network calls only happen in callback handlers (preview, add, etc.)

### 4. Safe Peer Resolution Helper

**Problem**: Peer resolution errors would crash callback handlers.

**Solution**:
- Added `ensure_peer()` helper function
- Returns tuple: (success, error_msg, chat_object)
- Handles all peer resolution errors gracefully
- Provides user-friendly error messages
- Used only in callbacks where network access is expected (preview button)

**Usage**:
```python
from peer_utils import ensure_peer

success, error_msg, chat = ensure_peer(app, watch_data)
if not success:
    # Show error to user
    bot.answer_callback_query(callback_query.id, f"❌ {error_msg}", show_alert=True)
    return

# Use chat object safely
print(f"Resolved: {chat.title}")
```

### 5. Preview Handler Implementation

**Problem**: Preview button existed but had no handler, would fail silently.

**Solution**:
- Implemented preview action handler in `inline_ui.py`
- Uses `ensure_peer()` for safe resolution
- Shows channel/group details: title, username, ID, type, member count, description
- Provides clear error messages if bot lacks access
- Includes "Back" button to return to watch details

### 6. /iktest Diagnostic Command

**Problem**: No easy way to test if inline keyboards work in a chat.

**Solution**:
- Added `/iktest` command for quick inline keyboard testing
- Shows simple test message with two buttons
- Verifies callback query handling works
- Displays chat ID, chat type, and user ID for debugging
- Helps diagnose inline keyboard issues before using `/watch list`

**Usage**:
```
User: /iktest
Bot: [Shows test message with inline buttons]
User: [Clicks "Test Button"]
Bot: [Shows alert: "✅ 按钮工作正常！"]
```

### 7. Comprehensive Error Handling

**Problem**: Errors would crash handlers without user-friendly messages.

**Solution**:
- Wrapped `/watch list` command in try/except block
- All callback handlers have error handling
- Errors are logged with full stack traces
- Users receive readable error messages
- Debug mode includes shortened traceback in replies

### 8. Enhanced Logging

**Problem**: Difficult to diagnose issues without visibility into command execution.

**Solution**:
- Added INFO-level logging for all commands
- Logs include: user ID, chat ID, chat type, command text
- Peer resolution attempts are logged
- Errors include full context and stack traces
- Startup logs show peer warm-up results

**Example logs**:
```
2024-01-15 10:30:15 - main - INFO - /watch list called by user 123456789 in chat 123456789
2024-01-15 10:30:15 - peer_utils - INFO - Starting peer warm-up...
2024-01-15 10:30:16 - peer_utils - INFO - ✓ Resolved: Test Channel (-1001234567890)
2024-01-15 10:30:16 - peer_utils - WARNING - ✗ Cannot access Private Group: ChannelPrivate
2024-01-15 10:30:16 - peer_utils - INFO - Peer warm-up complete: 1/2 resolved, 1 failed
```

### 9. Inline Keyboard Improvements

**Problem**: Callback data could exceed 64-byte limit, pagination was limited.

**Solution**:
- Short, safe callback data format: `w:<id>:<action>:<params>`
- Pagination for long watch lists (configurable items per page)
- Pagination for filter lists
- Callback data length validation in tests
- Empty state keyboard for users with no watches

### 10. Comprehensive Tests

**Problem**: No tests for inline keyboard generation and peer resolution.

**Solution**:
- Created `test_inline_keyboard.py` with 16 tests
- Tests keyboard generation for all scenarios
- Tests callback data format and length limits
- Tests peer resolution error handling
- Tests pagination logic
- Tests backward compatibility with old watch formats
- All tests pass successfully

**Run tests**:
```bash
python3 test_inline_keyboard.py -v
```

## Configuration Updates

### Docker Compose

```yaml
services:
  telegram-bot:
    environment:
      - SESSION_DIR=/data/sessions
    volumes:
      - ./data/sessions:/data/sessions
```

### .gitignore

```
# Session directory
data/sessions/
```

## Acceptance Criteria

✅ **All criteria met:**

1. ✅ `/iktest` responds in private and groups with visible inline keyboard and working callback
2. ✅ `/watch list` always responds with inline keyboard without raising exceptions
3. ✅ No crashes from peer resolution during list rendering
4. ✅ Peer lookups only happen in callbacks and are guarded
5. ✅ Peer warm-up runs on startup and logs missing access
6. ✅ Sessions persist across restarts
7. ✅ Peer cache is retained
8. ✅ Preview button works with safe peer resolution
9. ✅ Clear error messages when bot lacks access
10. ✅ Comprehensive logging for debugging
11. ✅ 16 unit tests all passing

## Error Messages

When the bot cannot access a channel/group, users now see clear messages:

- **During preview**: "❌ 无法访问 Channel Name：频道或群组为私有，请确保机器人已加入"
- **Invalid ID**: "❌ 无法访问 Channel Name：ID无效或机器人未加入该频道/群组"
- **Username not found**: "❌ 无法访问 Channel Name：用户名不存在"

## Usage Guide

### For Users

1. **Test inline keyboards**: `/iktest`
2. **View watches**: `/watch list` - Always works, no crashes
3. **Preview channel**: Click "🔍 预览" button in watch details
4. **Add watches**: Bot will verify access during add, not during list

### For Developers

1. **Session persistence**: Configure `SESSION_DIR` environment variable
2. **Peer resolution**: Use `ensure_peer()` for safe network calls
3. **Logging**: Check logs for detailed execution traces
4. **Testing**: Run `python3 test_inline_keyboard.py` before deployment

## Migration Notes

- Existing watch configurations work without changes
- Sessions will be recreated in new location on first run
- Peer warm-up adds ~0.1s delay per watch on startup
- Docker volumes must be configured for persistence

## Future Improvements

1. Add retry logic for FloodWait errors during warm-up
2. Cache peer resolution results with TTL
3. Implement peer resolution queue to avoid rate limits
4. Add health check endpoint that includes peer cache status
5. Support manual peer cache refresh command
