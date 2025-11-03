# Inline UI v2 Migration Guide

## Overview

This document explains the changes made to fix the inline UI callback system and eliminate the '未知操作' (unknown operation) errors.

## Problem Summary

Previously, the inline UI callback system had inconsistent callback data formats:
- Detail buttons used: `w:<id>:mfilter:menu`
- Filter menu buttons used: `w:<id>:monitor:kw:add`

This mismatch caused monitor and extract filter buttons to show '未知操作' error messages.

## Solution

We implemented a centralized callback router system with:
1. **Unified callback data schema** - Consistent format across all buttons
2. **Centralized routing** - Single point of parsing and dispatching
3. **Comprehensive logging** - Every callback is logged with full context
4. **Better error messages** - Actionable guidance instead of generic errors
5. **Backward compatibility** - Legacy format still supported during migration

## New Components

### callback_router.py
- `CallbackRouter` class - Central router for callback queries
- `build_callback_data()` - Helper to build callback data strings
- `validate_callback_length()` - Enforce 64-byte limit
- Schema: `w:<id>|sec:<section>|act:<action>[|param:value]...`

### inline_ui_v2.py
- New keyboard builders using unified callback format
- All callback handlers registered with the router
- Input flow management for adding keywords/regex
- Consistent error handling and logging

### test_callback_router.py
- Unit tests for router parsing and routing
- Tests for callback data building
- Validation of size limits
- Realistic user flow scenarios

### test_inline_ui_v2.py
- Integration tests for keyboard builders
- Tests for all callback handlers
- Input flow testing
- Consistency validation

## Callback Data Schema

### Old Format (Legacy)
```
w:<watch_id>:<action>:<param1>:<param2>:...
```
Examples:
- `w:abc123:detail`
- `w:abc123:mfilter:menu`
- `w:abc123:monitor:kw:add`  ❌ This didn't match the handler!

### New Format (v2)
```
w:<id>|sec:<section>|act:<action>[|param:value]...
```
Examples:
- `w:abc123|sec:d|act:show`
- `w:abc123|sec:m|act:menu`
- `w:abc123|sec:m|act:add_kw` ✅ Now works!
- `w:abc123|sec:e|act:del_re|i:3`

## Section Codes

- `m` - Monitor filters
- `e` - Extract filters
- `d` - Watch detail/management
- (empty) - Special actions (list, noop)

## Action Codes

### Watch Detail (sec=d)
- `show` - Show detail view
- `mode` - Change forward mode
- `preserve` - Toggle preserve source
- `enabled` - Toggle enabled state
- `preview` - Preview source channel
- `del_conf` - Delete confirmation
- `del_yes` - Confirm delete

### Filter Management (sec=m or sec=e)
- `menu` - Show filter menu
- `add_kw` - Add keyword (input flow)
- `add_re` - Add regex (input flow)
- `list_kw` - List keywords
- `list_re` - List regex patterns
- `del_kw` - Delete keyword
- `del_re` - Delete regex
- `clear_conf` - Clear all confirmation
- `clear_yes` - Confirm clear all

### List Actions
- `page` - Watch list pagination

## Migration Path

The system supports both old and new formats during migration:

1. **New callbacks** use v2 format and are handled by new router
2. **Old callbacks** fall back to legacy handler
3. **Gradual migration** - old messages still work
4. **No downtime** - seamless transition

## Key Improvements

### 1. Unified Schema
All callbacks now use the same format with clear structure:
```python
build_callback_data(watch_id, sec="m", act="menu")
# Result: "w:abc123|sec:m|act:menu"
```

### 2. Centralized Routing
Single router handles all callbacks:
```python
router.register("m", "menu", handle_filter_menu)
router.handle_callback(callback_query, bot, watch_config)
```

### 3. Comprehensive Logging
Every callback is logged:
```
INFO: Callback received: w:abc123|sec:m|act:menu from user 12345
INFO: Routing to handler: m:menu (watch_id: abc123)
```

Errors are also logged:
```
WARNING: No handler found for: x:unknown (watch_id: abc123)
ERROR: Unhandled callback data: w:abc123|sec:x|act:unknown
```

### 4. Better Error Messages
Instead of generic '未知操作', users see:
```
❌ 未知操作

区域: m
动作: unknown_action

请返回主菜单重试
```

### 5. Input Flows
Adding keywords/regex now uses proper state management:
1. User clicks "➕ 添加关键词"
2. Bot asks for keyword
3. User sends text
4. Bot validates and adds keyword
5. State is cleaned up
6. User returns to menu

### 6. Size Enforcement
All callback data is validated to be ≤ 64 bytes:
- Watch IDs truncated to 8 characters
- Short section codes (1 char)
- Short action codes (≤ 10 chars)
- Validation on build

## Testing

Run all tests:
```bash
# Callback router tests
python3 test_callback_router.py -v

# Inline UI v2 tests
python3 test_inline_ui_v2.py -v

# Existing tests (should still pass)
python3 test_inline_keyboard.py -v
python3 test_watch_v3.py
```

## Usage Examples

### Building Buttons
```python
from callback_router import build_callback_data
from pyrogram.types import InlineKeyboardButton

# Monitor filter menu button
button = InlineKeyboardButton(
    "📊 监控过滤器",
    callback_data=build_callback_data("abc123", sec="m", act="menu")
)

# Delete keyword button
button = InlineKeyboardButton(
    "🗑️",
    callback_data=build_callback_data("abc123", sec="e", act="del_kw", i=2)
)
```

### Registering Handlers
```python
from callback_router import router

def my_handler(bot, callback_query, parsed, watch_config):
    """Handle custom action"""
    watch_id = parsed["watch_id"]
    # ... do something ...
    bot.answer_callback_query(callback_query.id, "✅ Done!")

# Register
router.register("m", "my_action", my_handler)
```

### Parsing Callbacks
```python
from callback_router import router

data = "w:abc123|sec:m|act:del_kw|i:3"
parsed = router.parse_callback_data(data)
# Result: {'watch_id': 'abc123', 'sec': 'm', 'act': 'del_kw', 'i': '3'}
```

## Files Changed

### New Files
- `callback_router.py` - Callback routing system
- `inline_ui_v2.py` - New inline UI implementation
- `test_callback_router.py` - Router unit tests
- `test_inline_ui_v2.py` - UI integration tests
- `CALLBACK_ROUTER.md` - Detailed documentation
- `INLINE_UI_V2_MIGRATION.md` - This file

### Modified Files
- `main.py` - Updated to use new router with legacy fallback

### Legacy Files (Still Supported)
- `inline_ui.py` - Old implementation, used as fallback

## Rollback Plan

If issues arise, the system can be rolled back:

1. The legacy `inline_ui.py` is still present and functional
2. The callback handler in `main.py` can be reverted to only use legacy:
   ```python
   @bot.on_callback_query()
   def callback_handler(client, callback_query):
       handle_callback_legacy(bot, callback_query)
   ```

## Future Improvements

Potential enhancements:
- Short ID mapping (3-4 char codes instead of 8)
- Callback data compression
- State persistence across bot restarts
- Permission validation in router
- Automatic callback data validation on button creation

## Troubleshooting

### Problem: Buttons still show '未知操作'

**Check:**
1. Is the callback data in new format? (contains `|`)
2. Is the handler registered? (check logs for "Registered handler")
3. Does the section/action match a registered handler?

**Debug:**
Look at logs:
```
INFO: Callback received: <data> from user <id>
WARNING: No handler found for: <sec>:<act>
```

### Problem: Callback data too long

**Solution:**
- Use shorter watch IDs (first 8 chars)
- Use short parameter names (i, p instead of index, page)
- Store complex state in memory, not callback data

### Problem: Input flow doesn't work

**Check:**
1. Is the state set correctly in `user_input_states`?
2. Is `handle_user_input()` being called for text messages?
3. Are watch IDs matching (short vs full)?

**Debug:**
Add logging:
```python
logger.info(f"Input states: {user_input_states}")
```

## Summary

The new callback router system provides:
- ✅ Consistent callback data format
- ✅ All monitor/extract filter buttons work
- ✅ Comprehensive logging for debugging
- ✅ Better error messages for users
- ✅ Proper input flow handling
- ✅ Size limit enforcement
- ✅ Backward compatibility
- ✅ Full test coverage

No more '未知操作' errors!
