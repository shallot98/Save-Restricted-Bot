# 笔记系统磁力链接功能重构总结

## 重构日期
2025-12-09

## 重构目标
根据用户需求，重构笔记系统中磁力链接的处理逻辑，包括：
1. 记录笔记时提取磁力链接的dn参数（文件名A）
2. 校准功能中机器人回复的解析逻辑
3. 校准完成后补全笔记中的磁力链接

## 核心需求
- **文件名A定义**：磁力链接中dn参数的值（dn=后面的文本到行结束）
- **点击校准**：使用机器人回复获取文件名，提取冒号(:)到第一个逗号(,)之间的内容替换文件名A
- **qBittorrent校准**：直接使用种子获取的文件名替换文件名A
- **校准完成**：补全笔记文本中的磁力链接，将校准后的文件名更新到dn参数

## 修改的文件

### 1. database.py
**文件路径**: `/root/Save-Restricted-Bot/database.py`

#### 修改1: `_extract_magnet_link` 函数 (第279-330行)
**功能**: 从消息文本中提取磁力链接并规范化dn参数

**修改内容**:
- 优化了dn参数的提取逻辑
- 如果磁力链接中已有dn参数，提取dn=后面的文本到行结束
- 如果dn参数后面还有其他参数（如&tr=），只提取dn的值
- 自动处理URL编码和解码
- 如果没有dn参数，从文本开头到第一个#号之前提取作为dn

**关键代码**:
```python
# 已有dn参数，提取dn=后面的文本到行结束
dn_pos = magnet_link.find('dn=')
if dn_pos >= 0:
    # 提取dn=后面到行结束的内容
    dn_text = magnet_link[dn_pos + 3:].rstrip()
    # 如果dn后面还有&参数，只取到&之前
    amp_pos = dn_text.find('&')
    if amp_pos > 0:
        dn_text = dn_text[:amp_pos]

    # 解码dn参数（如果已编码）
    dn_decoded = unquote(dn_text)
    # 重新构建磁力链接（URL编码dn参数）
    return f'magnet:?xt=urn:btih:{info_hash}&dn={quote(dn_decoded)}'
```

#### 修改2: `update_note_with_calibrated_dns` 函数 (第590行)
**功能**: 校准后更新笔记文本中的磁力链接

**修改内容**:
- 添加注释说明message_text中不需要URL编码，保持可读性
- 确保校准后的文件名正确补全到笔记文本中

**关键代码**:
```python
# 构建新的磁力链接（message_text中不需要URL编码，保持可读性）
new_magnet = f"magnet:?xt=urn:btih:{info_hash}&dn={filename}"
```

### 2. calibrate_bot_helper.py
**文件路径**: `/root/Save-Restricted-Bot/calibrate_bot_helper.py`

#### 修改: 机器人回复解析逻辑 (第81-106行)
**功能**: 从Telegram机器人回复中提取文件名

**修改内容**:
- 重构了文件名提取逻辑，改为提取冒号(:)到第一个逗号(,)之间的内容
- 扩展了条件判断，不仅匹配"离线任务已添加"，还匹配任何包含冒号的回复
- 添加了更清晰的注释说明提取规则

**修改前**:
```python
# 从后往前找最后一个逗号（hash值前的逗号）
last_comma = content.rfind(',')
if last_comma > 0:
    filename = content[:last_comma].strip()
    return filename
```

**修改后**:
```python
# 提取规则：获取冒号(:)到第一个逗号(,)之间的内容
if '离线任务已添加' in text or ':' in text:
    first_line = text.split('\n')[0].strip()

    # 查找冒号位置
    colon_pos = first_line.find(':')
    if colon_pos >= 0:
        # 提取冒号后的内容
        after_colon = first_line[colon_pos + 1:].strip()

        # 查找第一个逗号位置
        comma_pos = after_colon.find(',')
        if comma_pos > 0:
            # 提取冒号到第一个逗号之间的内容
            filename = after_colon[:comma_pos].strip()
            return filename
        else:
            # 如果没有逗号，返回冒号后的全部内容
            return after_colon.strip()

    # 如果没有冒号，返回整行内容
    return first_line.strip()
```

### 3. test_refactored_features.py (新增)
**文件路径**: `/root/Save-Restricted-Bot/test_refactored_features.py`

**功能**: 测试重构后的功能

**测试覆盖**:
1. 磁力链接dn参数提取（4个测试用例）
   - 已有dn参数（未编码）
   - 已有dn参数（URL编码）
   - 没有dn参数，从文本开头提取
   - dn参数后面还有其他参数

2. 机器人回复解析（4个测试用例）
   - 标准格式（冒号+逗号）
   - 没有逗号
   - 多个逗号
   - 没有冒号

3. 校准后磁力链接补全（1个测试用例）
   - 验证校准后的文件名正确补全到笔记文本中

**测试结果**: ✅ 所有测试通过

## 功能流程

### 1. 笔记记录流程
```
用户发送消息 → 提取磁力链接 → 解析dn参数（文件名A）
    ↓
如果有dn参数：提取dn=后面的文本到行结束
如果没有dn参数：从文本开头到第一个#号之前提取
    ↓
URL编码dn参数 → 保存到数据库（magnet_link字段）
```

### 2. 校准流程

#### 自动校准（qBittorrent）
```
定时任务 → 获取待校准笔记 → qBittorrent API添加种子
    ↓
等待元数据下载 → 获取真实文件名 → 替换文件名A
    ↓
更新数据库（filename字段 + message_text中的磁力链接）
```

#### 手动校准（Telegram机器人）
```
用户点击"校准"按钮 → 发送磁力链接给机器人
    ↓
机器人回复 → 解析回复（提取冒号到第一个逗号的内容）
    ↓
替换文件名A → 更新数据库
```

### 3. 磁力链接补全流程
```
校准成功 → 获取校准后的文件名
    ↓
遍历笔记文本中的所有磁力链接
    ↓
匹配info_hash → 替换dn参数 → 更新message_text
    ↓
同时更新magnet_link字段和filename字段
```

## 数据库字段说明

### notes表相关字段
- **message_text**: 笔记原始文本，包含所有磁力链接（dn参数未编码，保持可读性）
- **magnet_link**: 主磁力链接（dn参数URL编码，用于数据库存储）
- **filename**: 校准后的完整文件名（未编码，用于显示和搜索）

### 优先级
```
filename字段 > magnet_link的dn参数 > message_text提取
```

## 兼容性说明

### 向后兼容
- 保留了旧的`update_note_with_calibrated_dn`函数（第625行）
- 新代码使用`update_note_with_calibrated_dns`函数（支持多磁力链接）
- 现有数据库记录不受影响

### URL编码处理
- **数据库存储**: magnet_link字段使用URL编码（符合标准）
- **文本显示**: message_text中不编码（保持可读性）
- **Web界面**: 自动处理编码和解码

## 测试验证

### 运行测试
```bash
python3 test_refactored_features.py
```

### 测试结果
```
测试1: 磁力链接dn参数提取 - ✅ 4/4 通过
测试2: 机器人回复解析 - ✅ 4/4 通过
测试3: 校准后磁力链接补全 - ✅ 1/1 通过
```

## 注意事项

1. **dn参数提取规则**
   - 如果磁力链接中已有dn参数，优先使用该参数
   - dn参数可以包含空格和特殊字符
   - 自动处理URL编码和解码

2. **机器人回复格式**
   - 标准格式：`离线任务已添加: 文件名, hash值, 到 /Downloads`
   - 提取规则：冒号(:)到第一个逗号(,)之间的内容
   - 兼容没有冒号或逗号的情况

3. **校准后更新**
   - 同时更新message_text、magnet_link和filename三个字段
   - message_text中的磁力链接保持未编码状态（可读性）
   - magnet_link字段使用URL编码（标准格式）

4. **多磁力链接支持**
   - 一条笔记可以包含多个磁力链接
   - 批量校准所有磁力链接
   - 独立处理每个链接的成功/失败状态

## 相关文件

- `database.py` - 数据库操作和磁力链接提取
- `calibrate_bot_helper.py` - Telegram机器人校准
- `calibrate_qbt_helper.py` - qBittorrent API校准
- `bot/services/calibration_manager.py` - 校准管理器
- `app.py` - Web API接口
- `templates/notes.html` - Web前端界面

## 后续优化建议

1. **性能优化**
   - 考虑缓存已校准的文件名，避免重复校准
   - 优化正则表达式匹配性能

2. **用户体验**
   - 添加校准进度显示
   - 支持批量手动校准
   - 添加校准历史记录

3. **错误处理**
   - 增强异常处理和日志记录
   - 添加校准失败的详细错误信息
   - 支持手动重试失败的校准任务

## 总结

本次重构成功实现了用户需求的所有功能点：
- ✅ 正确提取磁力链接的dn参数作为文件名A
- ✅ 机器人回复解析改为提取冒号到第一个逗号的内容
- ✅ qBittorrent校准直接使用种子文件名
- ✅ 校准完成后正确补全笔记中的磁力链接
- ✅ 所有功能通过测试验证

重构遵循了KISS、DRY、YAGNI原则，代码简洁清晰，易于维护和扩展。
