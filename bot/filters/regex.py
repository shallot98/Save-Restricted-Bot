"""
Regex-based filtering
"""
import re
import logging
from typing import List

from src.domain.entities.watch import WatchTask
from src.domain.services.filter_service import FilterService

logger = logging.getLogger(__name__)


def _log_invalid_patterns(patterns: List[str], label: str) -> None:
    for pattern in patterns:
        try:
            re.compile(pattern)
        except re.error as e:
            logger.warning(f"   ⚠️ 正则{label}表达式错误 '{pattern}': {e}")


def check_whitelist_regex(message_text: str, whitelist_regex: List[str]) -> bool:
    """Check if message matches regex whitelist
    
    Args:
        message_text: Message text to check
        whitelist_regex: List of regex patterns that should match
        
    Returns:
        True if message passes (matches at least one pattern), False otherwise
    """
    if not whitelist_regex:
        return True  # No whitelist means pass all

    _log_invalid_patterns(whitelist_regex, "白名单")

    task = WatchTask(source="", dest=None, whitelist_regex=whitelist_regex)
    passed = FilterService.should_forward(task, message_text)
    if not passed:
        logger.debug(f"   ⏭ 过滤：未匹配正则白名单 {whitelist_regex}")
    return passed


def check_blacklist_regex(message_text: str, blacklist_regex: List[str]) -> bool:
    """Check if message matches regex blacklist
    
    Args:
        message_text: Message text to check
        blacklist_regex: List of regex patterns that should NOT match
        
    Returns:
        True if message should be blocked (matches a pattern), False otherwise
    """
    if not blacklist_regex:
        return False  # No blacklist means nothing to block

    _log_invalid_patterns(blacklist_regex, "黑名单")

    task = WatchTask(source="", dest=None, blacklist_regex=blacklist_regex)
    blocked = not FilterService.should_forward(task, message_text)
    if blocked:
        logger.debug("   ⏭ 过滤：匹配到正则黑名单")
    return blocked
