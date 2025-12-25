# 📚 Save-Restricted-Bot API 文档

**版本**: 2.0.0
**更新日期**: 2025-12-13

---

## 📋 目录

1. [概述](#概述)
2. [认证](#认证)
3. [REST API](#rest-api)
4. [错误处理](#错误处理)
5. [示例代码](#示例代码)

---

## 🌐 概述

Save-Restricted-Bot 提供 RESTful API 用于管理笔记、校准任务和系统配置。

### 基础信息

- **Base URL**: `http://localhost:5000`
- **Content-Type**: `application/json`
- **认证方式**: Session Cookie

---

## 🔐 认证

### POST /login

用户登录

**请求体**:
```json
{
  "username": "admin",
  "password": "admin",
  "remember": true
}
```

**响应**: 重定向到 `/notes`

**示例**:
```bash
curl -X POST http://localhost:5000/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin&remember=on"
```

---

### GET /logout

用户登出

**响应**: 重定向到 `/login`

---

## 📝 笔记 API

### GET /notes

获取笔记列表

**查询参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `page` | integer | 否 | 页码（默认1） |
| `source` | string | 否 | 来源过滤 |
| `search` | string | 否 | 搜索关键词 |
| `date_from` | string | 否 | 开始日期 (YYYY-MM-DD) |
| `date_to` | string | 否 | 结束日期 (YYYY-MM-DD) |
| `favorite` | string | 否 | 仅收藏 (1) |

**响应**: HTML页面

**示例**:
```bash
# 获取第2页笔记
curl http://localhost:5000/notes?page=2

# 搜索包含"测试"的笔记
curl http://localhost:5000/notes?search=测试

# 获取收藏的笔记
curl http://localhost:5000/notes?favorite=1
```

---

### GET /api/edit_note/<note_id>

编辑笔记（API）

**路径参数**:
- `note_id`: 笔记ID

**请求体**:
```json
{
  "message_text": "更新后的笔记内容"
}
```

**响应**:
```json
{
  "success": true
}
```

**错误响应**:
```json
{
  "success": false,
  "error": "笔记内容不能为空"
}
```

**示例**:
```bash
curl -X POST http://localhost:5000/api/edit_note/123 \
  -H "Content-Type: application/json" \
  -d '{"message_text": "新的笔记内容"}'
```

---

### POST /delete_note/<note_id>

删除笔记

**路径参数**:
- `note_id`: 笔记ID

**响应**:
```json
{
  "success": true,
  "reload": false
}
```

**错误响应**:
```json
{
  "success": false,
  "error": "删除失败"
}
```

**示例**:
```bash
curl -X POST http://localhost:5000/delete_note/123
```

---

### POST /toggle_favorite/<note_id>

切换笔记收藏状态

**路径参数**:
- `note_id`: 笔记ID

**响应**:
```json
{
  "success": true
}
```

**示例**:
```bash
curl -X POST http://localhost:5000/toggle_favorite/123
```

---

## 🔧 校准 API

### POST /api/calibrate/<note_id>

校准磁力链接

**路径参数**:
- `note_id`: 笔记ID

**响应**:
```json
{
  "success": true,
  "total": 2,
  "success_count": 2,
  "fail_count": 0,
  "results": [
    {
      "info_hash": "ABC123",
      "old_magnet": "magnet:?xt=urn:btih:ABC123",
      "filename": "校准后的文件名.mp4",
      "success": true
    },
    {
      "info_hash": "DEF456",
      "old_magnet": "magnet:?xt=urn:btih:DEF456",
      "filename": "另一个文件.mkv",
      "success": true
    }
  ]
}
```

**错误响应**:
```json
{
  "success": false,
  "error": "笔记不存在"
}
```

**示例**:
```bash
curl -X POST http://localhost:5000/api/calibrate/123
```

---

### GET /admin/calibration/queue

查看校准任务队列

**查询参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `status` | string | 否 | 状态过滤 (pending/retrying/success/failed) |
| `page` | integer | 否 | 页码（默认1） |

**响应**: HTML页面

**示例**:
```bash
# 查看待处理的任务
curl http://localhost:5000/admin/calibration/queue?status=pending

# 查看失败的任务
curl http://localhost:5000/admin/calibration/queue?status=failed
```

---

### POST /api/calibration/task/<task_id>/retry

重试校准任务

**路径参数**:
- `task_id`: 任务ID

**响应**:
```json
{
  "success": true,
  "message": "任务已加入重试队列"
}
```

**示例**:
```bash
curl -X POST http://localhost:5000/api/calibration/task/456/retry
```

---

### POST /api/calibration/task/<task_id>/delete

删除校准任务

**路径参数**:
- `task_id`: 任务ID

**响应**:
```json
{
  "success": true,
  "message": "任务已删除"
}
```

**示例**:
```bash
curl -X POST http://localhost:5000/api/calibration/task/456/delete
```

---

## ⚙️ 管理 API

### GET /admin

管理面板

**功能**:
- 修改密码
- 查看系统信息

**响应**: HTML页面

---

### POST /admin

修改密码

**请求体**:
```json
{
  "current_password": "当前密码",
  "new_password": "新密码",
  "confirm_password": "确认新密码"
}
```

**响应**: HTML页面（带成功/错误消息）

**示例**:
```bash
curl -X POST http://localhost:5000/admin \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "current_password=admin&new_password=newpass123&confirm_password=newpass123"
```

---

### GET /admin/calibration

校准配置管理

**响应**: HTML页面

---

### POST /admin/calibration

更新校准配置

**请求体**:
```json
{
  "enabled": "on",
  "filter_mode": "empty_only",
  "first_delay": 600,
  "retry_delay_1": 3600,
  "retry_delay_2": 14400,
  "retry_delay_3": 28800,
  "max_retries": 3,
  "concurrent_limit": 5,
  "timeout_per_magnet": 30,
  "batch_timeout": 300
}
```

**响应**: HTML页面（带成功/错误消息）

---

### GET /admin/webdav

WebDAV配置管理

**响应**: HTML页面

---

### POST /admin/webdav

更新WebDAV配置

**请求体**:
```json
{
  "enabled": "on",
  "url": "https://webdav.example.com",
  "webdav_username": "user",
  "webdav_password": "pass",
  "base_path": "/telegram_media",
  "keep_local_copy": "on"
}
```

**响应**: HTML页面（带成功/错误消息）

---

### GET /admin/viewer

观看网站配置管理

**响应**: HTML页面

---

### POST /admin/viewer

更新观看网站配置

**请求体**:
```json
{
  "viewer_url": "https://example.com/watch?dn="
}
```

**响应**: HTML页面（带成功/错误消息）

---

## 🏥 健康检查 API

### GET /health

系统健康检查

**响应**:
```json
{
  "status": "healthy",
  "checks": {
    "database": "ok",
    "config": "ok",
    "watch_config": "ok",
    "storage": "ok"
  }
}
```

**错误响应** (503):
```json
{
  "status": "unhealthy",
  "checks": {
    "database": "error: connection failed",
    "config": "ok",
    "watch_config": "missing",
    "storage": "ok"
  }
}
```

**示例**:
```bash
curl http://localhost:5000/health
```

---

## 📁 媒体 API

### GET /media/<storage_location>

获取媒体文件

**路径参数**:
- `storage_location`: 存储位置（URL编码）

**响应**: 媒体文件（支持Range请求）

**Headers**:
- `Accept-Ranges`: bytes
- `Content-Length`: 文件大小
- `Content-Range`: 范围（如果是部分请求）
- `Cache-Control`: public, max-age=31536000, immutable

**示例**:
```bash
# 获取完整文件
curl http://localhost:5000/media/image.jpg

# Range请求（用于视频流）
curl -H "Range: bytes=0-1023" http://localhost:5000/media/video.mp4
```

---

## ❌ 错误处理

### 错误响应格式

所有API错误都返回以下格式：

```json
{
  "success": false,
  "error": "错误描述"
}
```

### HTTP状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 206 | 部分内容（Range请求） |
| 400 | 请求错误 |
| 401 | 未认证 |
| 404 | 资源不存在 |
| 500 | 服务器错误 |
| 502 | WebDAV代理错误 |
| 503 | 服务不可用 |

---

## 💻 示例代码

### Python示例

```python
import requests

# 登录
session = requests.Session()
session.post('http://localhost:5000/login', data={
    'username': 'admin',
    'password': 'admin'
})

# 获取笔记列表
response = session.get('http://localhost:5000/notes?page=1')
print(response.text)

# 校准磁力链接
response = session.post('http://localhost:5000/api/calibrate/123')
result = response.json()
print(f"校准结果: {result['success_count']}/{result['total']} 成功")

# 删除笔记
response = session.post('http://localhost:5000/delete_note/123')
result = response.json()
print(f"删除{'成功' if result['success'] else '失败'}")
```

### JavaScript示例

```javascript
// 登录
async function login() {
  const response = await fetch('http://localhost:5000/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: 'username=admin&password=admin',
    credentials: 'include'
  });
  return response.ok;
}

// 校准磁力链接
async function calibrate(noteId) {
  const response = await fetch(`http://localhost:5000/api/calibrate/${noteId}`, {
    method: 'POST',
    credentials: 'include'
  });
  const result = await response.json();
  console.log(`校准结果: ${result.success_count}/${result.total} 成功`);
  return result;
}

// 切换收藏
async function toggleFavorite(noteId) {
  const response = await fetch(`http://localhost:5000/toggle_favorite/${noteId}`, {
    method: 'POST',
    credentials: 'include'
  });
  const result = await response.json();
  return result.success;
}
```

### cURL示例

```bash
# 登录并保存Cookie
curl -c cookies.txt -X POST http://localhost:5000/login \
  -d "username=admin&password=admin"

# 使用Cookie访问API
curl -b cookies.txt http://localhost:5000/notes

# 校准磁力链接
curl -b cookies.txt -X POST http://localhost:5000/api/calibrate/123

# 删除笔记
curl -b cookies.txt -X POST http://localhost:5000/delete_note/123

# 健康检查（无需认证）
curl http://localhost:5000/health
```

---

## 🔒 安全建议

1. **修改默认密码**: 首次登录后立即修改默认密码（admin/admin）
2. **HTTPS**: 生产环境使用HTTPS
3. **防火墙**: 限制API访问IP
4. **速率限制**: 考虑添加API速率限制
5. **日志监控**: 监控异常API调用

---

## 📊 速率限制

当前版本暂无速率限制，建议在生产环境中添加：

- 登录: 5次/分钟
- API调用: 100次/分钟
- 校准: 10次/分钟

---

## 🆕 版本历史

### v2.0.0 (2025-12-13)
- ✅ 添加完整的REST API
- ✅ 支持Range请求
- ✅ 添加健康检查端点
- ✅ 优化数据库查询
- ✅ 添加API文档

---

**文档维护**: Claude Code AI Assistant
**最后更新**: 2025-12-13
