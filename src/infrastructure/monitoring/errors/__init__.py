"""
错误追踪模块

包含：
- ErrorTracker: 错误采集入口（记录指标 + 触发告警）
- ErrorAggregator: 聚合与去重（按类型+堆栈哈希）
- ErrorAnalyzer: 趋势/热点分析
"""

from .tracker import ErrorTracker, get_error_tracker
from .aggregator import ErrorAggregator, ErrorGroup
from .analyzer import ErrorAnalyzer, get_error_analyzer

__all__ = [
    "ErrorTracker",
    "get_error_tracker",
    "ErrorAggregator",
    "ErrorGroup",
    "ErrorAnalyzer",
    "get_error_analyzer",
]

