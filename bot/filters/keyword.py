"""
Keyword-based filtering
"""
import logging
from typing import List

from src.domain.entities.watch import WatchTask
from src.domain.services.filter_service import FilterService

logger = logging.getLogger(__name__)


def check_whitelist(message_text: str, whitelist: List[str]) -> bool:
    """Check if message matches keyword whitelist

    Args:
        message_text: Message text to check
        whitelist: List of keywords that should be present

    Returns:
        True if message passes (matches at least one keyword), False otherwise
    """
    task = WatchTask(source="", dest=None, whitelist=whitelist)
    passed = FilterService.should_forward(task, message_text)

    if not whitelist:
        return True

    if passed:
        logger.info("   ✅ 通过关键词白名单过滤")
        return True

    logger.warning(f"   ⏭ 过滤：未匹配关键词白名单 {whitelist}")
    logger.warning(f"   消息文本: {message_text[:200] if message_text else '(空)'}")
    return False


def check_blacklist(message_text: str, blacklist: List[str]) -> bool:
    """Check if message matches keyword blacklist
    
    Args:
        message_text: Message text to check
        blacklist: List of keywords that should NOT be present
        
    Returns:
        True if message should be blocked (matches a blacklist keyword), False otherwise
    """
    task = WatchTask(source="", dest=None, blacklist=blacklist)
    blocked = not FilterService.should_forward(task, message_text)

    if blocked:
        logger.debug("   ⏭ 过滤：匹配到关键词黑名单")

    return blocked
