import sqlite3
import bcrypt
from datetime import datetime
import os

# 数据目录 - 独立存储，防止更新时丢失
# 支持环境变量配置，默认为系统级独立目录 '/data/save_restricted_bot/'
DATA_DIR = os.environ.get('DATA_DIR', '/data/save_restricted_bot')
DATABASE_FILE = os.path.join(DATA_DIR, 'notes.db')

def init_database():
    """初始化数据库，创建必要的表"""
    # 确保数据目录和子目录存在
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, 'media'), exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, 'config'), exist_ok=True)
    
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    # 创建笔记表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            source_chat_id TEXT NOT NULL,
            source_name TEXT,
            message_text TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            media_type TEXT,
            media_path TEXT
        )
    ''')
    
    # 创建笔记媒体表（支持多图片）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS note_media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            note_id INTEGER NOT NULL,
            media_type TEXT NOT NULL,
            media_path TEXT NOT NULL,
            media_order INTEGER DEFAULT 0,
            FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE
        )
    ''')
    
    # 创建索引以提高查询性能
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_note_media_note_id 
        ON note_media(note_id)
    ''')
    
    # 创建用户表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')
    
    # 创建默认管理员账户 (admin/admin)
    try:
        password_hash = bcrypt.hashpw('admin'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', ('admin', password_hash))
    except sqlite3.IntegrityError:
        # 管理员账户已存在
        pass
    
    conn.commit()
    conn.close()

def add_note(user_id, source_chat_id, source_name, message_text, media_type=None, media_path=None, media_list=None):
    """
    添加一条笔记记录
    
    Args:
        user_id: 用户ID
        source_chat_id: 来源聊天ID
        source_name: 来源名称
        message_text: 消息文本
        media_type: 单个媒体类型（向后兼容）
        media_path: 单个媒体路径（向后兼容）
        media_list: 多媒体列表 [{'type': 'photo', 'path': 'xxx.jpg'}, ...]（最多9张）
    
    Returns:
        note_id: 新创建的笔记ID
    
    Raises:
        ValueError: 如果媒体数量超过9张
    """
    # 验证媒体数量限制（最多9张）
    if media_list and len(media_list) > 9:
        raise ValueError(f"每条笔记最多支持9张媒体，当前提供了{len(media_list)}张")
    
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    # 插入笔记主记录（保持向后兼容，media_type和media_path可能为空）
    cursor.execute('''
        INSERT INTO notes (user_id, source_chat_id, source_name, message_text, media_type, media_path)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, source_chat_id, source_name, message_text, media_type, media_path))
    
    note_id = cursor.lastrowid
    
    # 如果提供了多媒体列表，插入到 note_media 表
    if media_list:
        for idx, media_item in enumerate(media_list):
            cursor.execute('''
                INSERT INTO note_media (note_id, media_type, media_path, media_order)
                VALUES (?, ?, ?, ?)
            ''', (note_id, media_item['type'], media_item['path'], idx))
    
    conn.commit()
    conn.close()
    return note_id

def get_notes(user_id=None, source_chat_id=None, search_query=None, date_from=None, date_to=None, limit=50, offset=0):
    """获取笔记列表（包含多媒体信息）"""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = 'SELECT * FROM notes WHERE 1=1'
    params = []
    
    if user_id:
        query += ' AND user_id = ?'
        params.append(user_id)
    
    if source_chat_id:
        query += ' AND source_chat_id = ?'
        params.append(source_chat_id)
    
    if search_query:
        query += ' AND (message_text LIKE ? OR source_name LIKE ?)'
        search_pattern = f'%{search_query}%'
        params.extend([search_pattern, search_pattern])
    
    if date_from:
        query += ' AND DATE(timestamp) >= ?'
        params.append(date_from)
    
    if date_to:
        query += ' AND DATE(timestamp) <= ?'
        params.append(date_to)
    
    query += ' ORDER BY timestamp DESC LIMIT ? OFFSET ?'
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    notes = [dict(row) for row in cursor.fetchall()]
    
    # 为每条笔记加载多媒体列表
    for note in notes:
        note['media_list'] = get_note_media(note['id'])
    
    conn.close()
    return notes

def get_note_count(user_id=None, source_chat_id=None, search_query=None, date_from=None, date_to=None):
    """获取笔记总数"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    query = 'SELECT COUNT(*) FROM notes WHERE 1=1'
    params = []
    
    if user_id:
        query += ' AND user_id = ?'
        params.append(user_id)
    
    if source_chat_id:
        query += ' AND source_chat_id = ?'
        params.append(source_chat_id)
    
    if search_query:
        query += ' AND (message_text LIKE ? OR source_name LIKE ?)'
        search_pattern = f'%{search_query}%'
        params.extend([search_pattern, search_pattern])
    
    if date_from:
        query += ' AND DATE(timestamp) >= ?'
        params.append(date_from)
    
    if date_to:
        query += ' AND DATE(timestamp) <= ?'
        params.append(date_to)
    
    cursor.execute(query, params)
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_sources(user_id=None):
    """获取所有来源的列表"""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = 'SELECT DISTINCT source_chat_id, source_name FROM notes WHERE 1=1'
    params = []
    
    if user_id:
        query += ' AND user_id = ?'
        params.append(user_id)
    
    cursor.execute(query, params)
    sources = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return sources

def verify_user(username, password):
    """验证用户登录"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT password_hash FROM users WHERE username = ?', (username,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        password_hash = result[0]
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    return False

def update_password(username, new_password):
    """更新用户密码"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    cursor.execute('UPDATE users SET password_hash = ? WHERE username = ?', (password_hash, username))
    
    conn.commit()
    conn.close()

def get_note_media(note_id):
    """获取笔记的所有媒体文件"""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM note_media 
        WHERE note_id = ? 
        ORDER BY media_order
    ''', (note_id,))
    
    media_list = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return media_list

def get_note_by_id(note_id):
    """根据ID获取单条笔记（包含多媒体信息）"""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM notes WHERE id = ?', (note_id,))
    note = cursor.fetchone()
    conn.close()
    
    if note:
        note_dict = dict(note)
        # 获取关联的多媒体
        note_dict['media_list'] = get_note_media(note_id)
        return note_dict
    return None

def update_note(note_id, message_text):
    """更新笔记内容"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    cursor.execute('UPDATE notes SET message_text = ? WHERE id = ?', (message_text, note_id))
    
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0

def delete_note(note_id):
    """删除笔记（包括所有关联媒体文件）"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    # 获取笔记的旧版单媒体路径
    cursor.execute('SELECT media_path FROM notes WHERE id = ?', (note_id,))
    result = cursor.fetchone()
    old_media_path = result[0] if result and result[0] else None
    
    # 获取笔记的多媒体列表
    cursor.execute('SELECT media_path FROM note_media WHERE note_id = ?', (note_id,))
    media_paths = [row[0] for row in cursor.fetchall()]
    
    # 删除笔记记录（会级联删除 note_media）
    cursor.execute('DELETE FROM notes WHERE id = ?', (note_id,))
    
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    
    # 删除旧版单媒体文件
    if old_media_path:
        try:
            full_media_path = os.path.join(DATA_DIR, 'media', old_media_path)
            if os.path.exists(full_media_path):
                os.remove(full_media_path)
        except Exception as e:
            print(f"Error deleting old media file: {e}")
    
    # 删除多媒体文件
    for media_path in media_paths:
        try:
            full_media_path = os.path.join(DATA_DIR, 'media', media_path)
            if os.path.exists(full_media_path):
                os.remove(full_media_path)
        except Exception as e:
            print(f"Error deleting media file {media_path}: {e}")
    
    return affected > 0

# 初始化数据库（确保表和默认用户存在）
init_database()
