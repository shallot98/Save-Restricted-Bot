# 校准数据刷新后丢失问题 - 完整诊断和修复方案

## 问题描述
用户反馈：笔记手动校准后，观看按钮可以打开。但刷新页面后，观看按钮又打不开了，说明校准数据丢失。

## 诊断结果

### 1. 数据库层面 ✅ 正常
- `filename` 字段正确更新
- `magnet_link` 字段包含校准后的dn参数
- `message_text` 字段中的磁力链接也包含dn参数

### 2. 数据提取层面 ✅ 正常
运行 `python3 diagnose_calibration.py 979` 显示：
- `extract_all_dns_from_note()` 能正确提取dn参数
- 第一个磁力链接的dn值存在且正确

### 3. 缓存失效问题 ❌ 存在隐患

当前代码在 `web/routes/api.py:164-174`:
```python
# 使缓存失效，确保刷新页面后能看到更新后的数据
try:
    from src.infrastructure.cache.managers import get_note_cache_manager
    cache_manager = get_note_cache_manager()
    # 需要获取note的user_id来失效缓存
    user_id = updated_note.get('user_id')
    if user_id:
        invalidated = cache_manager.invalidate_note(note_id, user_id)
        logger.info(f"✅ 已失效笔记 {note_id} 的缓存 ({invalidated} 个条目)")
except Exception as e:
    logger.warning(f"⚠️ 缓存失效失败 (不影响功能): {e}")
```

**问题**：
1. 异常被捕获但只记录warning，用户看不到失败原因
2. 可能缓存key的生成方式与页面加载时不一致

### 4. 页面渲染流程分析

**服务端渲染路径**：
```
用户刷新 → GET /notes
         → web/routes/notes.py:notes_list()
         → note_service.get_notes() (可能从缓存读取)
         → 每个note调用 extract_all_dns_from_note()
         → 渲染模板 note['all_dns']
         → 前端显示
```

**关键发现**：问题可能在于：
- `note_service.get_notes()` 返回的是**缓存的笔记列表**
- 虽然单个笔记缓存失效了，但**列表缓存可能没失效**
- 页面渲染的是列表缓存中的旧数据

## 根本原因

查看 `src/infrastructure/cache/managers.py:193-200`：

```python
def invalidate_note(self, note_id: int, user_id: int) -> int:
    """Invalidate cache for a specific note"""
    # Invalidate individual note
    deleted = self._cache.delete(self._make_key(f"note:{note_id}"))
    # Also invalidate list caches for the user
    deleted += self._cache.delete_pattern(f"{self._key_prefix}:list:{user_id}:*")
    deleted += self._cache.delete_pattern(f"{self._key_prefix}:count:{user_id}:*")
    return deleted
```

这里失效的是 `list:{user_id}:*`，但查看 `src/application/services/note_service.py:93-109`:

```python
user_part = str(user_id) if user_id is not None else "all"
source_part = source_chat_id or "all"
search_part = search_query or ""
date_from_part = date_from or ""
date_to_part = date_to or ""

favorite_part = "fav" if favorite_only else "all"
cache_key = f"notes:list:{user_part}:{source_part}:{search_part[:20]}:{date_from_part}:{date_to_part}:{favorite_part}:{page}"
```

**问题**：
1. `notes_list()` 调用时 `user_id=None`（见 `web/routes/notes.py:54`）
2. 缓存key是 `notes:list:all:...`
3. 失效时用的pattern是 `notes:list:{user_id}:*`（user_id是具体数字）
4. **Pattern不匹配！缓存没被失效！**

## 修复方案

### 方案1：失效所有相关缓存（推荐）

修改 `web/routes/api.py` 的缓存失效逻辑：

```python
# 使缓存失效，确保刷新页面后能看到更新后的数据
try:
    from src.infrastructure.cache.managers import get_note_cache_manager
    cache_manager = get_note_cache_manager()
    user_id = updated_note.get('user_id')

    if user_id:
        # 失效特定用户的缓存
        invalidated = cache_manager.invalidate_note(note_id, user_id)
        logger.info(f"✅ 已失效笔记 {note_id} 的用户缓存 ({invalidated} 个条目)")

    # 【关键修复】失效全局列表缓存（user_id=None的情况）
    # 因为notes_list()使用user_id=None，生成的是notes:list:all:*的key
    deleted = cache_manager._cache.delete_pattern(f"{cache_manager._key_prefix}:list:all:*")
    deleted += cache_manager._cache.delete_pattern(f"{cache_manager._key_prefix}:count:all:*")
    logger.info(f"✅ 已失效全局笔记列表缓存 ({deleted} 个条目)")

except Exception as e:
    logger.error(f"❌ 缓存失效失败: {e}")
    import traceback
    traceback.print_exc()
```

### 方案2：同时失效用户和全局缓存

在 `src/infrastructure/cache/managers.py` 中添加新方法：

```python
def invalidate_note_all_views(self, note_id: int, user_id: Optional[int] = None) -> int:
    """Invalidate cache for a specific note across all views (user-specific and global)"""
    deleted = 0

    # Invalidate individual note cache
    deleted += self._cache.delete(self._make_key(f"note:{note_id}"))

    # Invalidate user-specific list caches
    if user_id:
        deleted += self._cache.delete_pattern(f"{self._key_prefix}:list:{user_id}:*")
        deleted += self._cache.delete_pattern(f"{self._key_prefix}:count:{user_id}:*")

    # Invalidate global list caches (for user_id=None queries)
    deleted += self._cache.delete_pattern(f"{self._key_prefix}:list:all:*")
    deleted += self._cache.delete_pattern(f"{self._key_prefix}:count:all:*")

    return deleted
```

然后在 `web/routes/api.py` 和 `bot/services/calibration_manager.py` 中使用：

```python
invalidated = cache_manager.invalidate_note_all_views(note_id, user_id)
```

## 需要修改的文件

1. **web/routes/api.py** (第164-174行)
   - 添加全局列表缓存失效

2. **bot/services/calibration_manager.py** (第425-434行)
   - 添加全局列表缓存失效

3. **src/infrastructure/cache/managers.py** (可选)
   - 添加 `invalidate_note_all_views()` 方法

## 测试步骤

1. 应用修复
2. 重启Flask服务
3. 对笔记979进行手动校准
4. 观察日志中的缓存失效信息
5. 刷新页面
6. 检查观看按钮是否能正常工作

## 额外优化建议

1. 将缓存失效的exception从warning改为error并打印堆栈
2. 在前端calibrate成功后自动刷新页面或更新note数据
3. 考虑使用更精确的缓存key或缓存标签系统
