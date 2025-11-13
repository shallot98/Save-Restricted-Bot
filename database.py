import sqlite3
import bcrypt
from datetime import datetime
import os
import json

# 数据目录 - 独立存储，防止更新时丢失
DEFAULT_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'data'))
DATA_DIR = os.environ.get('DATA_DIR', DEFAULT_DATA_DIR)
DATABASE_FILE = os.path.join(DATA_DIR, 'notes.db')

def init_database():
    """初始化数据库，创建必要的表"""
    try:
        print("=" * 50)
        print("🔧 正在初始化数据库...")
        print(f"📁 数据目录: {DATA_DIR}")
        print(f"💾 数据库路径: {DATABASE_FILE}")
        
        # 确保数据目录存在
        os.makedirs(DATA_DIR, exist_ok=True)
        print(f"✅ 数据目录已确认存在")
        
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # 创建笔记表
        print("📝 正在创建 notes 表...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                source_chat_id TEXT NOT NULL,
                source_name TEXT,
                message_text TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                media_type TEXT,
                media_path TEXT,
                media_paths TEXT
            )
        ''')
        print("✅ notes 表创建成功")
        
        # 创建用户表
        print("👤 正在创建 users 表...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        ''')
        print("✅ users 表创建成功")
        
        # 创建默认管理员账户 (admin/admin)
        try:
            print("🔐 正在创建默认管理员账户...")
            password_hash = bcrypt.hashpw('admin'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', ('admin', password_hash))
            print("✅ 默认管理员账户创建成功 (admin/admin)")
        except sqlite3.IntegrityError:
            # 管理员账户已存在
            print("ℹ️  管理员账户已存在，跳过创建")
        
        conn.commit()
        
        # 验证表是否创建成功
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"📊 数据库中的表: {', '.join(tables)}")
        
        # 检查 notes 表中的记录数
        cursor.execute("SELECT COUNT(*) FROM notes")
        notes_count = cursor.fetchone()[0]
        print(f"📝 notes 表中现有记录数: {notes_count}")
        
        conn.close()
        print("✅ 数据库初始化完成！")
        print("=" * 50)
        
    except Exception as e:
        print("=" * 50)
        print(f"❌ 数据库初始化失败！")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误信息: {str(e)}")
        print("=" * 50)
        raise

def add_note(user_id, source_chat_id, source_name, message_text, media_type=None, media_path=None, media_paths=None):
    """添加一条笔记记录"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    # 将media_paths列表转换为JSON字符串
    if media_paths:
        if media_path is None:
            media_path = media_paths[0]
        media_paths_json = json.dumps(media_paths)
    else:
        media_paths_json = None
    
    cursor.execute('''
        INSERT INTO notes (user_id, source_chat_id, source_name, message_text, media_type, media_path, media_paths)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, source_chat_id, source_name, message_text, media_type, media_path, media_paths_json))
    
    conn.commit()
    note_id = cursor.lastrowid
    conn.close()
    return note_id

def get_notes(user_id=None, source_chat_id=None, search_query=None, date_from=None, date_to=None, limit=50, offset=0):
    """获取笔记列表"""
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
    notes = []
    for row in cursor.fetchall():
        note = dict(row)
        # 解析media_paths JSON字符串为列表
        if note.get('media_paths'):
            try:
                note['media_paths'] = json.loads(note['media_paths'])
            except:
                note['media_paths'] = []
        else:
            note['media_paths'] = []
        if note['media_paths'] == [] and note.get('media_path'):
            note['media_paths'] = [note['media_path']]
        notes.append(note)
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

def get_note_by_id(note_id):
    """根据ID获取单条笔记"""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM notes WHERE id = ?', (note_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        note = dict(row)
        # 解析media_paths JSON字符串为列表
        if note.get('media_paths'):
            try:
                note['media_paths'] = json.loads(note['media_paths'])
            except:
                note['media_paths'] = []
        else:
            note['media_paths'] = []
        if note['media_paths'] == [] and note.get('media_path'):
            note['media_paths'] = [note['media_path']]
        return note
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
    """删除笔记"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    # 先获取笔记信息以删除关联的媒体文件
    cursor.execute('SELECT media_path, media_paths FROM notes WHERE id = ?', (note_id,))
    result = cursor.fetchone()
    
    media_files = set()
    if result:
        single_path = result[0]
        media_paths_json = result[1]
        if single_path:
            media_files.add(single_path)
        if media_paths_json:
            try:
                for path in json.loads(media_paths_json):
                    if path:
                        media_files.add(path)
            except:
                pass
    
    # 删除数据库记录
    cursor.execute('DELETE FROM notes WHERE id = ?', (note_id,))
    
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    
    # 删除关联的媒体文件
    for media_path in media_files:
        try:
            full_media_path = os.path.join(DATA_DIR, 'media', media_path)
            if os.path.exists(full_media_path):
                os.remove(full_media_path)
        except Exception as e:
            print(f"Error deleting media file: {e}")
    
    return affected > 0

# 初始化数据库（确保表和默认用户存在）
init_database()
