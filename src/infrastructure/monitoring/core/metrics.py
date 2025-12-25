"""
监控指标数据模型

定义各种类型的监控指标数据结构
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum


class MetricType(Enum):
    """指标类型"""
    COUNTER = "counter"          # 计数器
    GAUGE = "gauge"              # 仪表盘
    HISTOGRAM = "histogram"      # 直方图
    TIMER = "timer"              # 计时器


@dataclass
class Metric:
    """基础指标"""
    name: str
    value: float
    metric_type: MetricType
    timestamp: datetime = field(default_factory=datetime.now)
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'name': self.name,
            'value': self.value,
            'metric_type': self.metric_type.value,
            'timestamp': self.timestamp.isoformat(),
            'tags': self.tags,
            'metadata': self.metadata
        }


@dataclass
class PerformanceMetric(Metric):
    """性能指标"""
    duration_ms: float = 0.0
    endpoint: Optional[str] = None
    method: Optional[str] = None
    status_code: Optional[int] = None

    def __post_init__(self):
        """初始化后处理"""
        if self.value == 0.0:
            self.value = self.duration_ms

        # 添加性能相关的元数据
        if self.endpoint:
            self.metadata['endpoint'] = self.endpoint
        if self.method:
            self.metadata['method'] = self.method
        if self.status_code:
            self.metadata['status_code'] = self.status_code


@dataclass
class DatabaseMetric(Metric):
    """数据库查询指标"""
    query: str = ""
    duration_ms: float = 0.0
    rows_affected: int = 0
    is_slow: bool = False

    def __post_init__(self):
        """初始化后处理"""
        if self.value == 0.0:
            self.value = self.duration_ms

        # 添加数据库相关的元数据
        self.metadata.update({
            'query': self.query[:200] if len(self.query) > 200 else self.query,  # 截断长查询
            'rows_affected': self.rows_affected,
            'is_slow': self.is_slow
        })


@dataclass
class BusinessMetric(Metric):
    """业务指标"""
    category: str = ""
    success: bool = True
    error_type: Optional[str] = None

    def __post_init__(self):
        """初始化后处理"""
        # 添加业务相关的元数据
        self.metadata.update({
            'category': self.category,
            'success': self.success
        })
        if self.error_type:
            self.metadata['error_type'] = self.error_type


@dataclass
class ErrorMetric(Metric):
    """错误指标"""
    error_type: str = ""
    error_message: str = ""
    stacktrace: str = ""
    context: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """初始化后处理"""
        # 添加错误相关的元数据
        self.metadata.update({
            'error_type': self.error_type,
            'error_message': self.error_message[:500],  # 截断长消息
            'stacktrace': self.stacktrace[:1000],  # 截断长堆栈
            'context': self.context
        })
