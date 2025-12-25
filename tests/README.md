# 测试目录结构

## 目录说明

### `unit/` - 单元测试
独立的功能模块测试，不依赖外部服务：
- `test_filter_logic.py` - 过滤引擎逻辑
- `test_deduplication.py` - 去重逻辑
- `test_regex_extract.py` - 正则提取
- `test_config_*.py` - 配置管理

### `integration/` - 集成测试
多模块协作测试，可能依赖数据库/队列：
- `test_message_queue.py` - 消息队列
- `test_media_group_dedup.py` - 媒体组去重
- `test_async_*.py` - 异步处理
- `performance_test.py` - 性能测试

### `e2e/` - 端到端测试
完整流程测试（待添加）

### `mobile/` - 移动端测试
Playwright移动端UI测试

### `fixtures/` - 测试工具和数据
- `clean_duplicates.py` - 清理重复数据
- `migrate_data.py` - 数据迁移
- `performance_comparison.py` - 性能对比

### `archived/` - 已归档测试
过时或重复的测试文件，保留用于参考

## 运行测试

```bash
# 运行所有测试
pytest tests/

# 运行单元测试
pytest tests/unit/

# 运行集成测试
pytest tests/integration/

# 运行移动端测试
pytest tests/mobile/

# 生成覆盖率报告
pytest --cov=. --cov-report=html tests/
```
