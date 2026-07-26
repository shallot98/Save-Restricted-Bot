# 校准系统改进总结

## 问题描述

用户反馈：909笔记有两个磁力链接，但只有一个进入了自动校准列表。

## 原因分析

### 1. 设计缺陷

原有设计存在严重问题：
- **以笔记为单位创建任务**：一个笔记只创建一个校准任务
- **批量处理容易出错**：如果第一个磁力链接成功、第二个失败，整个任务被标记为成功
- **失败的磁力链接无法重试**：没有独立的任务记录，无法针对单个磁力链接重试

### 2. 技术问题

发现两个技术问题：

#### 问题1：数据库去重逻辑错误
```python
# 旧代码（错误）
cursor.execute('''
    SELECT id FROM calibration_tasks
    WHERE note_id = ? AND status IN ('pending', 'retrying')
''', (note_id,))
```
只检查`note_id`，导致同一笔记的第二个磁力链接无法添加任务。

#### 问题2：正则表达式bug
```python
# 旧正则（错误）
MAGNET_PATTERN = r'magnet:\?xt=urn:btih:[a-zA-Z0-9]+(?:[&?](?!magnet:)[^\s\n]*)*'
```
当两个磁力链接紧挨着时（中间没有空格或换行），第一个会把第二个也匹配进去。

## 解决方案

### 1. 改为以磁力链接为单位

#### 修改任务创建逻辑 (`bot/services/calibration_manager.py:168-226`)
```python
def add_note_to_calibration_queue(self, note_id: int) -> bool:
    """将笔记添加到校准队列（为每个磁力链接创建独立任务）"""

    # 提取所有磁力链接
    all_dns = self.extract_all_dns_from_note(note)

    # 为每个磁力链接创建独立的校准任务
    for idx, dn_info in enumerate(all_dns, 1):
        magnet_hash = dn_info['info_hash']
        task_id = add_calibration_task(note_id, magnet_hash, first_delay)

        if task_id:
            logger.info(f"✅ 第 {idx}/{len(all_dns)} 个磁力链接任务已添加")
```

#### 修改任务处理逻辑 (`bot/services/calibration_manager.py:282-398`)
```python
def process_calibration_task(self, task: Dict) -> bool:
    """处理单个校准任务（只处理任务指定的磁力链接）"""

    magnet_hash = task['magnet_hash']

    # 找到当前任务对应的磁力链接
    target_magnet = None
    for dn_info in all_dns:
        if dn_info['info_hash'] == magnet_hash:
            target_magnet = dn_info
            break

    # 只校准这一个磁力链接
    filename = self.calibrate_magnet(magnet_hash, timeout)

    # 更新数据库（只更新这一个磁力链接）
    calibrated_results = [{
        'info_hash': magnet_hash,
        'old_magnet': target_magnet['magnet'],
        'filename': filename,
        'success': True
    }]
```

### 2. 修复数据库去重逻辑 (`database.py:401-424`)
```python
def add_calibration_task(note_id: int, magnet_hash: str, delay_seconds: int = 600) -> Optional[int]:
    """Add calibration task (one task per magnet link)"""

    # 检查是否已存在该磁力链接的任务（以磁力链接为单位去重）
    cursor.execute('''
        SELECT id FROM calibration_tasks
        WHERE note_id = ? AND magnet_hash = ? AND status IN ('pending', 'retrying')
    ''', (note_id, magnet_hash))
```

### 3. 修复正则表达式 (`bot/utils/magnet_utils.py:17`)
```python
# 新正则（正确）
MAGNET_PATTERN = r'magnet:\?xt=urn:btih:[a-zA-Z0-9]+(?:[&?][^&\s\n]*?(?=(?:magnet:|$|[\s\n])))*'
```

使用前瞻断言`(?=(?:magnet:|$|[\s\n]))`确保在遇到下一个`magnet:`、字符串结束或空白字符时停止匹配。

## 测试结果

### 测试笔记909
```
笔记内容：
猥琐眼镜kk哥全集127G超清无水印
magnet:?xt=urn:btih:094DD6D482B31DCF7DDBE7D3F45111349D8A58C6&dn=[ThZu.Cc]猥琐眼镜kk哥全集127G超清无水印
magnet:?xt=urn:btih:292DA7E94DC52C42D8603284379E89A727C1E46D&dn=YE0505_16_眼镜KK哥绳艺教学【71V】66G
```

### 测试结果
```
创建的任务数量: 2
  task_id=165, hash=094DD6D482B31DCF..., status=pending
  task_id=166, hash=292DA7E94DC52C42..., status=pending
```

✅ **成功为两个磁力链接都创建了独立的校准任务！**

## 改进优势

### 1. 可靠性提升
- ✅ 每个磁力链接独立校准，互不影响
- ✅ 单个磁力链接失败不影响其他磁力链接
- ✅ 失败的磁力链接可以独立重试

### 2. 可追踪性提升
- ✅ 每个磁力链接有独立的任务记录
- ✅ 可以查看每个磁力链接的校准状态
- ✅ 可以针对单个磁力链接进行操作（重试、删除）

### 3. 用户体验提升
- ✅ 校准队列显示更清晰（显示所有磁力链接）
- ✅ 校准进度更透明（可以看到每个磁力链接的状态）
- ✅ 问题定位更容易（知道具体哪个磁力链接失败）

## 影响范围

### 修改的文件
1. `bot/services/calibration_manager.py` - 校准任务创建和处理逻辑
2. `database.py` - 数据库去重逻辑
3. `bot/utils/magnet_utils.py` - 磁力链接正则表达式

### 向后兼容性
- ✅ 数据库结构无变化
- ✅ API接口无变化
- ✅ 现有任务可以正常处理
- ✅ Web界面无需修改

## 部署说明

1. 重新构建Docker镜像：
```bash
docker compose build --no-cache
```

2. 重启容器：
```bash
docker compose restart
```

3. 验证改进：
- 访问 `/admin/calibration/queue` 查看校准队列
- 添加包含多个磁力链接的笔记
- 确认每个磁力链接都有独立的任务记录

## 日期
2025-12-17
