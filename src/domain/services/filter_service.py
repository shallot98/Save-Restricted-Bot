"""
Filter Service
==============

Domain service for message filtering logic.
"""

import logging
import re
from typing import Optional, Set

from src.domain.entities.watch import WatchTask

logger = logging.getLogger(__name__)

# 已记录过的非法正则，避免每条消息重复刷日志
_reported_invalid_patterns: Set[str] = set()


def _report_invalid_pattern(field: str, pattern: str, error: re.error) -> None:
    """非法正则只告警一次；该条规则被跳过，其余规则继续生效。"""
    key = f"{field}:{pattern}"
    if key in _reported_invalid_patterns:
        return
    _reported_invalid_patterns.add(key)
    logger.error("非法正则表达式已被忽略: field=%s pattern=%r error=%s", field, pattern, error)


class FilterService:
    """
    Domain service for message filtering

    Encapsulates the business logic for determining
    whether a message should be forwarded based on
    watch task filter configuration.
    """

    @staticmethod
    def should_forward(task: WatchTask, message_text: Optional[str]) -> bool:
        """
        Determine if message should be forwarded

        Args:
            task: Watch task configuration
            message_text: Message text to check

        Returns:
            True if message should be forwarded
        """
        if getattr(task, "filters_corrupt", False):
            # 过滤器数据损坏时失败方向必须是「拒绝」：宁可漏转，也不能把
            # 本该被拦截的内容放行。
            logger.error(
                "过滤器数据损坏，拒绝转发该来源的消息: source=%s watch_id=%s",
                getattr(task, "source", None),
                getattr(task, "watch_id", None),
            )
            return False

        if not message_text:
            # No text to filter - forward if no whitelist
            return not task.whitelist and not task.whitelist_regex

        text_lower = message_text.lower()

        # Check blacklist first (reject if any match)
        if FilterService._matches_blacklist(task, text_lower, message_text):
            return False

        # Check whitelist (require match if configured)
        if task.whitelist or task.whitelist_regex:
            return FilterService._matches_whitelist(task, text_lower, message_text)

        # No whitelist configured - forward
        return True

    @staticmethod
    def _matches_blacklist(
        task: WatchTask,
        text_lower: str,
        original_text: str
    ) -> bool:
        """Check if text matches any blacklist pattern"""
        # Keyword blacklist
        for keyword in task.blacklist:
            if keyword.lower() in text_lower:
                return True

        # Regex blacklist
        for pattern in task.blacklist_regex:
            try:
                if re.search(pattern, original_text):
                    return True
            except re.error as exc:
                _report_invalid_pattern("blacklist_regex", pattern, exc)
                continue

        return False

    @staticmethod
    def _matches_whitelist(
        task: WatchTask,
        text_lower: str,
        original_text: str
    ) -> bool:
        """Check if text matches any whitelist pattern"""
        # Keyword whitelist
        for keyword in task.whitelist:
            if keyword.lower() in text_lower:
                return True

        # Regex whitelist
        for pattern in task.whitelist_regex:
            try:
                if re.search(pattern, original_text):
                    return True
            except re.error as exc:
                _report_invalid_pattern("whitelist_regex", pattern, exc)
                continue

        return False

    @staticmethod
    def extract_content(task: WatchTask, message_text: str) -> Optional[str]:
        """
        Extract content using task's extract patterns

        Args:
            task: Watch task configuration
            message_text: Message text to extract from

        Returns:
            Extracted content or None
        """
        if not task.extract_patterns:
            return message_text

        extracted_parts: list[str] = []
        for pattern in task.extract_patterns:
            try:
                matches = re.findall(pattern, message_text)
            except re.error as exc:
                _report_invalid_pattern("extract_patterns", pattern, exc)
                continue

            if not matches:
                continue

            # Flatten capturing groups: re.findall returns tuples when pattern has multiple groups
            if isinstance(matches[0], tuple):
                for match_group in matches:
                    extracted_parts.extend(str(item) for item in match_group if item)
            else:
                extracted_parts.extend(str(item) for item in matches if item)

        if not extracted_parts:
            return None

        # Deduplicate while preserving first-seen order (deterministic output)
        unique_parts: list[str] = []
        seen: set[str] = set()
        for part in extracted_parts:
            if part in seen:
                continue
            seen.add(part)
            unique_parts.append(part)

        return "\n".join(unique_parts)
