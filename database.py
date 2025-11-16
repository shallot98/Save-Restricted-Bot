import sqlite3
import bcrypt
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import json
import logging
from contextlib import contextmanager
from constants import DB_DEDUP_WINDOW

logger = logging.getLogger(__name__)

# 设置中国时区
CHINA_TZ = ZoneInfo("Asia/Shanghai")

# 数据目录 - 独立存储，防止更新时丢失
DEFAULT_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'data'))
DATA_DIR = os.environ.get('DATA_DIR', DEFAULT_DATA_DIR)
DATABASE_FILE = os.path.join(DATA_DIR, 'notes.db')


@contextmanager
def get_db_connection():
    """Database connection context manager"""
    conn = sqlite3.connect(DATABASE_FILE)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

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
                media_paths TEXT,
                media_group_id TEXT
            )
        ''')
        print("✅ notes 表创建成功")
        
        # 检查并添加 media_paths 列（迁移旧数据库）
        print("🔄 检查 media_paths 列是否存在...")
        cursor.execute("PRAGMA table_info(notes)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'media_paths' not in columns:
            print("➕ 添加 media_paths 列...")
            cursor.execute("ALTER TABLE notes ADD COLUMN media_paths TEXT")
            conn.commit()
            print("✅ media_paths 列添加成功")
        else:
            print("✅ media_paths 列已存在")
        
        # 检查并添加 media_group_id 列（迁移旧数据库）
        print("🔄 检查 media_group_id 列是否存在...")
        cursor.execute("PRAGMA table_info(notes)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'media_group_id' not in columns:
            print("➕ 添加 media_group_id 列...")
            cursor.execute("ALTER TABLE notes ADD COLUMN media_group_id TEXT")
            conn.commit()
            print("✅ media_group_id 列添加成功")
        else:
            print("✅ media_group_id 列已存在")
        
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

def _validate_and_convert_params(user_id, source_chat_id):
    """Validate and convert note parameters"""
    if user_id is None:
        raise ValueError("user_id 不能为 None")
    if source_chat_id is None:
        raise ValueError("source_chat_id 不能为 None")
    
    # 确保 user_id 是整数
    if not isinstance(user_id, int):
        try:
            user_id = int(user_id)
        except (ValueError, TypeError) as e:
            raise ValueError(f"user_id 必须是整数或可转换为整数的值: {user_id}") from e
    
    # 确保 source_chat_id 是字符串
    if not isinstance(source_chat_id, str):
        source_chat_id = str(source_chat_id)
    
    return user_id, source_chat_id


def _check_duplicate_media_group(cursor, user_id, source_chat_id, media_group_id):
    """Check for duplicate media groups"""
    cursor.execute(
        "SELECT id FROM notes WHERE user_id=? AND source_chat_id=? AND media_group_id=? LIMIT 1",
        (user_id, source_chat_id, media_group_id)
    )
    existing = cursor.fetchone()
    if existing:
        existing_id = existing[0]
        logger.debug(f"媒体组已存在，跳过重复保存 (existing_id={existing_id})")
        return existing_id
    return None


def _check_duplicate_message(cursor, user_id, source_chat_id, message_text):
    """Check for duplicate messages within time window"""
    cursor.execute(f"""
        SELECT id FROM notes 
        WHERE user_id=? AND source_chat_id=? AND message_text=? 
        AND datetime(timestamp) > datetime('now', '-{DB_DEDUP_WINDOW} seconds')
        LIMIT 1
    """, (user_id, source_chat_id, message_text))
    existing = cursor.fetchone()
    if existing:
        existing_id = existing[0]
        logger.debug(f"消息在{DB_DEDUP_WINDOW}秒内已保存，跳过重复 (existing_id={existing_id})")
        return existing_id
    return None


def add_note(user_id, source_chat_id, source_name, message_text, media_type=None, media_path=None, media_paths=None, media_group_id=None):
    """添加一条笔记记录"""
    try:
        logger.debug(f"开始保存笔记: user_id={user_id}, source={source_chat_id}, media_type={media_type}")
        
        # 验证和转换参数
        user_id, source_chat_id = _validate_and_convert_params(user_id, source_chat_id)
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check for duplicate media groups
            if media_group_id:
                existing_id = _check_duplicate_media_group(cursor, user_id, source_chat_id, media_group_id)
                if existing_id:
                    return existing_id
            
            # Check for duplicate messages
            if message_text and not media_group_id:
                existing_id = _check_duplicate_message(cursor, user_id, source_chat_id, message_text)
                if existing_id:
                    return existing_id
            
            # Prepare media paths JSON
            media_paths_json = None
            if media_paths:
                if media_path is None:
                    media_path = media_paths[0]
                media_paths_json = json.dumps(media_paths, ensure_ascii=False)
            
            # Generate China timezone timestamp
            china_timestamp = datetime.now(CHINA_TZ).strftime('%Y-%m-%d %H:%M:%S')
            
            # Insert note
            cursor.execute('''
                INSERT INTO notes (user_id, source_chat_id, source_name, message_text, timestamp, media_type, media_path, media_paths, media_group_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, source_chat_id, source_name, message_text, china_timestamp, media_type, media_path, media_paths_json, media_group_id))
            
            note_id = cursor.lastrowid
            logger.info(f"✅ 笔记保存成功！note_id={note_id}")
            return note_id
        
    except sqlite3.Error as e:
        logger.error(f"SQLite 错误: {type(e).__name__}: {e}")
        raise
    except Exception as e:
        logger.error(f"保存笔记失败: {type(e).__name__}: {e}")
        raise

def _parse_media_paths(note):
    """Parse media paths from JSON string"""
    if note.get('media_paths'):
        try:
            note['media_paths'] = json.loads(note['media_paths'])
        except (json.JSONDecodeError, TypeError):
            note['media_paths'] = []
    else:
        note['media_paths'] = []
    
    # Fallback: if media_paths is empty but media_path exists
    if not note['media_paths'] and note.get('media_path'):
        note['media_paths'] = [note['media_path']]
    
    return note


def get_notes(user_id=None, source_chat_id=None, search_query=None, date_from=None, date_to=None, limit=50, offset=0):
    """获取笔记列表"""
    with get_db_connection() as conn:
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
        notes = [_parse_media_paths(dict(row)) for row in cursor.fetchall()]
        return notes

def get_note_count(user_id=None, source_chat_id=None, search_query=None, date_from=None, date_to=None):
    """获取笔记总数"""
    with get_db_connection() as conn:
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
        return cursor.fetchone()[0]

def get_sources(user_id=None):
    """获取所有来源的列表"""
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = 'SELECT DISTINCT source_chat_id, source_name FROM notes WHERE 1=1'
        params = []
        
        if user_id:
            query += ' AND user_id = ?'
            params.append(user_id)
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def verify_user(username, password):
    """验证用户登录"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT password_hash FROM users WHERE username = ?', (username,))
        result = cursor.fetchone()
        
        if result:
            password_hash = result[0]
            return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
        return False


def update_password(username, new_password):
    """更新用户密码"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cursor.execute('UPDATE users SET password_hash = ? WHERE username = ?', (password_hash, username))


def get_note_by_id(note_id):
    """根据ID获取单条笔记"""
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM notes WHERE id = ?', (note_id,))
        row = cursor.fetchone()
        
        if row:
            return _parse_media_paths(dict(row))
        return None


def update_note(note_id, message_text):
    """更新笔记内容"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE notes SET message_text = ? WHERE id = ?', (message_text, note_id))
        return cursor.rowcount > 0


def delete_note(note_id):
    """删除笔记"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 先获取笔记信息以删除关联的媒体文件
        cursor.execute('SELECT media_path, media_paths FROM notes WHERE id = ?', (note_id,))
        result = cursor.fetchone()
        
        media_files = set()
        if result:
            single_path, media_paths_json = result
            if single_path:
                media_files.add(single_path)
            if media_paths_json:
                try:
                    media_files.update(path for path in json.loads(media_paths_json) if path)
                except (json.JSONDecodeError, TypeError):
                    pass
        
        # 删除数据库记录
        cursor.execute('DELETE FROM notes WHERE id = ?', (note_id,))
        affected = cursor.rowcount
    
    # 删除关联的媒体文件
    for media_path in media_files:
        try:
            full_media_path = os.path.join(DATA_DIR, 'media', media_path)
            if os.path.exists(full_media_path):
                os.remove(full_media_path)
        except Exception as e:
            logger.warning(f"删除媒体文件失败: {e}")
    
    return affected > 0

# 初始化数据库（确保表和默认用户存在）
init_database()
