# Save-Restricted-Bot UI重构方案 - 第三部分

> 接续 UI_REFACTOR_SPECIFICATION_PART2.md

---

## 第三部分：技术实施方案

### 3.1 后端API层设计

#### 3.1.1 RESTful API端点列表

```python
# API端点完整清单

# ==================== 认证相关 ====================
POST   /api/v1/auth/login           # 用户登录
POST   /api/v1/auth/logout          # 用户登出
POST   /api/v1/auth/refresh         # 刷新Token
GET    /api/v1/auth/me              # 获取当前用户信息

# ==================== 笔记管理 ====================
GET    /api/v1/notes                # 获取笔记列表（支持分页、筛选、搜索）
POST   /api/v1/notes                # 创建新笔记
GET    /api/v1/notes/:id            # 获取单条笔记详情
PUT    /api/v1/notes/:id            # 更新笔记
DELETE /api/v1/notes/:id            # 删除笔记
POST   /api/v1/notes/:id/favorite   # 切换收藏状态
POST   /api/v1/notes/batch          # 批量操作
    # 请求体: { "action": "delete|archive|tag", "note_ids": [1,2,3], "data": {...} }

# ==================== 标签管理 ====================
GET    /api/v1/tags                 # 获取所有标签
POST   /api/v1/tags                 # 创建标签
GET    /api/v1/tags/:id             # 获取标签详情
PUT    /api/v1/tags/:id             # 更新标签
DELETE /api/v1/tags/:id             # 删除标签
POST   /api/v1/notes/:id/tags       # 为笔记添加标签
DELETE /api/v1/notes/:id/tags/:tagId # 移除笔记标签

# ==================== 搜索功能 ====================
GET    /api/v1/search               # 全文搜索
GET    /api/v1/search/suggestions   # 搜索建议
GET    /api/v1/search/history       # 搜索历史
POST   /api/v1/search/history       # 保存搜索历史
DELETE /api/v1/search/history       # 清除搜索历史

# ==================== 媒体文件 ====================
GET    /api/v1/media/:path          # 获取媒体文件
POST   /api/v1/media/upload         # 上传媒体文件
DELETE /api/v1/media/:id            # 删除媒体文件

# ==================== 统计数据 ====================
GET    /api/v1/stats/overview       # 总览统计
GET    /api/v1/stats/daily          # 每日统计
GET    /api/v1/stats/sources        # 来源统计
GET    /api/v1/stats/tags           # 标签统计

# ==================== 用户设置 ====================
GET    /api/v1/user/preferences     # 获取用户偏好
PUT    /api/v1/user/preferences     # 更新用户偏好
PUT    /api/v1/user/password        # 修改密码

# ==================== 导出功能 ====================
GET    /api/v1/export/notes         # 导出笔记（支持JSON/Markdown/CSV）
    # 查询参数: ?format=json&note_ids=1,2,3
```

#### 3.1.2 请求/响应格式规范

**统一响应格式**

```typescript
// types/api.ts

// 成功响应
interface SuccessResponse<T = any> {
  success: true
  data: T
  message?: string
  timestamp: string
}

// 错误响应
interface ErrorResponse {
  success: false
  error: {
    code: string
    message: string
    details?: any
  }
  timestamp: string
}

// 分页响应
interface PaginatedResponse<T> {
  success: true
  data: {
    items: T[]
    pagination: {
      page: number
      pageSize: number
      total: number
      totalPages: number
      hasNext: boolean
      hasPrev: boolean
    }
  }
  timestamp: string
}
```

**Python后端实现**

```python
# api/responses.py
from flask import jsonify
from datetime import datetime
from typing import Any, Optional, Dict, List

def success_response(data: Any = None, message: Optional[str] = None):
    """成功响应"""
    return jsonify({
        'success': True,
        'data': data,
        'message': message,
        'timestamp': datetime.utcnow().isoformat()
    })

def error_response(code: str, message: str, details: Optional[Dict] = None, status_code: int = 400):
    """错误响应"""
    return jsonify({
        'success': False,
        'error': {
            'code': code,
            'message': message,
            'details': details
        },
        'timestamp': datetime.utcnow().isoformat()
    }), status_code

def paginated_response(items: List, page: int, page_size: int, total: int):
    """分页响应"""
    total_pages = (total + page_size - 1) // page_size
    
    return jsonify({
        'success': True,
        'data': {
            'items': items,
            'pagination': {
                'page': page,
                'pageSize': page_size,
                'total': total,
                'totalPages': total_pages,
                'hasNext': page < total_pages,
                'hasPrev': page > 1
            }
        },
        'timestamp': datetime.utcnow().isoformat()
    })
```

#### 3.1.3 笔记API实现示例

```python
# api/routes/notes.py
from flask import Blueprint, request, g
from database import get_notes, get_note_count, get_note_by_id, add_note, update_note, delete_note
from api.responses import success_response, error_response, paginated_response
from api.auth import require_auth
from typing import Dict, Any

notes_bp = Blueprint('notes', __name__, url_prefix='/api/v1/notes')

@notes_bp.route('', methods=['GET'])
@require_auth
def list_notes():
    """获取笔记列表"""
    try:
        # 解析查询参数
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('pageSize', 50, type=int)
        search = request.args.get('search', '')
        source = request.args.get('source', '')
        tags = request.args.get('tags', '').split(',') if request.args.get('tags') else []
        favorite_only = request.args.get('favorite', 'false').lower() == 'true'
        date_from = request.args.get('dateFrom', '')
        date_to = request.args.get('dateTo', '')
        sort_by = request.args.get('sortBy', 'timestamp')
        sort_order = request.args.get('sortOrder', 'desc')
        
        # 参数验证
        if page < 1:
            return error_response('INVALID_PARAMETER', 'Page must be >= 1')
        if page_size < 1 or page_size > 100:
            return error_response('INVALID_PARAMETER', 'Page size must be between 1 and 100')
        
        # 计算偏移量
        offset = (page - 1) * page_size
        
        # 获取笔记
        notes = get_notes(
            user_id=g.user_id,
            source_chat_id=source if source else None,
            search_query=search if search else None,
            tags=tags if tags else None,
            date_from=date_from if date_from else None,
            date_to=date_to if date_to else None,
            favorite_only=favorite_only,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=page_size,
            offset=offset
        )
        
        # 获取总数
        total = get_note_count(
            user_id=g.user_id,
            source_chat_id=source if source else None,
            search_query=search if search else None,
            tags=tags if tags else None,
            date_from=date_from if date_from else None,
            date_to=date_to if date_to else None,
            favorite_only=favorite_only
        )
        
        # 格式化响应
        items = [format_note(note) for note in notes]
        
        return paginated_response(items, page, page_size, total)
        
    except Exception as e:
        return error_response('SERVER_ERROR', str(e), status_code=500)

@notes_bp.route('/<int:note_id>', methods=['GET'])
@require_auth
def get_note(note_id: int):
    """获取单条笔记"""
    try:
        note = get_note_by_id(note_id)
        
        if not note:
            return error_response('NOT_FOUND', f'Note {note_id} not found', status_code=404)
        
        # 权限检查
        if note['user_id'] != g.user_id:
            return error_response('FORBIDDEN', 'Access denied', status_code=403)
        
        return success_response(format_note(note))
        
    except Exception as e:
        return error_response('SERVER_ERROR', str(e), status_code=500)

@notes_bp.route('', methods=['POST'])
@require_auth
def create_note():
    """创建笔记"""
    try:
        data = request.get_json()
        
        # 参数验证
        if not data:
            return error_response('INVALID_PARAMETER', 'Request body is required')
        
        # 创建笔记
        note_id = add_note(
            user_id=g.user_id,
            source_chat_id=data.get('source_chat_id', 'web'),
            source_name=data.get('source_name', 'Web'),
            message_text=data.get('content', ''),
            title=data.get('title'),
            content_html=data.get('content_html'),
            content_markdown=data.get('content_markdown'),
        )
        
        # 添加标签
        if data.get('tags'):
            for tag_id in data['tags']:
                add_note_tag(note_id, tag_id)
        
        # 获取创建的笔记
        note = get_note_by_id(note_id)
        
        return success_response(format_note(note), message='Note created successfully')
        
    except Exception as e:
        return error_response('SERVER_ERROR', str(e), status_code=500)

@notes_bp.route('/<int:note_id>', methods=['PUT'])
@require_auth
def update_note_route(note_id: int):
    """更新笔记"""
    try:
        note = get_note_by_id(note_id)
        
        if not note:
            return error_response('NOT_FOUND', f'Note {note_id} not found', status_code=404)
        
        if note['user_id'] != g.user_id:
            return error_response('FORBIDDEN', 'Access denied', status_code=403)
        
        data = request.get_json()
        
        # 更新笔记
        update_note(
            note_id,
            title=data.get('title'),
            message_text=data.get('content'),
            content_html=data.get('content_html'),
            content_markdown=data.get('content_markdown'),
        )
        
        # 更新标签
        if 'tags' in data:
            # 先删除现有标签
            clear_note_tags(note_id)
            # 添加新标签
            for tag_id in data['tags']:
                add_note_tag(note_id, tag_id)
        
        # 获取更新后的笔记
        updated_note = get_note_by_id(note_id)
        
        return success_response(format_note(updated_note), message='Note updated successfully')
        
    except Exception as e:
        return error_response('SERVER_ERROR', str(e), status_code=500)

@notes_bp.route('/<int:note_id>', methods=['DELETE'])
@require_auth
def delete_note_route(note_id: int):
    """删除笔记"""
    try:
        note = get_note_by_id(note_id)
        
        if not note:
            return error_response('NOT_FOUND', f'Note {note_id} not found', status_code=404)
        
        if note['user_id'] != g.user_id:
            return error_response('FORBIDDEN', 'Access denied', status_code=403)
        
        # 删除笔记
        delete_note(note_id)
        
        return success_response(message='Note deleted successfully')
        
    except Exception as e:
        return error_response('SERVER_ERROR', str(e), status_code=500)

@notes_bp.route('/batch', methods=['POST'])
@require_auth
def batch_operation():
    """批量操作"""
    try:
        data = request.get_json()
        action = data.get('action')
        note_ids = data.get('note_ids', [])
        
        if not action or not note_ids:
            return error_response('INVALID_PARAMETER', 'action and note_ids are required')
        
        if action == 'delete':
            # 批量删除
            for note_id in note_ids:
                note = get_note_by_id(note_id)
                if note and note['user_id'] == g.user_id:
                    delete_note(note_id)
            
            return success_response(message=f'{len(note_ids)} notes deleted')
        
        elif action == 'archive':
            # 批量归档
            for note_id in note_ids:
                note = get_note_by_id(note_id)
                if note and note['user_id'] == g.user_id:
                    archive_note(note_id, True)
            
            return success_response(message=f'{len(note_ids)} notes archived')
        
        elif action == 'tag':
            # 批量添加标签
            tag_ids = data.get('tag_ids', [])
            for note_id in note_ids:
                note = get_note_by_id(note_id)
                if note and note['user_id'] == g.user_id:
                    for tag_id in tag_ids:
                        add_note_tag(note_id, tag_id)
            
            return success_response(message=f'Tags added to {len(note_ids)} notes')
        
        else:
            return error_response('INVALID_PARAMETER', f'Unknown action: {action}')
        
    except Exception as e:
        return error_response('SERVER_ERROR', str(e), status_code=500)

def format_note(note: Dict[str, Any]) -> Dict[str, Any]:
    """格式化笔记数据"""
    return {
        'id': note['id'],
        'title': note.get('title'),
        'content': note.get('message_text'),
        'contentHtml': note.get('content_html'),
        'contentMarkdown': note.get('content_markdown'),
        'sourceId': note['source_chat_id'],
        'sourceName': note.get('source_name'),
        'timestamp': note['timestamp'],
        'updatedAt': note.get('updated_at'),
        'isFavorite': bool(note.get('is_favorite')),
        'isArchived': bool(note.get('is_archived')),
        'viewCount': note.get('view_count', 0),
        'mediaFiles': note.get('media_files', []),
        'tags': note.get('tags', []),
        'magnetLink': note.get('magnet_link'),
    }
```

#### 3.1.4 认证机制

```python
# api/auth.py
from functools import wraps
from flask import request, g
from api.responses import error_response
import jwt
import os
from datetime import datetime, timedelta

SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'your-secret-key-change-in-production')
ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24小时

def generate_token(user_id: int, username: str) -> str:
    """生成JWT Token"""
    payload = {
        'user_id': user_id,
        'username': username,
        'exp': datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    """解码JWT Token"""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise ValueError('Token has expired')
    except jwt.InvalidTokenError:
        raise ValueError('Invalid token')

def require_auth(f):
    """认证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 从Header获取Token
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return error_response('UNAUTHORIZED', 'Authorization header is required', status_code=401)
        
        try:
            # 格式: "Bearer <token>"
            token = auth_header.split(' ')[1]
            payload = decode_token(token)
            
            # 将用户信息存储到g对象
            g.user_id = payload['user_id']
            g.username = payload['username']
            
        except (IndexError, ValueError) as e:
            return error_response('UNAUTHORIZED', str(e), status_code=401)
        
        return f(*args, **kwargs)
    
    return decorated_function

# 登录路由
from flask import Blueprint
from database import verify_user

auth_bp = Blueprint('auth', __name__, url_prefix='/api/v1/auth')

@auth_bp.route('/login', methods=['POST'])
def login():
    """用户登录"""
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return error_response('INVALID_PARAMETER', 'Username and password are required')
        
        # 验证用户
        user = verify_user(username, password)
        
        if not user:
            return error_response('INVALID_CREDENTIALS', 'Invalid username or password', status_code=401)
        
        # 生成Token
        token = generate_token(user['id'], user['username'])
        
        return success_response({
            'token': token,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'displayName': user.get('display_name'),
            }
        }, message='Login successful')
        
    except Exception as e:
        return error_response('SERVER_ERROR', str(e), status_code=500)

@auth_bp.route('/me', methods=['GET'])
@require_auth
def get_current_user():
    """获取当前用户信息"""
    try:
        from database import get_user_by_id
        user = get_user_by_id(g.user_id)
        
        return success_response({
            'id': user['id'],
            'username': user['username'],
            'email': user.get('email'),
            'displayName': user.get('display_name'),
            'avatarUrl': user.get('avatar_url'),
        })
        
    except Exception as e:
        return error_response('SERVER_ERROR', str(e), status_code=500)
```

---

### 3.2 状态管理（Pinia Store）

#### 3.2.1 Auth Store

```typescript
// stores/auth.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as authAPI from '@/api/auth'
import { useStorage } from '@vueuse/core'
import type { User } from '@/types/user'

export const useAuthStore = defineStore('auth', () => {
  // State
  const token = useStorage<string | null>('auth_token', null)
  const user = ref<User | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  
  // Getters
  const isAuthenticated = computed(() => !!token.value && !!user.value)
  const username = computed(() => user.value?.username || '')
  
  // Actions
  async function login(username: string, password: string) {
    loading.value = true
    error.value = null
    
    try {
      const response = await authAPI.login(username, password)
      
      if (response.success) {
        token.value = response.data.token
        user.value = response.data.user
        return true
      } else {
        error.value = response.error.message
        return false
      }
    } catch (err: any) {
      error.value = err.message || '登录失败'
      return false
    } finally {
      loading.value = false
    }
  }
  
  async function logout() {
    try {
      await authAPI.logout()
    } catch (err) {
      console.error('Logout error:', err)
    } finally {
      token.value = null
      user.value = null
    }
  }
  
  async function fetchCurrentUser() {
    if (!token.value) return
    
    try {
      const response = await authAPI.getCurrentUser()
      
      if (response.success) {
        user.value = response.data
      }
    } catch (err) {
      console.error('Fetch user error:', err)
      // Token可能过期，清除登录状态
      token.value = null
      user.value = null
    }
  }
  
  return {
    // State
    token,
    user,
    loading,
    error,
    // Getters
    isAuthenticated,
    username,
    // Actions
    login,
    logout,
    fetchCurrentUser
  }
})
```

#### 3.2.2 Notes Store

```typescript
// stores/notes.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as notesAPI from '@/api/notes'
import type { Note, NoteFilters } from '@/types/note'

export const useNotesStore = defineStore('notes', () => {
  // State
  const notes = ref<Note[]>([])
  const currentNote = ref<Note | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  
  // Pagination
  const currentPage = ref(1)
  const pageSize = ref(50)
  const total = ref(0)
  const hasMore = computed(() => notes.value.length < total.value)
  
  // Filters
  const filters = ref<NoteFilters>({})
  
  // Getters
  const totalCount = computed(() => total.value)
  const favoriteCount = computed(() => notes.value.filter(n => n.isFavorite).length)
  const totalPages = computed(() => Math.ceil(total.value / pageSize.value))
  
  // Top sources
  const topSources = computed(() => {
    const sourceMap = new Map<string, { id: string; name: string; count: number }>()
    
    notes.value.forEach(note => {
      const existing = sourceMap.get(note.sourceId)
      if (existing) {
        existing.count++
      } else {
        sourceMap.set(note.sourceId, {
          id: note.sourceId,
          name: note.sourceName || note.sourceId,
          count: 1
        })
      }
    })
    
    return Array.from(sourceMap.values())
      .sort((a, b) => b.count - a.count)
      .slice(0, 10)
  })
  
  // Actions
  async function fetchNotes(newFilters?: NoteFilters) {
    loading.value = true
    error.value = null
    
    if (newFilters) {
      filters.value = newFilters
      currentPage.value = 1
      notes.value = []
    }
    
    try {
      const response = await notesAPI.getNotes({
        page: currentPage.value,
        pageSize: pageSize.value,
        ...filters.value
      })
      
      if (response.success) {
        notes.value = response.data.items
        total.value = response.data.pagination.total
      }
    } catch (err: any) {
      error.value = err.message || '加载笔记失败'
    } finally {
      loading.value = false
    }
  }
  
  async function loadMore() {
    if (!hasMore.value || loading.value) return
    
    currentPage.value++
    loading.value = true
    
    try {
      const response = await notesAPI.getNotes({
        page: currentPage.value,
        pageSize: pageSize.value,
        ...filters.value
      })
      
      if (response.success) {
        notes.value.push(...response.data.items)
      }
    } catch (err: any) {
      error.value = err.message
    } finally {
      loading.value = false
    }
  }
  
  async function fetchNoteById(id: number) {
    loading.value = true
    error.value = null
    
    try {
      const response = await notesAPI.getNoteById(id)
      
      if (response.success) {
        currentNote.value = response.data
        return response.data
      }
    } catch (err: any) {
      error.value = err.message || '加载笔记失败'
    } finally {
      loading.value = false
    }
  }
  
  async function createNote(data: Partial<Note>) {
    loading.value = true
    error.value = null
    
    try {
      const response = await notesAPI.createNote(data)
      
      if (response.success) {
        notes.value.unshift(response.data)
        total.value++
        return response.data
      }
    } catch (err: any) {
      error.value = err.message || '创建笔记失败'
      throw err
    } finally {
      loading.value = false
    }
  }
  
  async function updateNote(id: number, data: Partial<Note>) {
    loading.value = true
    error.value = null
    
    try {
      const response = await notesAPI.updateNote(id, data)
      
      if (response.success) {
        const index = notes.value.findIndex(n => n.id === id)
        if (index !== -1) {
          notes.value[index] = response.data
        }
        if (currentNote.value?.id === id) {
          currentNote.value = response.data
        }
        return response.data
      }
    } catch (err: any) {
      error.value = err.message || '更新笔记失败'
      throw err
    } finally {
      loading.value = false
    }
  }
  
  async function deleteNote(id: number) {
    loading.value = true
    error.value = null
    
    try {
      const response = await notesAPI.deleteNote(id)
      
      if (response.success) {
        notes.value = notes.value.filter(n => n.id !== id)
        total.value--
        return true
      }
    } catch (err: any) {
      error.value = err.message || '删除笔记失败'
      throw err
    } finally {
      loading.value = false
    }
  }
  
  async function toggleFavorite(id: number) {
    try {
      const response = await notesAPI.toggleFavorite(id)
      
      if (response.success) {
        const note = notes.value.find(n => n.id === id)
        if (note) {
          note.isFavorite = !note.isFavorite
        }
      }
    } catch (err: any) {
      error.value = err.message || '操作失败'
    }
  }
  
  async function batchDelete(ids: number[]) {
    loading.value = true
    error.value = null
    
    try {
      const response = await notesAPI.batchOperation('delete', ids)
      
      if (response.success) {
        notes.value = notes.value.filter(n => !ids.includes(n.id))
        total.value -= ids.length
        return true
      }
    } catch (err: any) {
      error.value = err.message || '批量删除失败'
      throw err
    } finally {
      loading.value = false
    }
  }
  
  async function batchAddTags(noteIds: number[], tagIds: number[]) {
    loading.value = true
    error.value = null
    
    try {
      const response = await notesAPI.batchOperation('tag', noteIds, { tag_ids: tagIds })
      
      if (response.success) {
        // 更新本地笔记的标签
        await fetchNotes(filters.value)
        return true
      }
    } catch (err: any) {
      error.value = err.message || '批量添加标签失败'
      throw err
    } finally {
      loading.value = false
    }
  }
  
  return {
    // State
    notes,
    currentNote,
    loading,
    error,
    currentPage,
    pageSize,
    total,
    filters,
    // Getters
    hasMore,
    totalCount,
    favoriteCount,
    totalPages,
    topSources,
    // Actions
    fetchNotes,
    loadMore,
    fetchNoteById,
    createNote,
    updateNote,
    deleteNote,
    toggleFavorite,
    batchDelete,
    batchAddTags
  }
})
```

#### 3.2.3 Tags Store

```typescript
// stores/tags.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as tagsAPI from '@/api/tags'
import type { Tag } from '@/types/tag'

export const useTagsStore = defineStore('tags', () => {
  // State
  const tags = ref<Tag[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  
  // Getters
  const tagCount = computed(() => tags.value.length)
  const popularTags = computed(() => {
    return [...tags.value]
      .sort((a, b) => (b.use_count || 0) - (a.use_count || 0))
      .slice(0, 20)
  })
  
  // Actions
  async function fetchTags() {
    loading.value = true
    error.value = null
    
    try {
      const response = await tagsAPI.getTags()
      
      if (response.success) {
        tags.value = response.data
      }
    } catch (err: any) {
      error.value = err.message || '加载标签失败'
    } finally {
      loading.value = false
    }
  }
  
  async function createTag(data: Partial<Tag>) {
    loading.value = true
    error.value = null
    
    try {
      const response = await tagsAPI.createTag(data)
      
      if (response.success) {
        tags.value.push(response.data)
        return response.data
      }
    } catch (err: any) {
      error.value = err.message || '创建标签失败'
      throw err
    } finally {
      loading.value = false
    }
  }
  
  async function updateTag(id: number, data: Partial<Tag>) {
    loading.value = true
    error.value = null
    
    try {
      const response = await tagsAPI.updateTag(id, data)
      
      if (response.success) {
        const index = tags.value.findIndex(t => t.id === id)
        if (index !== -1) {
          tags.value[index] = response.data
        }
        return response.data
      }
    } catch (err: any) {
      error.value = err.message || '更新标签失败'
      throw err
    } finally {
      loading.value = false
    }
  }
  
  async function deleteTag(id: number) {
    loading.value = true
    error.value = null
    
    try {
      const response = await tagsAPI.deleteTag(id)
      
      if (response.success) {
        tags.value = tags.value.filter(t => t.id !== id)
        return true
      }
    } catch (err: any) {
      error.value = err.message || '删除标签失败'
      throw err
    } finally {
      loading.value = false
    }
  }
  
  function getTagById(id: number): Tag | undefined {
    return tags.value.find(t => t.id === id)
  }
  
  function getTagsByIds(ids: number[]): Tag[] {
    return tags.value.filter(t => ids.includes(t.id))
  }
  
  return {
    // State
    tags,
    loading,
    error,
    // Getters
    tagCount,
    popularTags,
    // Actions
    fetchTags,
    createTag,
    updateTag,
    deleteTag,
    getTagById,
    getTagsByIds
  }
})
```

#### 3.2.4 UI Store

```typescript
// stores/ui.ts
import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { useStorage, usePreferredDark } from '@vueuse/core'

type Theme = 'light' | 'dark' | 'auto'
type ViewMode = 'grid' | 'list' | 'timeline'

export const useUIStore = defineStore('ui', () => {
  // State
  const theme = useStorage<Theme>('theme', 'auto')
  const viewMode = useStorage<ViewMode>('view_mode', 'grid')
  const sidebarCollapsed = useStorage('sidebar_collapsed', false)
  const isMobile = ref(false)
  
  // Auto dark mode
  const prefersDark = usePreferredDark()
  
  // Getters
  const effectiveTheme = computed(() => {
    if (theme.value === 'auto') {
      return prefersDark.value ? 'dark' : 'light'
    }
    return theme.value
  })
  
  const isDark = computed(() => effectiveTheme.value === 'dark')
  
  // Actions
  function setTheme(newTheme: Theme) {
    theme.value = newTheme
  }
  
  function toggleTheme() {
    if (theme.value === 'light') {
      theme.value = 'dark'
    } else if (theme.value === 'dark') {
      theme.value = 'auto'
    } else {
      theme.value = 'light'
    }
  }
  
  function setViewMode(mode: ViewMode) {
    viewMode.value = mode
  }
  
  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }
  
  function checkMobile() {
    isMobile.value = window.innerWidth < 768
  }
  
  // Watch theme changes and apply to DOM
  watch(effectiveTheme, (newTheme) => {
    document.documentElement.classList.remove('theme-light', 'theme-dark')
    document.documentElement.classList.add(`theme-${newTheme}`)
  }, { immediate: true })
  
  // Initialize mobile check
  checkMobile()
  window.addEventListener('resize', checkMobile)
  
  return {
    // State
    theme,
    viewMode,
    sidebarCollapsed,
    isMobile,
    // Getters
    effectiveTheme,
    isDark,
    // Actions
    setTheme,
    toggleTheme,
    setViewMode,
    toggleSidebar,
    checkMobile
  }
})
```

---

### 3.3 API调用层（Composables）

#### 3.3.1 useNotes Composable

```typescript
// composables/useNotes.ts
import { ref, computed } from 'vue'
import { useNotesStore } from '@/stores/notes'
import { ElMessage } from 'element-plus'
import type { Note } from '@/types/note'

export function useNotes() {
  const notesStore = useNotesStore()
  
  const creating = ref(false)
  const updating = ref(false)
  const deleting = ref(false)
  
  // Create note
  const create = async (data: Partial<Note>) => {
    creating.value = true
    
    try {
      const note = await notesStore.createNote(data)
      ElMessage.success('笔记创建成功')
      return note
    } catch (error: any) {
      ElMessage.error(error.message || '创建失败')
      throw error
    } finally {
      creating.value = false
    }
  }
  
  // Update note
  const update = async (id: number, data: Partial<Note>) => {
    updating.value = true
    
    try {
      const note = await notesStore.updateNote(id, data)
      ElMessage.success('笔记更新成功')
      return note
    } catch (error: any) {
      ElMessage.error(error.message || '更新失败')
      throw error
    } finally {
      updating.value = false
    }
  }
  
  // Delete note
  const remove = async (id: number) => {
    deleting.value = true
    
    try {
      await notesStore.deleteNote(id)
      ElMessage.success('笔记删除成功')
    } catch (error: any) {
      ElMessage.error(error.message || '删除失败')
      throw error
    } finally {
      deleting.value = false
    }
  }
  
  // Toggle favorite
  const toggleFavorite = async (id: number) => {
    try {
      await notesStore.toggleFavorite(id)
    } catch (error: any) {
      ElMessage.error(error.message || '操作失败')
    }
  }
  
  return {
    // From store
    notes: computed(() => notesStore.notes),
    currentNote: computed(() => notesStore.currentNote),
    loading: computed(() => notesStore.loading),
    error: computed(() => notesStore.error),
    hasMore: computed(() => notesStore.hasMore),
    
    // Loading states
    creating,
    updating,
    deleting,
    
    // Actions
    fetch: notesStore.fetchNotes,
    loadMore: notesStore.loadMore,
    fetchById: notesStore.fetchNoteById,
    create,
    update,
    remove,
    toggleFavorite
  }
}
```

#### 3.3.2 useEditor Composable

```typescript
// composables/useEditor.ts
import { ref, onBeforeUnmount } from 'vue'
import { ElMessageBox } from 'element-plus'

export function useEditor() {
  const content = ref('')
  const isDirty = ref(false)
  const saving = ref(false)
  
  // Track changes
  const handleChange = (newContent: string) => {
    content.value = newContent
    isDirty.value = true
  }
  
  // Save function
  const save = async (saveFn: (content: string) => Promise<any>) => {
    if (!isDirty.value) return
    
    saving.value = true
    
    try {
      await saveFn(content.value)
      isDirty.value = false
    } finally {
      saving.value = false
    }
  }
  
  // Confirm unsaved changes
  const confirmLeave = async () => {
    if (!isDirty.value) return true
    
    try {
      await ElMessageBox.confirm(
        '您有未保存的更改，确定要离开吗？',
        '提示',
        {
          confirmButtonText: '离开',
          cancelButtonText: '取消',
          type: 'warning'
        }
      )
      return true
    } catch {
      return false
    }
  }
  
  // Warn before unload
  const handleBeforeUnload = (e: BeforeUnloadEvent) => {
    if (isDirty.value) {
      e.preventDefault()
      e.returnValue = ''
    }
  }
  
  window.addEventListener('beforeunload', handleBeforeUnload)
  
  onBeforeUnmount(() => {
    window.removeEventListener('beforeunload', handleBeforeUnload)
  })
  
  return {
    content,
    isDirty,
    saving,
    handleChange,
    save,
    confirmLeave
  }
}
```

#### 3.3.3 useInfiniteScroll Composable

```typescript
// composables/useInfiniteScroll.ts
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useThrottleFn } from '@vueuse/core'

interface InfiniteScrollOptions {
  onLoad: () => Promise<void>
  distance?: number
  disabled?: boolean
}

export function useInfiniteScroll(options: InfiniteScrollOptions) {
  const {
    onLoad,
    distance = 200,
    disabled = false
  } = options
  
  const containerRef = ref<HTMLElement | null>(null)
  const isLoading = ref(false)
  
  const checkScroll = useThrottleFn(async () => {
    if (disabled || isLoading.value) return
    
    const container = containerRef.value
    if (!container) return
    
    const scrollHeight = container.scrollHeight
    const scrollTop = container.scrollTop || window.pageYOffset
    const clientHeight = container.clientHeight || window.innerHeight
    
    const distanceToBottom = scrollHeight - scrollTop - clientHeight
    
    if (distanceToBottom < distance) {
      isLoading.value = true
      
      try {
        await onLoad()
      } finally {
        isLoading.value = false
      }
    }
  }, 200)
  
  onMounted(() => {
    const container = containerRef.value || window
    container.addEventListener('scroll', checkScroll)
  })
  
  onBeforeUnmount(() => {
    const container = containerRef.value || window
    container.removeEventListener('scroll', checkScroll)
  })
  
  return {
    containerRef,
    isLoading
  }
}
```

---

### 3.4 路由和导航

#### 3.4.1 完整路由配置

```typescript
// router/index.ts
import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { setupRouterGuards } from './guards'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
    meta: {
      title: '登录',
      requiresAuth: false
    }
  },
  {
    path: '/',
    component: () => import('@/components/layout/AppLayout.vue'),
    meta: {
      requiresAuth: true
    },
    children: [
      {
        path: '',
        redirect: '/notes'
      },
      {
        path: 'notes',
        name: 'Notes',
        component: () => import('@/views/NotesView.vue'),
        meta: {
          title: '笔记列表',
          transition: 'fade'
        }
      },
      {
        path: 'notes/new',
        name: 'NoteNew',
        component: () => import('@/views/NoteEditView.vue'),
        meta: {
          title: '新建笔记',
          transition: 'slide-up'
        }
      },
      {
        path: 'notes/:id',
        name: 'NoteDetail',
        component: () => import('@/views/NoteDetailView.vue'),
        meta: {
          title: '笔记详情',
          transition: 'fade'
        }
      },
      {
        path: 'notes/:id/edit',
        name: 'NoteEdit',
        component: () => import('@/views/NoteEditView.vue'),
        meta: {
          title: '编辑笔记',
          transition: 'slide-up'
        }
      },
      {
        path: 'notes/favorites',
        name: 'Favorites',
        component: () => import('@/views/NotesView.vue'),
        meta: {
          title: '收藏',
          favorite: true
        }
      },
      {
        path: 'search',
        name: 'Search',
        component: () => import('@/views/SearchView.vue'),
        meta: {
          title: '搜索'
        }
      },
      {
        path: 'tags',
        name: 'Tags',
        component: () => import('@/views/TagsView.vue'),
        meta: {
          title: '标签管理'
        }
      },
      {
        path: 'stats',
        name: 'Stats',
        component: () => import('@/views/StatsView.vue'),
        meta: {
          title: '统计分析'
        }
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/SettingsView.vue'),
        meta: {
          title: '设置'
        }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFoundView.vue'),
    meta: {
      title: '页面未找到'
    }
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) {
      return savedPosition
    } else {
      return { top: 0 }
    }
  }
})

setupRouterGuards(router)

export default router
```

#### 3.4.2 路由守卫

```typescript
// router/guards.ts
import type { Router } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import NProgress from 'nprogress'
import 'nprogress/nprogress.css'

NProgress.configure({ showSpinner: false })

export function setupRouterGuards(router: Router) {
  // 全局前置守卫
  router.beforeEach(async (to, from, next) => {
    NProgress.start()
    
    const authStore = useAuthStore()
    const requiresAuth = to.matched.some(record => record.meta.requiresAuth !== false)
    
    // 设置页面标题
    document.title = to.meta.title 
      ? `${to.meta.title} - Telegram Notes` 
      : 'Telegram Notes'
    
    // 检查认证
    if (requiresAuth && !authStore.isAuthenticated) {
      next({
        name: 'Login',
        query: { redirect: to.fullPath }
      })
    } else if (to.name === 'Login' && authStore.isAuthenticated) {
      next({ name: 'Notes' })
    } else {
      next()
    }
  })
  
  // 全局后置钩子
  router.afterEach(() => {
    NProgress.done()
  })
  
  // 错误处理
  router.onError((error) => {
    console.error('Router error:', error)
    NProgress.done()
  })
}
```

---

**继续编写中...**

本部分已完成：
- ✅ 3.1 后端API层设计
- ✅ 3.2 状态管理（Pinia Store）
- ✅ 3.3 API调用层（Composables）
- ✅ 3.4 路由和导航

下一部分将继续编写第四部分：CSS设计系统、第五部分：实施路线、以及其他剩余部分。
