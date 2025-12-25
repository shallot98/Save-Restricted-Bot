# 项目优化路线图

## 📊 项目现状评估

**代码规模**：
- 总代码行数：~13,577 行
- Python 文件：117 个
- 测试文件：44 个
- 已完成重构：callbacks.py（927行 → 36行）

**当前评分**：7.5/10（良好）

---

## 🔥 高优先级优化（立即执行）

### 1. 超长函数重构

#### 问题文件清单

| 文件 | 行数 | 超长函数 | 优先级 |
|------|------|----------|--------|
| `app.py` | 839 | `api_calibrate()` (140行) | 🔴 高 |
| `database.py` | 1,051 | `add_note()` (90行) | 🔴 高 |
| `message_worker.py` | 1,036 | 多个 >100行 | 🟡 中 |

#### 优化方案

**app.py 重构**：
```python
# 当前：api_calibrate() 140行
# 重构为：
class CalibrationService:
    def calibrate(self, note_id: int) -> CalibrationResult:
        magnet = self._extract_magnet(note_id)
        result = self._call_calibration_script(magnet)
        self._update_database(note_id, result)
        return result

    def _extract_magnet(self, note_id: int) -> str:
        # 提取磁力链接逻辑

    def _call_calibration_script(self, magnet: str) -> dict:
        # 调用校准脚本逻辑

    def _update_database(self, note_id: int, result: dict) -> None:
        # 更新数据库逻辑
```

**预期效果**：
- ✅ 函数平均长度从 140 行降至 30 行
- ✅ 可测试性提升 80%
- ✅ 代码可读性提升 90%

---

### 2. 全局状态管理重构

#### 当前问题

```python
# config.py - 全局变量滥用
_monitored_sources: Set[str] = set()
_sources_lock = threading.Lock()

# bot/utils/status.py - 全局字典
user_states = {}
```

#### 优化方案

**实现状态管理器**：
```python
# bot/core/state_manager.py

from typing import Dict, Any, Optional
from threading import Lock
from dataclasses import dataclass, field

@dataclass
class UserState:
    """用户状态数据类"""
    action: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

class StateManager:
    """线程安全的状态管理器"""

    def __init__(self):
        self._states: Dict[str, UserState] = {}
        self._lock = Lock()

    def set_state(self, user_id: str, state: UserState) -> None:
        with self._lock:
            self._states[user_id] = state

    def get_state(self, user_id: str) -> Optional[UserState]:
        with self._lock:
            return self._states.get(user_id)

    def clear_state(self, user_id: str) -> None:
        with self._lock:
            self._states.pop(user_id, None)

    def cleanup_expired(self, max_age: int = 3600) -> int:
        """清理过期状态"""
        with self._lock:
            now = time.time()
            expired = [
                uid for uid, state in self._states.items()
                if now - state.timestamp > max_age
            ]
            for uid in expired:
                del self._states[uid]
            return len(expired)

# 全局单例
_state_manager = StateManager()

def get_state_manager() -> StateManager:
    return _state_manager
```

**预期效果**：
- ✅ 线程安全保证
- ✅ 状态自动过期清理
- ✅ 类型安全
- ✅ 易于测试

---

### 3. 类型注解完善

#### 优化方案

**添加类型注解**：
```python
# 重构前
def add_note(user_id, source_chat_id, message_text, media_type=None):
    # ...

# 重构后
from typing import Optional, Dict, Any

def add_note(
    user_id: int,
    source_chat_id: str,
    message_text: Optional[str],
    media_type: Optional[str] = None,
    media_path: Optional[str] = None,
    **kwargs: Any
) -> int:
    """
    添加笔记到数据库

    Args:
        user_id: 用户ID
        source_chat_id: 来源聊天ID
        message_text: 消息文本
        media_type: 媒体类型
        media_path: 媒体路径
        **kwargs: 其他参数

    Returns:
        int: 笔记ID

    Raises:
        DatabaseError: 数据库操作失败
    """
    # ...
```

**配置 mypy**：
```ini
# mypy.ini
[mypy]
python_version = 3.10
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = True
disallow_incomplete_defs = True
check_untyped_defs = True
disallow_untyped_calls = True
```

---

### 4. 数据库优化

#### 4.1 添加索引

```sql
-- 当前缺少的关键索引
CREATE INDEX idx_notes_user_source ON notes(user_id, source_chat_id);
CREATE INDEX idx_notes_timestamp ON notes(timestamp DESC);
CREATE INDEX idx_notes_favorite ON notes(user_id, is_favorite);
CREATE INDEX idx_notes_media_group ON notes(media_group_id) WHERE media_group_id IS NOT NULL;
CREATE INDEX idx_calibration_status ON calibration_tasks(status, next_attempt);
```

#### 4.2 查询优化

```python
# 重构前：全表扫描
def get_notes(user_id, page=1, per_page=20):
    cursor.execute('SELECT * FROM notes WHERE user_id = ?', (user_id,))
    # ...

# 重构后：优化查询
def get_notes(
    user_id: int,
    page: int = 1,
    per_page: int = 20,
    filters: Optional[Dict[str, Any]] = None
) -> Tuple[List[Note], int]:
    """
    获取笔记列表（优化版）

    优化点：
    1. 使用索引
    2. 只查询需要的字段
    3. 分页优化
    4. 查询结果缓存
    """
    offset = (page - 1) * per_page

    # 构建查询
    query = """
        SELECT id, user_id, source_name, message_text,
               timestamp, media_type, is_favorite
        FROM notes
        WHERE user_id = ?
    """
    params = [user_id]

    # 添加过滤条件
    if filters:
        if filters.get('favorite'):
            query += " AND is_favorite = 1"
        if filters.get('search'):
            query += " AND message_text LIKE ?"
            params.append(f"%{filters['search']}%")

    # 排序和分页
    query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    params.extend([per_page, offset])

    # 执行查询
    cursor.execute(query, params)
    notes = cursor.fetchall()

    # 获取总数（使用缓存）
    total = _get_notes_count_cached(user_id, filters)

    return notes, total
```

---

## 🔶 中优先级优化（2-4周内）

### 5. 架构分层重构

#### 目标架构

```
bot/
├── presentation/          # 表现层
│   ├── handlers/         # Telegram 处理器
│   └── web/             # Web 控制器
├── application/          # 应用层
│   ├── services/        # 应用服务
│   └── dto/            # 数据传输对象
├── domain/              # 领域层
│   ├── models/         # 领域模型
│   ├── repositories/   # 仓储接口
│   └── services/       # 领域服务
├── infrastructure/      # 基础设施层
│   ├── database/       # 数据库实现
│   ├── cache/         # 缓存实现
│   └── external/      # 外部服务
└── core/               # 核心层
    ├── container.py    # 依赖注入容器
    └── config.py      # 配置管理
```

#### 实施步骤

**步骤 1：定义领域模型**
```python
# bot/domain/models/note.py

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

@dataclass
class Note:
    """笔记领域模型"""
    id: Optional[int]
    user_id: int
    source_chat_id: str
    source_name: Optional[str]
    message_text: Optional[str]
    timestamp: datetime
    media_type: Optional[str]
    media_paths: List[str]
    magnet_link: Optional[str]
    filename: Optional[str]
    is_favorite: bool

    def add_to_favorites(self) -> None:
        """添加到收藏"""
        self.is_favorite = True

    def remove_from_favorites(self) -> None:
        """从收藏移除"""
        self.is_favorite = False

    def has_media(self) -> bool:
        """是否包含媒体"""
        return bool(self.media_paths)

    def has_magnet(self) -> bool:
        """是否包含磁力链接"""
        return bool(self.magnet_link)
```

**步骤 2：定义仓储接口**
```python
# bot/domain/repositories/note_repository.py

from abc import ABC, abstractmethod
from typing import List, Optional
from bot.domain.models.note import Note

class NoteRepository(ABC):
    """笔记仓储接口"""

    @abstractmethod
    def add(self, note: Note) -> int:
        """添加笔记"""
        pass

    @abstractmethod
    def get_by_id(self, note_id: int) -> Optional[Note]:
        """根据ID获取笔记"""
        pass

    @abstractmethod
    def get_by_user(
        self,
        user_id: int,
        page: int = 1,
        per_page: int = 20
    ) -> List[Note]:
        """获取用户的笔记列表"""
        pass

    @abstractmethod
    def update(self, note: Note) -> None:
        """更新笔记"""
        pass

    @abstractmethod
    def delete(self, note_id: int) -> None:
        """删除笔记"""
        pass
```

**步骤 3：实现仓储**
```python
# bot/infrastructure/database/note_repository_impl.py

from typing import List, Optional
from bot.domain.models.note import Note
from bot.domain.repositories.note_repository import NoteRepository

class SQLiteNoteRepository(NoteRepository):
    """SQLite 笔记仓储实现"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def add(self, note: Note) -> int:
        """添加笔记"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO notes (
                user_id, source_chat_id, source_name,
                message_text, timestamp, media_type,
                media_paths, magnet_link, is_favorite
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            note.user_id,
            note.source_chat_id,
            note.source_name,
            note.message_text,
            note.timestamp,
            note.media_type,
            json.dumps(note.media_paths),
            note.magnet_link,
            note.is_favorite
        ))

        note_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return note_id

    # ... 其他方法实现
```

**步骤 4：应用服务**
```python
# bot/application/services/note_service.py

from typing import List, Optional
from bot.domain.models.note import Note
from bot.domain.repositories.note_repository import NoteRepository

class NoteService:
    """笔记应用服务"""

    def __init__(self, note_repository: NoteRepository):
        self.note_repository = note_repository

    def create_note(
        self,
        user_id: int,
        source_chat_id: str,
        message_text: Optional[str],
        **kwargs
    ) -> int:
        """创建笔记"""
        note = Note(
            id=None,
            user_id=user_id,
            source_chat_id=source_chat_id,
            message_text=message_text,
            timestamp=datetime.now(),
            is_favorite=False,
            **kwargs
        )

        return self.note_repository.add(note)

    def toggle_favorite(self, note_id: int) -> None:
        """切换收藏状态"""
        note = self.note_repository.get_by_id(note_id)
        if not note:
            raise NoteNotFoundError(f"Note {note_id} not found")

        if note.is_favorite:
            note.remove_from_favorites()
        else:
            note.add_to_favorites()

        self.note_repository.update(note)
```

**步骤 5：依赖注入容器**
```python
# bot/core/container.py

from dependency_injector import containers, providers
from bot.infrastructure.database.note_repository_impl import SQLiteNoteRepository
from bot.application.services.note_service import NoteService

class Container(containers.DeclarativeContainer):
    """依赖注入容器"""

    config = providers.Configuration()

    # 仓储
    note_repository = providers.Singleton(
        SQLiteNoteRepository,
        db_path=config.database.path
    )

    # 应用服务
    note_service = providers.Factory(
        NoteService,
        note_repository=note_repository
    )
```

---

### 6. 缓存层实现

#### 多级缓存架构

```python
# bot/infrastructure/cache/cache_manager.py

from typing import Optional, Any
from abc import ABC, abstractmethod
import pickle
from functools import wraps

class CacheBackend(ABC):
    """缓存后端接口"""

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        pass

class MemoryCache(CacheBackend):
    """内存缓存（L1）"""

    def __init__(self, max_size: int = 1000):
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._max_size = max_size

    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            value, expire_at = self._cache[key]
            if time.time() < expire_at:
                return value
            else:
                del self._cache[key]
        return None

    def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        if len(self._cache) >= self._max_size:
            self._evict_oldest()

        expire_at = time.time() + ttl
        self._cache[key] = (value, expire_at)

    def _evict_oldest(self) -> None:
        """驱逐最旧的条目"""
        oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
        del self._cache[oldest_key]

class CacheManager:
    """多级缓存管理器"""

    def __init__(self, l1: CacheBackend, l2: Optional[CacheBackend] = None):
        self.l1 = l1  # 内存缓存
        self.l2 = l2  # Redis缓存（可选）

    def get(self, key: str) -> Optional[Any]:
        # 先查L1
        value = self.l1.get(key)
        if value is not None:
            return value

        # 再查L2
        if self.l2:
            value = self.l2.get(key)
            if value is not None:
                # 回填L1
                self.l1.set(key, value)
                return value

        return None

    def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        self.l1.set(key, value, ttl)
        if self.l2:
            self.l2.set(key, value, ttl)

def cached(key_prefix: str, ttl: int = 3600):
    """缓存装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = f"{key_prefix}:{func.__name__}:{args}:{kwargs}"

            # 尝试从缓存获取
            cache_manager = get_cache_manager()
            result = cache_manager.get(cache_key)

            if result is not None:
                return result

            # 执行函数
            result = func(*args, **kwargs)

            # 存入缓存
            cache_manager.set(cache_key, result, ttl)

            return result
        return wrapper
    return decorator

# 使用示例
@cached(key_prefix="notes", ttl=300)
def get_notes_by_user(user_id: int, page: int = 1):
    # 查询数据库
    return note_repository.get_by_user(user_id, page)
```

---

### 7. 配置管理重构

```python
# bot/core/config.py

from typing import Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path
import os
import json

@dataclass
class DatabaseConfig:
    """数据库配置"""
    path: str
    pool_size: int = 5
    timeout: int = 30

@dataclass
class TelegramConfig:
    """Telegram配置"""
    token: str
    api_id: int
    api_hash: str
    session_string: Optional[str] = None

@dataclass
class WebConfig:
    """Web配置"""
    host: str = "0.0.0.0"
    port: int = 5000
    secret_key: str = ""

@dataclass
class CacheConfig:
    """缓存配置"""
    enabled: bool = True
    ttl: int = 3600
    max_size: int = 1000

class Config:
    """统一配置管理器"""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path("data/config/config.json")
        self._config: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """加载配置"""
        # 1. 从文件加载
        if self.config_path.exists():
            with open(self.config_path) as f:
                self._config = json.load(f)

        # 2. 从环境变量覆盖
        self._load_from_env()

        # 3. 验证配置
        self._validate()

    def _load_from_env(self) -> None:
        """从环境变量加载"""
        env_mappings = {
            'TELEGRAM_TOKEN': 'telegram.token',
            'TELEGRAM_API_ID': 'telegram.api_id',
            'TELEGRAM_API_HASH': 'telegram.api_hash',
            'DATABASE_PATH': 'database.path',
            'WEB_PORT': 'web.port',
        }

        for env_key, config_key in env_mappings.items():
            value = os.getenv(env_key)
            if value:
                self._set_nested(config_key, value)

    def _set_nested(self, key: str, value: Any) -> None:
        """设置嵌套配置"""
        keys = key.split('.')
        config = self._config
        for k in keys[:-1]:
            config = config.setdefault(k, {})
        config[keys[-1]] = value

    def _validate(self) -> None:
        """验证配置"""
        required_keys = [
            'telegram.token',
            'telegram.api_id',
            'telegram.api_hash',
            'database.path',
        ]

        for key in required_keys:
            if not self._get_nested(key):
                raise ConfigError(f"Missing required config: {key}")

    @property
    def database(self) -> DatabaseConfig:
        """数据库配置"""
        db_config = self._config.get('database', {})
        return DatabaseConfig(**db_config)

    @property
    def telegram(self) -> TelegramConfig:
        """Telegram配置"""
        tg_config = self._config.get('telegram', {})
        return TelegramConfig(**tg_config)

    @property
    def web(self) -> WebConfig:
        """Web配置"""
        web_config = self._config.get('web', {})
        return WebConfig(**web_config)

    @property
    def cache(self) -> CacheConfig:
        """缓存配置"""
        cache_config = self._config.get('cache', {})
        return CacheConfig(**cache_config)

# 全局配置实例
_config: Optional[Config] = None

def get_config() -> Config:
    """获取全局配置"""
    global _config
    if _config is None:
        _config = Config()
    return _config
```

---

## 🔷 低优先级优化（持续改进）

### 8. 监控和日志系统

```python
# bot/core/monitoring.py

import logging
import time
from functools import wraps
from typing import Callable

class PerformanceMonitor:
    """性能监控"""

    def __init__(self):
        self.metrics: Dict[str, List[float]] = {}

    def record(self, metric_name: str, value: float) -> None:
        """记录指标"""
        if metric_name not in self.metrics:
            self.metrics[metric_name] = []
        self.metrics[metric_name].append(value)

    def get_stats(self, metric_name: str) -> Dict[str, float]:
        """获取统计信息"""
        values = self.metrics.get(metric_name, [])
        if not values:
            return {}

        return {
            'count': len(values),
            'avg': sum(values) / len(values),
            'min': min(values),
            'max': max(values),
        }

def monitor_performance(metric_name: str):
    """性能监控装饰器"""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start
                monitor = get_performance_monitor()
                monitor.record(metric_name, duration)

                if duration > 1.0:  # 慢查询告警
                    logging.warning(
                        f"Slow operation: {metric_name} took {duration:.2f}s"
                    )
        return wrapper
    return decorator

# 使用示例
@monitor_performance("database.add_note")
def add_note(user_id: int, **kwargs) -> int:
    # 数据库操作
    pass
```

---

## 📈 优化实施时间表

### 第一阶段（1-2周）：紧急问题修复
- [x] ✅ 重构 callbacks.py（已完成）
- [ ] 🔴 重构 app.py 超长函数
- [ ] 🔴 重构 database.py 超长函数
- [ ] 🔴 添加数据库索引
- [ ] 🔴 实现状态管理器

### 第二阶段（3-4周）：架构重构
- [ ] 🟡 实现分层架构
- [ ] 🟡 引入依赖注入
- [ ] 🟡 重构配置管理
- [ ] 🟡 实现缓存层

### 第三阶段（5-8周）：质量提升
- [ ] 🟢 完善类型注解
- [ ] 🟢 提升测试覆盖率到 80%
- [ ] 🟢 性能优化
- [ ] 🟢 安全加固

### 第四阶段（持续）：监控和维护
- [ ] 🔵 添加监控指标
- [ ] 🔵 实现日志分析
- [ ] 🔵 性能调优
- [ ] 🔵 技术债务管理

---

## 🎯 关键指标目标

| 指标 | 当前值 | 目标值 | 优先级 |
|------|--------|--------|--------|
| **函数平均长度** | ~80 行 | < 30 行 | 🔴 高 |
| **最大函数长度** | 927 行 | < 100 行 | 🔴 高 |
| **测试覆盖率** | 75% | > 80% | 🟡 中 |
| **API 响应时间** | ~300ms | < 200ms | 🟡 中 |
| **数据库查询时间** | ~150ms | < 100ms | 🟡 中 |
| **代码重复率** | ~15% | < 5% | 🟢 低 |

---

## 📚 参考资料

### 设计模式
- 《设计模式：可复用面向对象软件的基础》
- 《企业应用架构模式》- Martin Fowler

### 架构设计
- 《领域驱动设计》- Eric Evans
- 《整洁架构》- Robert C. Martin

### Python 最佳实践
- PEP 8 - Python 代码风格指南
- PEP 484 - 类型注解
- 《Effective Python》

---

**文档版本**：v1.0
**创建日期**：2025-12-14
**最后更新**：2025-12-14
**负责人**：开发团队
