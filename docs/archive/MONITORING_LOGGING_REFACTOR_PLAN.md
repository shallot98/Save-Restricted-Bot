# 监控和日志系统重构方案

## 📋 目录
- [一、现状分析](#一现状分析)
- [二、重构目标](#二重构目标)
- [三、架构设计](#三架构设计)
- [四、核心模块](#四核心模块)
- [五、实施计划](#五实施计划)
- [六、技术选型](#六技术选型)

---

## 一、现状分析

### 1.1 现有系统
```
src/infrastructure/
├── logging/              # 基础日志系统
│   └── __init__.py      # 简单的日志配置
└── cache/
    └── monitoring.py    # 缓存监控
```

### 1.2 存在问题
- ❌ **缺少性能监控**: 无法追踪请求响应时间、吞吐量
- ❌ **缺少慢查询告警**: 数据库查询性能无监控
- ❌ **缺少错误追踪**: 错误日志分散,无聚合分析
- ❌ **日志格式不统一**: 缺少结构化日志
- ❌ **缺少告警机制**: 无主动告警能力
- ❌ **缺少可视化**: 无监控面板

---

## 二、重构目标

### 2.1 核心目标
1. **性能监控**: 实时追踪系统性能指标
2. **慢查询告警**: 自动检测并告警慢查询
3. **错误追踪**: 聚合分析错误日志
4. **结构化日志**: 统一日志格式,便于分析
5. **告警机制**: 多渠道告警(Telegram/邮件/Webhook)
6. **可视化**: 提供监控面板

### 2.2 设计原则
- **KISS**: 简单易用,避免过度设计
- **YAGNI**: 只实现当前需要的功能
- **DRY**: 统一监控和日志接口
- **可扩展**: 支持插件化扩展

---

## 三、架构设计

### 3.1 整体架构
```
src/infrastructure/observability/
├── __init__.py
├── logging/                    # 日志系统
│   ├── __init__.py
│   ├── structured.py          # 结构化日志
│   ├── formatters.py          # 日志格式化器
│   └── handlers.py            # 日志处理器
├── monitoring/                 # 监控系统
│   ├── __init__.py
│   ├── metrics.py             # 指标收集
│   ├── performance.py         # 性能监控
│   ├── database.py            # 数据库监控
│   └── health.py              # 健康检查
├── tracing/                    # 追踪系统
│   ├── __init__.py
│   ├── context.py             # 追踪上下文
│   └── decorators.py          # 追踪装饰器
├── alerting/                   # 告警系统
│   ├── __init__.py
│   ├── rules.py               # 告警规则
│   ├── channels.py            # 告警渠道
│   └── manager.py             # 告警管理器
└── dashboard/                  # 监控面板
    ├── __init__.py
    ├── api.py                 # API接口
    └── templates/             # 前端模板
```

### 3.2 数据流
```
应用代码
    ↓
[装饰器/中间件]
    ↓
[指标收集器] → [时序数据库] → [监控面板]
    ↓
[日志处理器] → [日志存储] → [日志分析]
    ↓
[告警规则引擎] → [告警渠道] → [Telegram/邮件]
```

---

## 四、核心模块

### 4.1 结构化日志系统

#### 4.1.1 日志格式
```python
{
    "timestamp": "2025-12-20T10:30:45.123Z",
    "level": "ERROR",
    "logger": "bot.handlers.messages",
    "message": "Failed to forward message",
    "context": {
        "user_id": 123456,
        "chat_id": -100123456,
        "message_id": 789
    },
    "error": {
        "type": "FloodWait",
        "message": "Too many requests",
        "traceback": "..."
    },
    "trace_id": "abc123",
    "span_id": "def456"
}
```

#### 4.1.2 核心功能
- **结构化输出**: JSON格式,便于解析
- **上下文注入**: 自动注入trace_id、user_id等
- **敏感信息脱敏**: 自动脱敏密码、token等
- **日志轮转**: 按大小/时间轮转
- **多目标输出**: 文件、控制台、远程服务

### 4.2 性能监控系统

#### 4.2.1 监控指标
```python
# 请求指标
- request_count: 请求总数
- request_duration: 请求耗时(P50/P95/P99)
- request_rate: 请求速率(QPS)

# 数据库指标
- db_query_count: 查询总数
- db_query_duration: 查询耗时
- db_slow_query_count: 慢查询数量
- db_connection_pool: 连接池状态

# 系统指标
- cpu_usage: CPU使用率
- memory_usage: 内存使用率
- disk_usage: 磁盘使用率

# 业务指标
- message_forward_count: 消息转发数
- note_save_count: 笔记保存数
- error_count: 错误数量
```

#### 4.2.2 实现方式
```python
from observability.monitoring import monitor_performance

@monitor_performance(name="forward_message")
async def forward_message(client, message):
    # 自动记录执行时间、成功/失败状态
    ...
```

### 4.3 慢查询监控

#### 4.3.1 监控策略
```python
# 配置阈值
SLOW_QUERY_THRESHOLD = 100  # ms

# 监控方式
1. 装饰器方式: @monitor_query
2. 上下文管理器: with query_monitor():
3. 自动注入: 在connection层自动监控
```

#### 4.3.2 告警规则
```python
# 规则示例
{
    "name": "slow_query_alert",
    "condition": "query_duration > 100ms",
    "threshold": 5,  # 5次慢查询触发告警
    "window": "5m",  # 5分钟窗口
    "channels": ["telegram", "log"]
}
```

### 4.4 错误追踪系统

#### 4.4.1 错误聚合
```python
# 错误指纹
fingerprint = hash(error_type + error_location + error_message)

# 聚合维度
- 错误类型
- 发生位置
- 错误消息
- 影响用户数
- 发生频率
```

#### 4.4.2 错误上下文
```python
{
    "error_id": "err_abc123",
    "fingerprint": "hash_value",
    "first_seen": "2025-12-20T10:00:00Z",
    "last_seen": "2025-12-20T10:30:00Z",
    "count": 15,
    "affected_users": [123, 456],
    "stack_trace": "...",
    "context": {
        "user_id": 123,
        "action": "forward_message"
    }
}
```

### 4.5 告警系统

#### 4.5.1 告警渠道
```python
# Telegram告警
class TelegramAlertChannel:
    async def send(self, alert):
        await bot.send_message(
            admin_chat_id,
            f"🚨 告警: {alert.title}\n"
            f"级别: {alert.level}\n"
            f"详情: {alert.message}"
        )

# 邮件告警
class EmailAlertChannel:
    async def send(self, alert):
        ...

# Webhook告警
class WebhookAlertChannel:
    async def send(self, alert):
        ...
```

#### 4.5.2 告警规则
```python
# 规则配置
rules = [
    {
        "name": "high_error_rate",
        "metric": "error_rate",
        "operator": ">",
        "threshold": 0.05,  # 5%错误率
        "window": "5m",
        "severity": "critical",
        "channels": ["telegram", "email"]
    },
    {
        "name": "slow_query_spike",
        "metric": "slow_query_count",
        "operator": ">",
        "threshold": 10,
        "window": "1m",
        "severity": "warning",
        "channels": ["telegram"]
    }
]
```

### 4.6 监控面板

#### 4.6.1 功能模块
```
1. 实时监控
   - 系统指标实时图表
   - 请求速率实时曲线
   - 错误率实时监控

2. 慢查询分析
   - 慢查询列表
   - 查询耗时分布
   - 查询热点分析

3. 错误追踪
   - 错误列表
   - 错误趋势图
   - 错误详情页

4. 告警管理
   - 告警历史
   - 告警规则配置
   - 告警静默设置
```

#### 4.6.2 技术实现
```python
# Flask API
@app.route('/api/metrics')
def get_metrics():
    return jsonify(metrics_collector.get_all())

@app.route('/api/slow_queries')
def get_slow_queries():
    return jsonify(db_monitor.get_slow_queries())

# 前端: 使用Chart.js实时图表
```

---

## 五、实施计划

### 5.1 Phase 1: 基础设施 (Week 1)
```
✓ 创建目录结构
✓ 实现结构化日志系统
✓ 实现基础指标收集
✓ 实现追踪上下文
```

### 5.2 Phase 2: 监控系统 (Week 2)
```
✓ 实现性能监控装饰器
✓ 实现数据库监控
✓ 实现慢查询检测
✓ 实现健康检查
```

### 5.3 Phase 3: 告警系统 (Week 3)
```
✓ 实现告警规则引擎
✓ 实现Telegram告警渠道
✓ 实现告警管理器
✓ 配置默认告警规则
```

### 5.4 Phase 4: 可视化 (Week 4)
```
✓ 实现监控API
✓ 实现监控面板前端
✓ 集成到现有Web界面
✓ 编写使用文档
```

### 5.5 Phase 5: 集成和优化 (Week 5)
```
✓ 集成到现有代码
✓ 性能优化
✓ 测试和调试
✓ 文档完善
```

---

## 六、技术选型

### 6.1 核心依赖
```python
# requirements.txt 新增
prometheus-client==0.19.0    # 指标收集
structlog==24.1.0            # 结构化日志
psutil==5.9.6                # 系统监控
```

### 6.2 可选依赖
```python
# 高级功能(可选)
opentelemetry-api==1.21.0    # 分布式追踪
sentry-sdk==1.39.0           # 错误追踪服务
```

### 6.3 存储方案
```
1. 指标存储: 内存 + SQLite (轻量级)
2. 日志存储: 文件 + 轮转
3. 告警历史: SQLite
```

---

## 七、使用示例

### 7.1 结构化日志
```python
from observability.logging import get_logger

logger = get_logger(__name__)

# 自动包含上下文
logger.info(
    "Message forwarded",
    user_id=123,
    chat_id=-100123,
    message_id=789
)

# 错误日志自动包含堆栈
try:
    ...
except Exception as e:
    logger.error("Forward failed", exc_info=True)
```

### 7.2 性能监控
```python
from observability.monitoring import monitor_performance

@monitor_performance(name="forward_message")
async def forward_message(client, message):
    # 自动记录执行时间
    ...

# 手动记录指标
from observability.monitoring import metrics

metrics.increment("message.forward.count")
metrics.timing("message.forward.duration", duration_ms)
```

### 7.3 慢查询监控
```python
from observability.monitoring import monitor_query

@monitor_query(threshold_ms=100)
def get_notes(user_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notes WHERE user_id=?", (user_id,))
        return cursor.fetchall()
```

### 7.4 告警配置
```python
from observability.alerting import AlertRule, AlertManager

# 配置告警规则
rule = AlertRule(
    name="high_error_rate",
    metric="error_rate",
    threshold=0.05,
    window_seconds=300,
    severity="critical",
    channels=["telegram"]
)

alert_manager.add_rule(rule)
```

---

## 八、配置示例

### 8.1 日志配置
```python
# config.py
LOGGING = {
    "level": "INFO",
    "format": "json",  # json | text
    "output": ["console", "file"],
    "file": {
        "path": "logs/app.log",
        "max_bytes": 10 * 1024 * 1024,  # 10MB
        "backup_count": 5
    },
    "sensitive_fields": ["password", "token", "api_key"]
}
```

### 8.2 监控配置
```python
# config.py
MONITORING = {
    "enabled": True,
    "slow_query_threshold_ms": 100,
    "metrics_retention_hours": 24,
    "health_check_interval_seconds": 60
}
```

### 8.3 告警配置
```python
# config.py
ALERTING = {
    "enabled": True,
    "channels": {
        "telegram": {
            "enabled": True,
            "chat_id": -100123456
        },
        "email": {
            "enabled": False,
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "from_addr": "alerts@example.com",
            "to_addrs": ["admin@example.com"]
        }
    },
    "rules": [
        {
            "name": "high_error_rate",
            "metric": "error_rate",
            "threshold": 0.05,
            "window_seconds": 300,
            "severity": "critical"
        }
    ]
}
```

---

## 九、性能影响评估

### 9.1 性能开销
```
- 结构化日志: ~5% CPU开销
- 指标收集: ~2% CPU开销
- 慢查询监控: ~1% CPU开销
- 总计: ~8% CPU开销 (可接受)
```

### 9.2 优化策略
```
1. 异步日志写入
2. 指标批量上报
3. 采样策略(高流量场景)
4. 缓存热点数据
```

---

## 十、迁移策略

### 10.1 向后兼容
```python
# 保持现有日志接口
from bot.utils.logger import get_logger  # 仍然可用

# 新代码使用新接口
from observability.logging import get_logger
```

### 10.2 渐进式迁移
```
Phase 1: 新功能使用新系统
Phase 2: 核心模块迁移
Phase 3: 全量迁移
Phase 4: 移除旧系统
```

---

## 十一、监控指标参考

### 11.1 关键指标
```
# RED指标(推荐)
- Rate: 请求速率
- Errors: 错误率
- Duration: 响应时间

# USE指标(系统)
- Utilization: 资源利用率
- Saturation: 饱和度
- Errors: 错误数
```

### 11.2 告警阈值建议
```
- 错误率: > 5% (critical), > 2% (warning)
- 响应时间P99: > 1s (critical), > 500ms (warning)
- 慢查询: > 100ms (warning)
- CPU使用率: > 80% (warning)
- 内存使用率: > 85% (warning)
```

---

## 十二、总结

### 12.1 核心优势
- ✅ **统一监控**: 一站式监控解决方案
- ✅ **主动告警**: 问题及时发现
- ✅ **易于调试**: 结构化日志便于排查
- ✅ **性能可视**: 性能瓶颈一目了然
- ✅ **轻量级**: 最小化性能开销

### 12.2 后续扩展
- 分布式追踪(OpenTelemetry)
- 集成Sentry错误追踪
- Prometheus + Grafana可视化
- 日志聚合服务(ELK/Loki)

---

## 附录

### A. 目录结构完整版
```
src/infrastructure/observability/
├── __init__.py
├── logging/
│   ├── __init__.py
│   ├── structured.py          # 结构化日志实现
│   ├── formatters.py          # JSON/Text格式化器
│   ├── handlers.py            # 文件/控制台/远程处理器
│   ├── context.py             # 日志上下文管理
│   └── filters.py             # 敏感信息过滤
├── monitoring/
│   ├── __init__.py
│   ├── metrics.py             # 指标收集器
│   ├── collectors/
│   │   ├── __init__.py
│   │   ├── system.py          # 系统指标
│   │   ├── database.py        # 数据库指标
│   │   └── application.py     # 应用指标
│   ├── performance.py         # 性能监控装饰器
│   ├── database.py            # 数据库监控
│   ├── health.py              # 健康检查
│   └── storage.py             # 指标存储
├── tracing/
│   ├── __init__.py
│   ├── context.py             # 追踪上下文
│   ├── decorators.py          # 追踪装饰器
│   └── propagation.py         # 上下文传播
├── alerting/
│   ├── __init__.py
│   ├── rules.py               # 告警规则引擎
│   ├── channels/
│   │   ├── __init__.py
│   │   ├── telegram.py        # Telegram渠道
│   │   ├── email.py           # 邮件渠道
│   │   └── webhook.py         # Webhook渠道
│   ├── manager.py             # 告警管理器
│   └── storage.py             # 告警历史存储
└── dashboard/
    ├── __init__.py
    ├── api.py                 # REST API
    ├── routes.py              # Flask路由
    ├── templates/
    │   ├── dashboard.html     # 监控面板
    │   ├── metrics.html       # 指标页面
    │   ├── slow_queries.html  # 慢查询页面
    │   └── alerts.html        # 告警页面
    └── static/
        ├── css/
        └── js/
```

### B. 参考资料
- [Prometheus最佳实践](https://prometheus.io/docs/practices/)
- [结构化日志指南](https://www.structlog.org/)
- [Google SRE Book - Monitoring](https://sre.google/sre-book/monitoring-distributed-systems/)
- [The RED Method](https://www.weave.works/blog/the-red-method-key-metrics-for-microservices-architecture/)
