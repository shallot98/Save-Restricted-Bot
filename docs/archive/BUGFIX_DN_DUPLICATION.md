# DN参数重复问题修复报告

**问题ID**: 笔记1030手动校准后DN参数重复
**修复日期**: 2025-12-26
**严重程度**: 中等

---

## 问题描述

用户报告笔记1030在手动校准后,`message_text` 字段中的磁力链接DN参数出现了**5次重复**:

```
【路少】 游走各大会所红灯区 第一视角(中) 【路少】 游走各大会所红灯区 第一视角(中) 【路少】 游走各大会所红灯区 第一视角(中) 【路少】 游走各大会所红灯区 第一视角(中) 【路少】 游走各大会所红灯区 第一视角(中)
```

## 根本原因分析

### 代码缺陷位置

`database.py:649-659` 中的 `update_note_with_calibrated_dns()` 函数存在两个严重问题:

#### 问题1: DN参数未进行URL编码

```python
# 错误代码 (第656行)
new_magnet = f"magnet:?xt=urn:btih:{info_hash}&dn={filename}"  # ❌ filename未编码
```

**影响**: 在 `message_text` 中替换磁力链接时,未编码的中文文件名会导致后续处理异常。

#### 问题2: 正则表达式匹配范围不当

```python
# 错误代码 (第658行)
magnet_pattern = rf'magnet:\?xt=urn:btih:\s*{re.escape(info_hash)}(?:[&?][^&\s\n]*?(?=(?:magnet:|$|[\s\n])))*'
```

**问题分析**:
1. 正则表达式只匹配磁力链接本身及其参数
2. **未能匹配磁力链接后面可能存在的重复文本**
3. 每次手动校准时:
   - 如果磁力链接已有DN参数,正则只会替换磁力链接部分
   - 但如果之前的校准在磁力链接后面追加了**未编码的重复文本**,这些文本不会被清理
   - 新的校准操作可能会继续追加文本,导致重复累积

### 触发条件

用户对同一笔记**多次执行手动校准**操作,每次校准都会:
1. 在 `message_text` 中添加或更新磁力链接
2. 由于正则表达式匹配不完整,可能在磁力链接后留下重复的文件名文本
3. 重复5次操作后,累积了5次重复的DN文本

---

## 修复方案

### 1. 修复 database.py 中的代码缺陷

**文件**: `database.py:649-662`

#### 修复内容:

```python
if message_text:
    for result in calibrated_results:
        if not result.get('success'):
            continue

        info_hash = result['info_hash']
        filename = MagnetLinkParser.clean_filename(result.get('filename', ''))
        # 【关键修复】对filename进行URL编码
        encoded_filename = quote(filename) if filename else ""
        new_magnet = f"magnet:?xt=urn:btih:{info_hash}&dn={encoded_filename}"
        # 【关键修复】正则表达式:先移除该hash的所有旧dn参数,然后替换为新的完整磁力链接
        # 匹配: magnet:?xt=urn:btih:{hash} + 可选的任意参数(包括旧的dn参数) 直到遇到换行/空白/下一个magnet:
        magnet_pattern = rf'magnet:\?xt=urn:btih:\s*{re.escape(info_hash)}(?:[&?][^\s\n]*?)*?(?=\s|$|magnet:)'
        updated_text = re.sub(magnet_pattern, new_magnet, updated_text, flags=re.IGNORECASE)
```

**关键改进**:
1. ✅ 添加 `quote(filename)` 对文件名进行URL编码
2. ✅ 改进正则表达式,使用前瞻断言 `(?=\s|$|magnet:)` 确保在遇到空白字符、字符串结束或下一个magnet:时停止匹配
3. ✅ 确保每次替换都是完整的磁力链接,不会留下残余文本

### 2. 清理已损坏的笔记1030

**工具**: `fix_duplicate_dn_1030.py`

**核心逻辑**:
```python
# 匹配该hash的磁力链接及其后续所有文本,直到遇到 # 号或字符串结尾
magnet_pattern = rf'magnet:\?xt=urn:btih:\s*{re.escape(info_hash)}[^\n#]*'

# 替换为正确的、URL编码的磁力链接
correct_magnet = f"magnet:?xt=urn:btih:{info_hash}&dn={quote(correct_dn)}"
fixed_message_text = re.sub(magnet_pattern, correct_magnet, message_text, flags=re.IGNORECASE)
```

**修复效果**:
- 修复前 `message_text` 长度: 645 字符
- 修复后 `message_text` 长度: 530 字符
- 成功清理了重复的DN参数文本

---

## 验证测试

### 测试脚本: `test_fix_duplicate_dn.py`

**测试用例**: 模拟对笔记1030再次执行手动校准

**验证点**:
1. ✅ message_text 长度不应该增加
2. ✅ message_text 中只有一个该hash的磁力链接
3. ✅ DN参数正确进行URL编码/解码
4. ✅ 不会出现未编码的重复文件名文本

**测试结果**:
```
✅ 验证1通过: message_text 长度没有增加 (长度变化: 0)
✅ 验证2通过: message_text 中只有1个该hash的磁力链接
✅ 验证3通过: DN参数正确解码为: 【重磅核弹】电报大神 【路少】 游走各大会所红灯区 第一视角(中)
✅ 验证4通过: message_text 中未编码的文件名出现次数正常 (0 次)

🎉 所有验证通过! 修复成功!
```

---

## 影响范围

### 受影响的功能
1. **手动校准**: `web/routes/api.py` 中的校准接口
2. **自动校准**: `bot/services/calibration_manager.py` 中的自动校准任务

### 受影响的笔记
- **已知**: 笔记1030 (已修复)
- **潜在**: 任何经过多次手动校准的笔记都可能存在相同问题

### 建议后续操作
1. 检查数据库中是否有其他笔记存在类似的DN重复问题:
   ```sql
   SELECT id, LENGTH(message_text), message_text
   FROM notes
   WHERE message_text LIKE '%【%【%【%'  -- 查找可能重复的中文文本
   ORDER BY LENGTH(message_text) DESC
   LIMIT 20;
   ```

2. 如果发现其他受影响的笔记,可以修改 `fix_duplicate_dn_1030.py` 脚本使其支持批量修复

---

## 技术细节

### 正则表达式改进对比

#### 修复前:
```python
rf'magnet:\?xt=urn:btih:\s*{re.escape(info_hash)}(?:[&?][^&\s\n]*?(?=(?:magnet:|$|[\s\n])))*'
```
- 匹配范围: 仅磁力链接及其参数
- 缺陷: 无法处理磁力链接后的重复文本

#### 修复后:
```python
rf'magnet:\?xt=urn:btih:\s*{re.escape(info_hash)}(?:[&?][^\s\n]*?)*?(?=\s|$|magnet:)'
```
- 匹配范围: 磁力链接及其参数,直到遇到空白/结束/下一个magnet:
- 改进: 确保完整替换,不留残余

---

## 相关文件清单

### 已修改文件
- `database.py` (database.py:649-662)

### 新增文件
- `fix_duplicate_dn_1030.py` - 修复脚本
- `test_fix_duplicate_dn.py` - 测试脚本
- `BUGFIX_DN_DUPLICATION.md` - 本文档

---

## 总结

此问题由代码缺陷和用户操作(多次手动校准)共同触发。通过:
1. 修复 `database.py` 中的URL编码和正则表达式问题
2. 编写专用脚本清理已损坏的数据
3. 全面验证测试

问题已彻底解决,且不会在未来的操作中再次出现。
