"""
Centralized callback query router with unified schema

Callback data format: w:<id>|sec:<section>|act:<action>[|param:value]...

Sections:
- m: Monitor filters
- e: Extract filters
- d: Watch detail
- l: Watch list

Actions:
- menu: Show filter menu
- add_kw: Add keyword (triggers input flow)
- add_re: Add regex (triggers input flow)
- list_kw: List keywords with pagination
- list_re: List regex patterns with pagination
- del_kw: Delete keyword by index
- del_re: Delete regex by index
- clear: Clear all filters (with confirmation)

Examples:
- w:abc123|sec:m|act:menu
- w:abc123|sec:e|act:add_kw
- w:abc123|sec:m|act:del_kw|i:3
- w:abc123|sec:e|act:list_re|p:2
"""

import logging
from typing import Dict, Optional, Tuple, Callable
from pyrogram.types import CallbackQuery

logger = logging.getLogger(__name__)


class CallbackRouter:
    """Central router for callback queries with schema validation"""
    
    def __init__(self):
        self.handlers: Dict[str, Callable] = {}
    
    def register(self, section: str, action: str, handler: Callable):
        """Register a handler for a specific section and action"""
        key = f"{section}:{action}"
        self.handlers[key] = handler
        logger.debug(f"Registered handler for {key}")
    
    def parse_callback_data(self, data: str) -> Optional[Dict[str, str]]:
        """
        Parse callback data into structured dict
        
        Returns:
            Dict with keys: watch_id, sec, act, and any additional params
            None if parsing fails
        """
        try:
            if not data.startswith("w:"):
                return None
            
            # Remove w: prefix
            data = data[2:]
            
            # Split by | to get components
            parts = data.split("|")
            
            # First part is watch_id (or special value like 'list')
            if not parts:
                return None
            
            result = {"watch_id": parts[0]}
            
            # Parse remaining key:value pairs
            for part in parts[1:]:
                if ":" not in part:
                    continue
                key, value = part.split(":", 1)
                result[key] = value
            
            return result
        
        except Exception as e:
            logger.error(f"Error parsing callback data '{data}': {e}")
            return None
    
    def route(self, parsed: Dict[str, str]) -> Optional[Callable]:
        """
        Find the appropriate handler for parsed callback data
        
        Returns:
            Handler function or None if not found
        """
        section = parsed.get("sec", "")
        action = parsed.get("act", "")
        
        key = f"{section}:{action}"
        handler = self.handlers.get(key)
        
        if handler:
            logger.info(f"Routing to handler: {key} (watch_id: {parsed.get('watch_id')})")
        else:
            logger.warning(f"No handler found for: {key} (watch_id: {parsed.get('watch_id')})")
        
        return handler
    
    def handle_callback(self, callback_query: CallbackQuery, bot, watch_config) -> bool:
        """
        Main entry point for handling callbacks
        
        Returns:
            True if handled, False if not our callback
        """
        data = callback_query.data
        
        # Log every callback received
        logger.info(f"Callback received: {data} from user {callback_query.from_user.id}")
        
        # Parse callback data
        parsed = self.parse_callback_data(data)
        
        if parsed is None:
            # Not our callback format
            return False
        
        # Find and execute handler
        handler = self.route(parsed)
        
        if handler is None:
            # No handler found - provide helpful error
            section = parsed.get("sec", "unknown")
            action = parsed.get("act", "unknown")
            
            error_msg = "❌ 未知操作\n\n"
            error_msg += f"区域: {section}\n"
            error_msg += f"动作: {action}\n\n"
            error_msg += "请返回主菜单重试"
            
            logger.error(f"Unhandled callback data: {data} (parsed: {parsed})")
            
            bot.answer_callback_query(
                callback_query.id,
                error_msg,
                show_alert=True
            )
            return True
        
        # Execute handler
        try:
            handler(bot, callback_query, parsed, watch_config)
            return True
        except Exception as e:
            logger.error(f"Error executing handler for {data}: {e}", exc_info=True)
            
            error_summary = str(e)[:100]
            bot.answer_callback_query(
                callback_query.id,
                f"❌ 操作失败: {error_summary}",
                show_alert=True
            )
            return True


def build_callback_data(watch_id: str, section: str = None, action: str = None, **kwargs) -> str:
    """
    Build callback data string from components
    
    Args:
        watch_id: Watch ID or special value (e.g., 'list')
        section: Section code (m, e, d, l, etc.)
        action: Action code
        **kwargs: Additional parameters (e.g., i=3, p=2)
    
    Returns:
        Formatted callback data string (max 64 bytes)
    """
    parts = [f"w:{watch_id}"]
    
    if section:
        parts.append(f"sec:{section}")
    
    if action:
        parts.append(f"act:{action}")
    
    # Add additional parameters
    for key, value in kwargs.items():
        if value is not None:
            parts.append(f"{key}:{value}")
    
    result = "|".join(parts)
    
    # Enforce 64 byte limit
    if len(result.encode('utf-8')) > 64:
        logger.warning(f"Callback data too long ({len(result)} chars): {result}")
        # Truncate watch_id if needed
        if len(watch_id) > 8:
            short_id = watch_id[:8]
            result = result.replace(f"w:{watch_id}", f"w:{short_id}", 1)
            logger.info(f"Truncated watch_id to: {short_id}")
    
    return result


def validate_callback_length(data: str) -> bool:
    """Validate that callback data doesn't exceed 64 bytes"""
    byte_len = len(data.encode('utf-8'))
    if byte_len > 64:
        logger.error(f"Callback data exceeds 64 bytes: {byte_len} bytes, data: {data}")
        return False
    return True


# Global router instance
router = CallbackRouter()
