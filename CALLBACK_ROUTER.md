# Callback Router System (v2)

## Overview

The callback router system provides centralized, schema-based routing for inline keyboard callbacks with comprehensive logging and error handling.

## Callback Data Schema

### Format
```
w:<id>|sec:<section>|act:<action>[|param:value]...
```

### Components

- **watch_id**: Watch ID (truncated to 8 chars) or special value (`list`, `noop`)
- **sec**: Section code (1 character)
  - `m`: Monitor filters
  - `e`: Extract filters
  - `d`: Watch detail/management
  - (empty): Special/system actions
- **act**: Action code (short string)
- **Additional params**: Optional key:value pairs (e.g., `i:3`, `p:2`)

### Size Limit
All callback data is enforced to be ≤ 64 bytes (Telegram limit).

## Sections and Actions

### Watch List (`watch_id=list`)
- `act:page|p:<n>` - Show page N of watch list

### Watch Detail (`sec:d`)
- `act:show` - Show watch detail view
- `act:mode|m:<mode>` - Set forward mode (full/extract)
- `act:preserve` - Toggle preserve source
- `act:enabled` - Toggle enabled state
- `act:preview` - Preview source channel
- `act:del_conf` - Show delete confirmation
- `act:del_yes` - Confirm deletion

### Monitor Filters (`sec:m`)
- `act:menu` - Show filter menu
- `act:add_kw` - Add keyword (triggers input flow)
- `act:add_re` - Add regex (triggers input flow)
- `act:list_kw|p:<n>` - List keywords with pagination
- `act:list_re|p:<n>` - List regex patterns with pagination
- `act:del_kw|i:<index>` - Delete keyword at index
- `act:del_re|i:<index>` - Delete regex at index
- `act:clear_conf` - Show clear all confirmation
- `act:clear_yes` - Confirm clear all

### Extract Filters (`sec:e`)
Same actions as monitor filters (`m`), but operates on extract filters.

### System Actions
- `act:noop` - No operation (display-only buttons)

## Usage Examples

### Building Callback Data

```python
from callback_router import build_callback_data

# Show watch detail
data = build_callback_data("abc123", sec="d", act="show")
# Result: "w:abc123|sec:d|act:show"

# Add monitor keyword
data = build_callback_data("abc123", sec="m", act="add_kw")
# Result: "w:abc123|sec:m|act:add_kw"

# Delete keyword at index 3
data = build_callback_data("abc123", sec="m", act="del_kw", i=3)
# Result: "w:abc123|sec:m|act:del_kw|i:3"

# List page 2
data = build_callback_data("list", act="page", p=2)
# Result: "w:list|act:page|p:2"
```

### Parsing Callback Data

```python
from callback_router import router

data = "w:abc123|sec:m|act:del_kw|i:3"
parsed = router.parse_callback_data(data)
# Result: {'watch_id': 'abc123', 'sec': 'm', 'act': 'del_kw', 'i': '3'}
```

### Registering Handlers

```python
from callback_router import router

def handle_my_action(bot, callback_query, parsed, watch_config):
    """Handle the action"""
    watch_id = parsed["watch_id"]
    # ... do something ...
    bot.answer_callback_query(callback_query.id, "Done!")

# Register handler
router.register("m", "my_action", handle_my_action)
```

## Input Flows

For actions that require user text input (e.g., adding keywords/regex):

1. Handler sets `user_input_states[user_id]` with action details
2. User sends next text message
3. `handle_user_input()` processes the text and completes the action
4. State is cleared

Example flow:
```python
def handle_filter_add_keyword(bot, callback_query, parsed, watch_config):
    user_id = str(callback_query.from_user.id)
    
    # Set input state
    user_input_states[user_id] = {
        "action": "add_keyword",
        "watch_id": parsed["watch_id"],
        "filter_type": "monitor",
        "section": "m",
        "message_id": callback_query.message.id
    }
    
    bot.answer_callback_query(callback_query.id, "Please send keyword...")
```

## Error Handling

### Unknown Actions
If no handler is found, the router provides a helpful error message:
```
❌ 未知操作

区域: m
动作: unknown_action

请返回主菜单重试
```

### Handler Exceptions
If a handler raises an exception:
- Full error is logged with stack trace
- User sees truncated error message (max 100 chars)
- Callback query is always answered to prevent loading spinner

## Logging

Every callback is logged with:
- Full callback data string
- User ID
- Matched handler (if found)
- Section and action codes

Example log output:
```
INFO: Callback received: w:abc123|sec:m|act:menu from user 12345
INFO: Routing to handler: m:menu (watch_id: abc123)
INFO: User 12345 entering keyword input flow for watch abc123, section m
```

For unhandled callbacks:
```
WARNING: No handler found for: x:unknown (watch_id: abc123)
ERROR: Unhandled callback data: w:abc123|sec:x|act:unknown (parsed: {...})
```

## Migration from Legacy Format

The system supports both formats:

### Legacy Format (old)
```
w:<watch_id>:<action>:<param1>:<param2>:...
```

### New Format (v2)
```
w:<id>|sec:<section>|act:<action>|param:value...
```

The callback handler tries the new router first, then falls back to legacy if not matched.

## Testing

Run unit tests:
```bash
python3 test_callback_router.py -v
```

Tests cover:
- Parsing all callback formats
- Building callback data
- Handler registration and routing
- Callback data size limits
- Realistic user flows

## Best Practices

1. **Keep watch_id short**: Use first 8 characters only
2. **Use short section codes**: Single characters (m, e, d)
3. **Use short action codes**: Abbreviations (del_kw, not delete_keyword)
4. **Validate callback length**: Always check ≤ 64 bytes
5. **Log everything**: Use logger.info() for all actions
6. **Handle errors gracefully**: Always answer callback queries
7. **Provide helpful messages**: Guide users back to valid state

## Architecture

```
User clicks button
    ↓
main.py: callback_handler()
    ↓
router.handle_callback()
    ↓
router.parse_callback_data()
    ↓
router.route() → find handler
    ↓
Execute handler(bot, callback_query, parsed, watch_config)
    ↓
Answer callback query (success or error)
```

## Handler Signature

All handlers must follow this signature:

```python
def handler_name(
    bot: Client,
    callback_query: CallbackQuery,
    parsed: Dict[str, str],
    watch_config: Dict
) -> None:
    """
    Handle a callback action
    
    Args:
        bot: Pyrogram bot client
        callback_query: The callback query object
        parsed: Parsed callback data dict
        watch_config: Current watch configuration
    """
    # Implementation
    bot.answer_callback_query(callback_query.id, "Message")
```

## Performance

- O(1) handler lookup via dictionary
- No regex matching needed
- Minimal string operations
- Watch ID truncation happens only during build

## Future Enhancements

Potential improvements:
- Short ID mapping (map long IDs to 3-4 char codes)
- Callback data compression
- State persistence for multi-step flows
- Automatic callback data validation on button creation
- Permission checks in router
