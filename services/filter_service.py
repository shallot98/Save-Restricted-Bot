"""
过滤服务模块 - 处理消息过滤逻辑
遵循 SOLID 原则：
- S: 单一职责 - 只负责消息过滤
- O: 开闭原则 - 易于添加新的过滤规则
"""
import re
from typing import List, Optional

class FilterService:
    """消息过滤服务"""

    @staticmethod
    def should_process_message(message_text: str, watch_config: dict) -> bool:
        """
        判断消息是否应该被处理（根据过滤规则）

        Args:
            message_text: 消息文本
            watch_config: 监控配置（包含过滤规则）

        Returns:
            bool: True表示应该处理，False表示应该跳过
        """
        whitelist = watch_config.get("whitelist", [])
        blacklist = watch_config.get("blacklist", [])
        whitelist_regex = watch_config.get("whitelist_regex", [])
        blacklist_regex = watch_config.get("blacklist_regex", [])

        # 检查关键词白名单
        if whitelist:
            if not FilterService._check_keyword_whitelist(message_text, whitelist):
                print(f"   ⏭️ 未匹配关键词白名单，跳过")
                return False

        # 检查关键词黑名单
        if blacklist:
            if FilterService._check_keyword_blacklist(message_text, blacklist):
                print(f"   ⏭️ 匹配关键词黑名单，跳过")
                return False

        # 检查正则白名单
        if whitelist_regex:
            if not FilterService._check_regex_whitelist(message_text, whitelist_regex):
                print(f"   ⏭️ 未匹配正则白名单，跳过")
                return False

        # 检查正则黑名单
        if blacklist_regex:
            if FilterService._check_regex_blacklist(message_text, blacklist_regex):
                print(f"   ⏭️ 匹配正则黑名单，跳过")
                return False

        return True

    @staticmethod
    def _check_keyword_whitelist(text: str, whitelist: List[str]) -> bool:
        """检查关键词白名单 - 至少匹配一个关键词"""
        text_lower = text.lower()
        for keyword in whitelist:
            if keyword.lower() in text_lower:
                print(f"   ✅ 匹配白名单关键词: {keyword}")
                return True
        return False

    @staticmethod
    def _check_keyword_blacklist(text: str, blacklist: List[str]) -> bool:
        """检查关键词黑名单 - 匹配任何一个关键词就拒绝"""
        text_lower = text.lower()
        for keyword in blacklist:
            if keyword.lower() in text_lower:
                print(f"   🚫 匹配黑名单关键词: {keyword}")
                return True
        return False

    @staticmethod
    def _check_regex_whitelist(text: str, patterns: List[str]) -> bool:
        """检查正则白名单 - 至少匹配一个正则"""
        for pattern in patterns:
            try:
                if re.search(pattern, text):
                    print(f"   ✅ 匹配白名单正则: {pattern}")
                    return True
            except re.error as e:
                print(f"   ⚠️ 正则表达式错误: {pattern} - {e}")
        return False

    @staticmethod
    def _check_regex_blacklist(text: str, patterns: List[str]) -> bool:
        """检查正则黑名单 - 匹配任何一个正则就拒绝"""
        for pattern in patterns:
            try:
                if re.search(pattern, text):
                    print(f"   🚫 匹配黑名单正则: {pattern}")
                    return True
            except re.error as e:
                print(f"   ⚠️ 正则表达式错误: {pattern} - {e}")
        return False
