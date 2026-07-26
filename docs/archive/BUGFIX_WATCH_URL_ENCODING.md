# 修复：观看链接空格截断问题

## 问题描述

用户报告：760笔记校准完成后，点击观看按钮生成的网址在空格处被截断。

**示例：**
- 完整文件名：`0223-推特顶级泡良大神『fKabuto』门槛 作品 超多位高颜值反差美女做爱视频 叫床淫荡不堪(157V)`
- 期望URL：`https://open.shallot.netlib.re/d2/Downloads/0223-推特顶级泡良大神『fKabuto』门槛%20作品%20超多位高颜值反差美女做爱视频%20叫床淫荡不堪(157V)`
- 实际URL：`https://open.shallot.netlib.re/d2/Downloads/0223-推特顶级泡良大神『fKabuto』门槛` （在第一个空格处截断）

## 根本原因

在生成观看链接时，文件名包含空格等特殊字符，但没有进行URL编码，导致浏览器在解析URL时在空格处截断。

**问题代码位置：**

1. **后端 (app.py:263)**
   ```python
   # 错误：直接拼接，未进行URL编码
   note['watch_url'] = viewer_url + all_dns[0]['dn'] if all_dns[0]['dn'] else None
   ```

2. **前端 (templates/notes.html:541)**
   ```javascript
   // 错误：直接拼接，未进行URL编码
   option.href = viewerUrl + dns.dn;
   ```

3. **前端 (templates/notes_old.html:1347)**
   ```javascript
   // 错误：直接拼接，未进行URL编码
   const watchUrl = viewerUrl + dnInfo.dn;
   ```

## 修复方案

### 1. 后端修复 (app.py)

在生成观看链接时使用 `urllib.parse.quote()` 对文件名进行URL编码：

```python
# 修复后：使用quote进行URL编码
from urllib.parse import quote
note['watch_url'] = viewer_url + quote(all_dns[0]['dn']) if all_dns[0]['dn'] else None
```

**修改位置：** `app.py:263-265`

### 2. 前端修复 (templates/notes.html)

在JavaScript中使用 `encodeURIComponent()` 对文件名进行URL编码：

```javascript
// 修复后：使用encodeURIComponent进行URL编码
option.href = viewerUrl + encodeURIComponent(dns.dn);
```

**修改位置：** `templates/notes.html:542`

### 3. 前端修复 (templates/notes_old.html)

同样使用 `encodeURIComponent()` 进行URL编码：

```javascript
// 修复后：使用encodeURIComponent进行URL编码
const watchUrl = viewerUrl + encodeURIComponent(dnInfo.dn);
```

**修改位置：** `templates/notes_old.html:1347`

## URL编码说明

### Python: `urllib.parse.quote()`
- 将特殊字符转换为 `%XX` 格式
- 空格转换为 `%20`
- 中文字符转换为UTF-8编码的 `%XX%XX%XX` 格式

### JavaScript: `encodeURIComponent()`
- 将特殊字符转换为 `%XX` 格式
- 空格转换为 `%20`
- 中文字符转换为UTF-8编码的 `%XX%XX%XX` 格式

## 测试验证

### 测试用例

**文件名：** `0223-推特顶级泡良大神『fKabuto』门槛 作品 超多位高颜值反差美女做爱视频 叫床淫荡不堪(157V)`

**修复前：**
```
https://open.shallot.netlib.re/d2/Downloads/0223-推特顶级泡良大神『fKabuto』门槛
```
（在第一个空格处截断）

**修复后：**
```
https://open.shallot.netlib.re/d2/Downloads/0223-%E6%8E%A8%E7%89%B9%E9%A1%B6%E7%BA%A7%E6%B3%A1%E8%89%AF%E5%A4%A7%E7%A5%9E%E3%80%8EfKabuto%E3%80%8F%E9%97%A8%E6%A7%9B%20%E4%BD%9C%E5%93%81%20%E8%B6%85%E5%A4%9A%E4%BD%8D%E9%AB%98%E9%A2%9C%E5%80%BC%E5%8F%8D%E5%B7%AE%E7%BE%8E%E5%A5%B3%E5%81%9A%E7%88%B1%E8%A7%86%E9%A2%91%20%E5%8F%AB%E5%BA%8A%E6%B7%AB%E8%8D%A1%E4%B8%8D%E5%A0%AA(157V)
```
（完整的URL编码链接）

### 验证步骤

1. 重启Flask应用
2. 访问笔记列表页面
3. 找到包含空格的文件名笔记（如760号笔记）
4. 点击"观看"按钮
5. 验证生成的URL是否完整（包含所有空格后的内容）
6. 点击链接，验证是否能正确跳转到观看网站

## 影响范围

- **后端：** `app.py` 中的观看链接生成逻辑
- **前端：** `templates/notes.html` 和 `templates/notes_old.html` 中的观看链接生成逻辑
- **用户体验：** 修复后，所有包含空格或特殊字符的文件名都能正确生成观看链接

## 相关问题

此修复同时解决了以下潜在问题：
- 文件名包含中文字符的URL编码问题
- 文件名包含特殊字符（如 `&`, `?`, `#` 等）的URL编码问题
- 文件名包含其他空白字符（如制表符、换行符）的问题

## 修复日期

2025-12-09

## 额外修复：优先使用校准后的文件名

### 问题
校准后，`filename` 字段存储了完整的校准文件名，但观看链接没有优先使用这个字段，而是从磁力链接的 `dn` 参数提取。

### 修复方案
修改 `extract_all_dns_from_note()` 函数，让第一个磁力链接优先使用校准后的 `filename` 字段：

```python
# 修复前：不使用filename字段
dn = extract_dn_from_magnet(magnet, message_text, None)

# 修复后：第一个磁力链接优先使用filename字段
for idx, magnet in enumerate(all_magnets):
    if idx == 0 and filename:
        # 第一个磁力链接使用校准后的filename
        dn = filename
    else:
        # 其他磁力链接从磁力链接自身提取dn
        dn = extract_dn_from_magnet(magnet, message_text, None)
```

**修改位置：** `app.py:209-217`

### 优先级说明
修复后，文件名提取的优先级为：
1. **校准后的 `filename` 字段**（最高优先级，仅用于第一个磁力链接）
2. 磁力链接的 `dn` 参数
3. `message_text` 提取

## 修复状态

✅ 已完成
- [x] 后端URL编码修复 (app.py:263-265)
- [x] 前端URL编码修复 (templates/notes.html:542)
- [x] 前端URL编码修复 (templates/notes_old.html:1347)
- [x] 优先使用校准文件名修复 (app.py:209-217)
- [ ] 测试验证（待用户测试）
