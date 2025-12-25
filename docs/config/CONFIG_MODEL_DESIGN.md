# 配置模型设计文档

## 1. 概述

### 1.1 设计目标

本次配置管理重构旨在建立统一、类型安全、易于维护的配置管理系统，解决现有系统的以下问题：

- **多层配置系统并存**：新架构层、兼容层、传统层三层并存，导致配置访问混乱
- **缺乏类型验证**：配置值缺乏类型检查，容易出现运行时错误
- **配置分散**：配置分散在多个文件中，缺乏统一管理
- **验证机制缺失**：缺乏完整的配置验证体系
- **热重载支持不足**：配置变更需要重启服务

### 1.2 技术方案

采用**Pydantic**作为配置模型基础，提供：

- ✅ **强类型验证**：自动进行类型检查和转换
- ✅ **环境变量支持**：自动从环境变量加载配置
- ✅ **默认值管理**：统一管理配置默认值
- ✅ **验证规则**：支持自定义验证逻辑
- ✅ **文档生成**：自动生成配置文档

### 1.3 配置优先级

配置加载遵循以下优先级（从高到低）：

```
环境变量 > 配置文件 > 默认值
```

**示例**：
```python
# 1. 环境变量（最高优先级）
export TOKEN="env_token"

# 2. 配置文件（中等优先级）
# config.json: {"TOKEN": "file_token"}

# 3. 默认值（最低优先级）
# models.py: TOKEN: str = Field(default="")

# 最终结果：TOKEN = "env_token"
```

---

## 2. 配置模型

### 2.1 PathConfig - 路径配置

管理项目中所有路径相关的配置。

**字段定义**：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `base_dir` | Path | 项目根目录 | 项目根目录路径 |
| `data_dir` | Path | `{base_dir}/data` | 数据目录，可通过`DATA_DIR`环境变量覆盖 |

**派生属性**：

| 属性 | 类型 | 说明 |
|------|------|------|
| `config_dir` | Path | 配置文件目录 (`data_dir/config`) |
| `media_dir` | Path | 媒体文件目录 (`data_dir/media`) |
| `config_file` | Path | 主配置文件路径 |
| `watch_file` | Path | 监控配置文件路径 |
| `webdav_file` | Path | WebDAV配置文件路径 |
| `viewer_file` | Path | 查看器配置文件路径 |

**使用示例**：

```python
from src.core.config.models import PathConfig

# 创建路径配置
paths = PathConfig()

# 确保目录存在
paths.ensure_directories()

# 访问路径
print(f"配置目录: {paths.config_dir}")
print(f"媒体目录: {paths.media_dir}")
```

---

### 2.2 MainConfig - 主配置

管理Telegram Bot的核心配置。

**字段定义**：

| 字段 | 类型 | 必填 | 环境变量 | 说明 |
|------|------|------|----------|------|
| `TOKEN` | str | 是* | `TOKEN` | Telegram Bot Token |
| `HASH` | str | 是* | `HASH` | Telegram API Hash |
| `ID` | str | 是* | `ID` | Telegram API ID |
| `STRING` | str | 是* | `STRING` | Telegram Session String |
| `OWNER_ID` | str | 是* | `OWNER_ID` | Bot所有者的Telegram用户ID |

*注：在生产环境（`ENV=production`）中为必填项

**验证规则**：

- 生产环境中所有字段不能为空
- 开发环境允许为空（便于测试）

**使用示例**：

```python
from src.core.config.models import MainConfig

# 从环境变量加载
config = MainConfig()

# 访问配置
print(f"Bot Token: {config.TOKEN}")
print(f"Owner ID: {config.OWNER_ID}")

# 验证配置
try:
    config = MainConfig(TOKEN="", HASH="")  # 生产环境会抛出异常
except ValueError as e:
    print(f"配置验证失败: {e}")
```

---

### 2.3 WatchConfig - 监控配置

管理用户监控源的映射关系。

**字段定义**：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `user_sources` | Dict[str, Dict[str, Any]] | `{}` | 用户ID到监控源的映射 |

**数据结构**：

```json
{
  "user_sources": {
    "123456789": {
      "source_1": {"name": "频道A", "enabled": true},
      "source_2": {"name": "频道B", "enabled": false}
    },
    "987654321": {
      "source_3": {"name": "频道C", "enabled": true}
    }
  }
}
```

**辅助方法**：

| 方法 | 说明 |
|------|------|
| `get_user_sources(user_id)` | 获取指定用户的监控源 |
| `set_user_sources(user_id, sources)` | 设置指定用户的监控源 |
| `get_all_source_ids()` | 获取所有监控源ID集合 |

**使用示例**：

```python
from src.core.config.models import WatchConfig

# 创建监控配置
watch = WatchConfig()

# 设置用户监控源
watch.set_user_sources("123456789", {
    "source_1": {"name": "频道A", "enabled": True}
})

# 获取用户监控源
sources = watch.get_user_sources("123456789")

# 获取所有监控源ID
all_sources = watch.get_all_source_ids()
print(f"监控源总数: {len(all_sources)}")
```

---

### 2.4 WebDAVConfig - WebDAV配置

管理WebDAV远程存储配置。

**字段定义**：

| 字段 | 类型 | 默认值 | 环境变量 | 说明 |
|------|------|--------|----------|------|
| `enabled` | bool | `False` | `WEBDAV_ENABLED` | 是否启用WebDAV |
| `url` | str | `""` | `WEBDAV_URL` | WebDAV服务器URL |
| `username` | str | `""` | `WEBDAV_USERNAME` | 用户名 |
| `password` | str | `""` | `WEBDAV_PASSWORD` | 密码 |
| `base_path` | str | `"/telegram_media"` | `WEBDAV_BASE_PATH` | 基础路径 |
| `keep_local_copy` | bool | `False` | `WEBDAV_KEEP_LOCAL_COPY` | 是否保留本地副本 |

**验证规则**：

- `url`必须以`http://`或`https://`开头

**使用示例**：

```python
from src.core.config.models import WebDAVConfig

# 从环境变量加载
config = WebDAVConfig()

# 或手动创建
config = WebDAVConfig(
    enabled=True,
    url="https://webdav.example.com",
    username="user",
    password="pass"
)

# 验证URL格式
try:
    config = WebDAVConfig(url="invalid_url")  # 会抛出异常
except ValueError as e:
    print(f"URL格式错误: {e}")
```

---

### 2.5 ViewerConfig - 查看器配置

管理外部查看器配置。

**字段定义**：

| 字段 | 类型 | 默认值 | 环境变量 | 说明 |
|------|------|--------|----------|------|
| `viewer_url` | str | `"https://example.com/watch?dn="` | `VIEWER_VIEWER_URL` | 查看器URL模板 |

**验证规则**：

- `viewer_url`必须以`http://`或`https://`开头

**使用示例**：

```python
from src.core.config.models import ViewerConfig

# 创建查看器配置
config = ViewerConfig(
    viewer_url="https://viewer.example.com/watch?dn="
)

# 生成查看链接
def generate_viewer_link(dn: str) -> str:
    return config.viewer_url + dn
```

---

## 3. 配置管理器接口

### 3.1 ConfigManager协议

定义统一的配置管理器接口，所有配置管理器实现都应遵循此协议。

**核心方法**：

| 方法 | 说明 |
|------|------|
| `get(key, default)` | 获取配置值，支持嵌套键（如`"webdav.enabled"`） |
| `set(key, value, persist)` | 设置配置值，可选择是否立即持久化 |
| `reload(config_type)` | 重新加载配置，支持指定配置类型 |
| `save(config_type)` | 保存配置到文件 |
| `validate(config_type)` | 验证配置完整性 |
| `subscribe(callback, key_pattern)` | 订阅配置变更通知 |
| `unsubscribe(subscription_id)` | 取消订阅 |

**使用示例**：

```python
from src.core.config.manager import ConfigManager

# 假设有一个实现了ConfigManager协议的类
manager: ConfigManager = UnifiedConfigManager()

# 获取配置
token = manager.get("TOKEN")
webdav_enabled = manager.get("webdav.enabled", False)

# 设置配置
manager.set("webdav.enabled", True)

# 订阅配置变更
def on_webdav_change(key, old, new):
    print(f"WebDAV配置变更: {key} = {new}")

sub_id = manager.subscribe(on_webdav_change, "webdav.*")

# 重新加载配置
manager.reload("webdav")

# 取消订阅
manager.unsubscribe(sub_id)
```

---

## 4. 配置优先级详解

### 4.1 优先级规则

配置加载遵循以下优先级（从高到低）：

1. **环境变量**（最高优先级）
2. **配置文件**（中等优先级）
3. **默认值**（最低优先级）

### 4.2 环境变量命名规则

不同配置模型使用不同的环境变量前缀：

| 配置模型 | 环境变量前缀 | 示例 |
|----------|--------------|------|
| MainConfig | 无前缀 | `TOKEN`, `HASH`, `ID` |
| WebDAVConfig | `WEBDAV_` | `WEBDAV_ENABLED`, `WEBDAV_URL` |
| ViewerConfig | `VIEWER_` | `VIEWER_VIEWER_URL` |

### 4.3 配置加载流程

```
1. 读取环境变量 (.env文件 + 系统环境变量)
   ↓
2. 读取配置文件 (data/config/*.json)
   ↓
3. 应用默认值 (models.py中定义的Field默认值)
   ↓
4. 合并配置 (环境变量 > 配置文件 > 默认值)
   ↓
5. 验证配置 (Pydantic自动验证)
   ↓
6. 返回配置对象
```

---

## 5. 使用示例

### 5.1 基本使用

```python
from src.core.config.models import MainConfig, WebDAVConfig

# 加载主配置
main_config = MainConfig()
print(f"Bot Token: {main_config.TOKEN}")

# 加载WebDAV配置
webdav_config = WebDAVConfig()
if webdav_config.enabled:
    print(f"WebDAV URL: {webdav_config.url}")
```

### 5.2 环境变量配置

```bash
# .env文件
TOKEN=your_bot_token
HASH=your_api_hash
ID=your_api_id
STRING=your_session_string
OWNER_ID=123456789

WEBDAV_ENABLED=true
WEBDAV_URL=https://webdav.example.com
WEBDAV_USERNAME=user
WEBDAV_PASSWORD=pass
```

```python
from src.core.config.models import MainConfig, WebDAVConfig

# 自动从.env文件加载
main_config = MainConfig()
webdav_config = WebDAVConfig()
```

### 5.3 配置验证

```python
from pydantic import ValidationError
from src.core.config.models import WebDAVConfig

try:
    # 无效的URL格式
    config = WebDAVConfig(url="invalid_url")
except ValidationError as e:
    print(f"配置验证失败: {e}")
    # 输出: WebDAV URL必须以http://或https://开头
```

### 5.4 配置持久化

```python
import json
from pathlib import Path
from src.core.config.models import WebDAVConfig

# 创建配置
config = WebDAVConfig(
    enabled=True,
    url="https://webdav.example.com",
    username="user",
    password="pass"
)

# 保存到文件
config_file = Path("data/config/webdav_config.json")
with open(config_file, 'w') as f:
    json.dump(config.model_dump(), f, indent=4)

# 从文件加载
with open(config_file, 'r') as f:
    data = json.load(f)
    config = WebDAVConfig(**data)
```

---

## 6. 迁移指南

### 6.1 从旧配置系统迁移

**旧代码**：
```python
from config import load_config, getenv

# 旧方式
config = load_config()
token = config.get("TOKEN")
owner_id = getenv("OWNER_ID")
```

**新代码**：
```python
from src.core.config.models import MainConfig

# 新方式
config = MainConfig()
token = config.TOKEN
owner_id = config.OWNER_ID
```

### 6.2 从Settings类迁移

**��代码**：
```python
from src.core.config import settings

# 旧方式
token = settings.get("TOKEN")
webdav_config = settings.webdav_config
```

**新代码**：
```python
from src.core.config.models import MainConfig, WebDAVConfig

# 新方式
main_config = MainConfig()
token = main_config.TOKEN

webdav_config = WebDAVConfig()
if webdav_config.enabled:
    print(webdav_config.url)
```

### 6.3 兼容性说明

为保持向后兼容性，旧的`Settings`类和兼容层函数仍然可用：

```python
# 旧代码仍然可以正常工作
from src.core.config import settings
from config import load_config

# 这些代码不需要修改
token = settings.get("TOKEN")
config = load_config()
```

建议在新代码中使用新的配置模型，旧代码可以逐步迁移。

---

## 7. 最佳实践

### 7.1 配置访问

✅ **推荐**：使用配置模型直接访问
```python
from src.core.config.models import MainConfig

config = MainConfig()
token = config.TOKEN  # 类型安全，IDE自动补全
```

❌ **不推荐**：使用字典访问
```python
config = load_config()
token = config.get("TOKEN")  # 无类型检查，容易出错
```

### 7.2 配置验证

✅ **推荐**：在应用启动时验证配置
```python
from pydantic import ValidationError
from src.core.config.models import MainConfig

try:
    config = MainConfig()
    # 配置验证通过，继续启动
except ValidationError as e:
    print(f"配置错误: {e}")
    exit(1)
```

### 7.3 敏感信息

✅ **推荐**：敏感信息使用环境变量
```bash
# .env文件（不要提交到Git）
TOKEN=your_secret_token
WEBDAV_PASSWORD=your_password
```

❌ **不推荐**：敏感信息写在配置文件中
```json
{
  "TOKEN": "your_secret_token"  // 不要这样做！
}
```

### 7.4 配置文档

✅ **推荐**：使用Field的description参数
```python
TOKEN: str = Field(
    default="",
    description="Telegram Bot Token"
)
```

这样可以自动生成配置文档。

---

## 8. 常见问题

### Q1: 如何覆盖配置文件中的值？

**A**: 使用环境变量，环境变量优先级最高。

```bash
# 配置文件: webdav_config.json
# {"enabled": false}

# 环境变量覆盖
export WEBDAV_ENABLED=true

# 结果: enabled = true
```

### Q2: 如何添加新的配置字段？

**A**: 在对应的配置模型中添加字段定义。

```python
class WebDAVConfig(BaseSettings):
    # 添加新字段
    timeout: int = Field(
        default=30,
        description="连接超时时间（秒）"
    )
```

### Q3: 如何处理配置验证错误？

**A**: 捕获`ValidationError`异常并处理。

```python
from pydantic import ValidationError

try:
    config = MainConfig()
except ValidationError as e:
    for error in e.errors():
        print(f"字段 {error['loc']}: {error['msg']}")
```

### Q4: 配置模型支持嵌套吗？

**A**: 支持，可以使用嵌套的Pydantic模型。

```python
class DatabaseConfig(BaseModel):
    host: str = "localhost"
    port: int = 5432

class MainConfig(BaseSettings):
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
```

---

## 9. 下一步计划

- [ ] **IMPL-2**: 实现配置验证机制
- [ ] **IMPL-3**: 整合环境变量和配置文件加载
- [ ] **IMPL-4**: 迁移现有配置到新管理器
- [ ] **IMPL-5**: 添加配置热重载支持
- [ ] **IMPL-6**: 完善文档和测试

---

## 10. 参考资料

- [Pydantic官方文档](https://docs.pydantic.dev/)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)
