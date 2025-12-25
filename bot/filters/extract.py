"""
Content extraction using regex patterns
"""
import logging
from typing import List

from src.domain.entities.watch import WatchTask
from src.domain.services.filter_service import FilterService

logger = logging.getLogger(__name__)


def extract_content(message_text: str, extract_patterns: List[str]) -> str:
    """Extract content from message using regex patterns

    Args:
        message_text: Message text to extract from
        extract_patterns: List of regex patterns for extraction

    Returns:
        Extracted content as newline-separated string, or empty string if nothing extracted
    """
    if not extract_patterns:
        return message_text  # No extraction patterns, return original text

    logger.debug(f"   应用提取模式: {extract_patterns}")
    task = WatchTask(source="", dest=None, extract_patterns=extract_patterns)
    extracted = FilterService.extract_content(task, message_text)
    if not extracted:
        logger.debug("   未提取到任何内容")
        return ""

    logger.debug(f"   提取后内容长度: {len(extracted)}")
    return extracted
