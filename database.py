import sqlite3
import bcrypt
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import json
import logging
import re
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
                media_group_id TEXT,
                magnet_link TEXT
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

        # 检查并添加 magnet_link 列（迁移旧数据库）
        print("🔄 检查 magnet_link 列是否存在...")
        cursor.execute("PRAGMA table_info(notes)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'magnet_link' not in columns:
            print("➕ 添加 magnet_link 列...")
            cursor.execute("ALTER TABLE notes ADD COLUMN magnet_link TEXT")
            conn.commit()
            print("✅ magnet_link 列添加成功")
        else:
            print("✅ magnet_link 列已存在")

        # 检查并添加 filename 列（用于存储校准后的文件名）
        print("🔄 检查 filename 列是否存在...")
        cursor.execute("PRAGMA table_info(notes)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'filename' not in columns:
            print("➕ 添加 filename 列...")
            cursor.execute("ALTER TABLE notes ADD COLUMN filename TEXT")
            conn.commit()
            print("✅ filename 列添加成功")
        else:
            print("✅ filename 列已存在")

        # 检查并添加 is_favorite 列（收藏功能）
        print("🔄 检查 is_favorite 列是否存在...")
        cursor.execute("PRAGMA table_info(notes)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'is_favorite' not in columns:
            print("➕ 添加 is_favorite 列...")
            cursor.execute("ALTER TABLE notes ADD COLUMN is_favorite INTEGER DEFAULT 0")
            conn.commit()
            print("✅ is_favorite 列添加成功")
        else:
            print("✅ is_favorite 列已存在")

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

        # 创建校准任务表
        print("🔧 正在创建 calibration_tasks 表...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS calibration_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                note_id INTEGER NOT NULL,
                magnet_hash TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                retry_count INTEGER DEFAULT 0,
                last_attempt DATETIME,
                next_attempt DATETIME NOT NULL,
                error_message TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE
            )
        ''')
        print("✅ calibration_tasks 表创建成功")

        # 创建索引以提高查询效率
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_calibration_status
            ON calibration_tasks(status, next_attempt)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_calibration_note
            ON calibration_tasks(note_id)
        ''')

        # 创建自动校准配置表
        print("⚙️ 正在创建 auto_calibration_config 表...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS auto_calibration_config (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                enabled BOOLEAN DEFAULT 0,
                filter_mode TEXT DEFAULT 'empty_only',
                first_delay INTEGER DEFAULT 600,
                retry_delay_1 INTEGER DEFAULT 3600,
                retry_delay_2 INTEGER DEFAULT 14400,
                retry_delay_3 INTEGER DEFAULT 28800,
                max_retries INTEGER DEFAULT 3,
                concurrent_limit INTEGER DEFAULT 5,
                timeout_per_magnet INTEGER DEFAULT 30,
                batch_timeout INTEGER DEFAULT 300
            )
        ''')

        # 插入默认配置
        cursor.execute('''
            INSERT OR IGNORE INTO auto_calibration_config (id, enabled, filter_mode)
            VALUES (1, 0, 'empty_only')
        ''')
        print("✅ auto_calibration_config 表创建成功")
        
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


def _extract_magnet_link(message_text):
    """从消息文本中提取磁力链接"""
    if not message_text:
        return None

    # 匹配完整的磁力链接格式: magnet:?xt=urn:btih:...（包含所有参数）
    # 匹配到换行、竖线或字符串结束为止（允许空格，因为dn参数中可能有空格）
    magnet_pattern = r'magnet:\?xt=urn:btih:[a-zA-Z0-9]+(?:[&?][^\n\r|]*)?'
    match = re.search(magnet_pattern, message_text, re.IGNORECASE)

    if match:
        magnet_link = match.group(0).rstrip()

        # 检测是否有 dn 参数
        if '&dn=' not in magnet_link and '?dn=' not in magnet_link:
            # 提取开头至第一个 # 之前的内容作为 dn
            hash_pos = message_text.find('#')
            dn_text = message_text[:hash_pos].rstrip() if hash_pos != -1 else message_text.rstrip()

            if dn_text:
                # URL编码dn参数，保留空格和特殊字符
                from urllib.parse import quote
                magnet_link += f'&dn={quote(dn_text)}'

        return magnet_link
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

            # Extract magnet link from message text
            magnet_link = _extract_magnet_link(message_text)

            # Generate China timezone timestamp
            china_timestamp = datetime.now(CHINA_TZ).strftime('%Y-%m-%d %H:%M:%S')

            # Insert note (filename留空，由自动校准填充)
            cursor.execute('''
                INSERT INTO notes (user_id, source_chat_id, source_name, message_text, timestamp, media_type, media_path, media_paths, media_group_id, magnet_link, filename)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, source_chat_id, source_name, message_text, china_timestamp, media_type, media_path, media_paths_json, media_group_id, magnet_link, None))

            note_id = cursor.lastrowid
            logger.info(f"✅ 笔记保存成功！note_id={note_id}, magnet_link={'有' if magnet_link else '无'}")

        # 事务已提交，现在可以安全地添加到校准队列
        # 自动添加到校准队列（如果启用了自动校准）
        logger.info(f"📋 检查校准条件: note_id={note_id}, has_magnet={bool(magnet_link)}")
        if note_id and magnet_link:
            try:
                # 延迟导入避免循环依赖
                from bot.services.calibration_manager import get_calibration_manager
                manager = get_calibration_manager()
                is_enabled = manager.is_enabled()
                logger.info(f"🔧 校准管理器已加载: enabled={is_enabled}")
                if is_enabled:
                    # 在事务外异步添加，避免阻塞
                    import threading
                    logger.info(f"🚀 启动校准任务线程: note_id={note_id}")
                    threading.Thread(
                        target=manager.add_note_to_calibration_queue,
                        args=(note_id,),
                        daemon=True
                    ).start()
                    logger.info(f"✅ 校准线程已启动: note_id={note_id}")
                else:
                    logger.info(f"⏭️ 自动校准未启用，跳过 note_id={note_id}")
            except Exception as e:
                logger.error(f"❌ 添加到校准队列失败: {e}", exc_info=True)
        else:
            logger.info(f"⏭️ 跳过校准: note_id={note_id}, magnet_link={magnet_link[:50] if magnet_link else 'None'}")

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


def get_notes(user_id=None, source_chat_id=None, search_query=None, date_from=None, date_to=None, favorite_only=False, limit=50, offset=0):
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

        if favorite_only:
            query += ' AND is_favorite = 1'

        query += ' ORDER BY timestamp DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])

        cursor.execute(query, params)
        notes = [_parse_media_paths(dict(row)) for row in cursor.fetchall()]
        return notes

def get_note_count(user_id=None, source_chat_id=None, search_query=None, date_from=None, date_to=None, favorite_only=False):
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

        if favorite_only:
            query += ' AND is_favorite = 1'

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


def update_magnet_link(note_id, magnet_link):
    """更新磁力链接"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE notes SET magnet_link = ? WHERE id = ?', (magnet_link, note_id))
        return cursor.rowcount > 0


def update_note_with_calibrated_dns(note_id, calibrated_results):
    """校准后更新笔记：同时更新多个磁力链接的dn参数

    Args:
        note_id: 笔记ID
        calibrated_results: 校准结果列表 [{'info_hash': ..., 'old_magnet': ..., 'filename': ..., 'success': bool}, ...]

    Returns:
        bool: 是否更新成功
    """
    import re
    from urllib.parse import quote

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 获取当前笔记内容
        cursor.execute('SELECT message_text, magnet_link FROM notes WHERE id = ?', (note_id,))
        row = cursor.fetchone()
        if not row:
            return False

        message_text, old_magnet = row
        updated_text = message_text

        # 更新笔记文本中的每个磁力链接
        if message_text:
            for result in calibrated_results:
                if not result.get('success'):
                    continue  # 跳过失败的校准

                info_hash = result['info_hash']
                filename = result.get('filename', '')

                # 构建新的磁力链接（使用原始文件名，不编码）
                new_magnet = f"magnet:?xt=urn:btih:{info_hash}&dn={filename}"

                # 在文本中查找并替换该磁力链接
                # 匹配: magnet:?xt=urn:btih:{hash} 后面跟任意参数直到换行或结束
                magnet_pattern = rf'magnet:\?xt=urn:btih:{re.escape(info_hash)}(?:[&?][^\n\r]*)?'

                # 替换找到的磁力链接
                updated_text = re.sub(magnet_pattern, new_magnet, updated_text, flags=re.IGNORECASE)

        # 更新magnet_link字段（使用第一个成功校准的磁力链接）
        new_magnet_link = old_magnet
        new_filename = None
        for result in calibrated_results:
            if result.get('success'):
                info_hash = result['info_hash']
                filename = result.get('filename', '')
                old_magnet_for_db = result['old_magnet']

                # 移除旧的 dn 参数
                new_magnet_base = re.sub(r'[&?]dn=[^&]*', '', old_magnet_for_db)

                # 添加URL编码的dn参数（用于存储）
                encoded_filename = quote(filename) if filename else ""
                new_magnet_link = f"{new_magnet_base}&dn={encoded_filename}"
                new_filename = filename  # 保存用于更新filename字段
                break  # 只使用第一个成功的

        # 更新数据库（包括filename字段）
        cursor.execute(
            'UPDATE notes SET message_text = ?, magnet_link = ?, filename = ? WHERE id = ?',
            (updated_text, new_magnet_link, new_filename, note_id)
        )

        return cursor.rowcount > 0


def update_note_with_calibrated_dn(note_id, new_magnet_link, filename):
    """校准后更新笔记：同时更新磁力链接和笔记文本中的 dn 参数（保留向后兼容）

    Args:
        note_id: 笔记ID
        new_magnet_link: 新的磁力链接（已包含URL编码的dn，用于数据库存储）
        filename: 校准后的原始文件名（未编码，用于笔记文本显示）

    Returns:
        bool: 是否更新成功
    """
    import re

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 获取当前笔记内容
        cursor.execute('SELECT message_text, magnet_link FROM notes WHERE id = ?', (note_id,))
        row = cursor.fetchone()
        if not row:
            return False

        message_text, old_magnet = row

        # 更新笔记文本中的磁力链接（使用原始文件名，不编码）
        updated_text = message_text

        if message_text:
            # 提取 info hash（用于匹配磁力链接）
            info_hash_match = re.search(r'xt=urn:btih:([a-zA-Z0-9]+)', new_magnet_link, re.IGNORECASE)
            if info_hash_match:
                info_hash = info_hash_match.group(1)

                # 构建用于笔记文本的磁力链接（使用未编码的文件名）
                text_magnet_base = re.sub(r'[&?]dn=[^&]*', '', new_magnet_link)
                text_magnet = f"{text_magnet_base}&dn={filename}"

                # 在文本中查找包含该 info hash 的磁力链接（可能有或没有 dn 参数）
                # 匹配格式: magnet:?xt=urn:btih:{hash}(任意参数直到换行或结束)
                magnet_pattern = rf'magnet:\?xt=urn:btih:{re.escape(info_hash)}(?:[&?][^\n\r]*)?'

                # 替换找到的磁力链接（使用未编码版本）
                updated_text = re.sub(magnet_pattern, text_magnet, message_text, flags=re.IGNORECASE)

        # 更新数据库：
        # - message_text: 使用未编码的文件名
        # - magnet_link: 使用URL编码的文件名
        # - filename: 校准后的文件名
        cursor.execute(
            'UPDATE notes SET message_text = ?, magnet_link = ?, filename = ? WHERE id = ?',
            (updated_text, new_magnet_link, filename, note_id)
        )

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

# ==================== 自动校准功能 ====================

def get_calibration_config():
    """获取自动校准配置"""
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM auto_calibration_config WHERE id = 1')
        row = cursor.fetchone()
        return dict(row) if row else None


def update_calibration_config(config):
    """更新自动校准配置"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE auto_calibration_config
            SET enabled = ?,
                filter_mode = ?,
                first_delay = ?,
                retry_delay_1 = ?,
                retry_delay_2 = ?,
                retry_delay_3 = ?,
                max_retries = ?,
                concurrent_limit = ?,
                timeout_per_magnet = ?,
                batch_timeout = ?
            WHERE id = 1
        ''', (
            config.get('enabled', 0),
            config.get('filter_mode', 'empty_only'),
            config.get('first_delay', 600),
            config.get('retry_delay_1', 3600),
            config.get('retry_delay_2', 14400),
            config.get('retry_delay_3', 28800),
            config.get('max_retries', 3),
            config.get('concurrent_limit', 5),
            config.get('timeout_per_magnet', 30),
            config.get('batch_timeout', 300)
        ))
        return cursor.rowcount > 0


def add_calibration_task(note_id, magnet_hash, delay_seconds=600):
    """添加校准任务到队列

    Args:
        note_id: 笔记ID
        magnet_hash: 磁力链接的info hash
        delay_seconds: 延迟执行时间（秒）
    """
    from datetime import datetime, timedelta

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # 检查是否已存在相同的待处理任务
            cursor.execute('''
                SELECT id FROM calibration_tasks
                WHERE note_id = ? AND status IN ('pending', 'retrying')
            ''', (note_id,))

            if cursor.fetchone():
                logger.debug(f"笔记 {note_id} 已存在待处理的校准任务，跳过添加")
                return None

            # 使用中国时区时间
            now_china = datetime.now(CHINA_TZ)
            next_attempt = now_china + timedelta(seconds=delay_seconds)

            # 明确设置created_at为中国时间,防止SQLite的CURRENT_TIMESTAMP使用UTC
            cursor.execute('''
                INSERT INTO calibration_tasks (note_id, magnet_hash, status, next_attempt, created_at)
                VALUES (?, ?, 'pending', ?, ?)
            ''', (note_id, magnet_hash, next_attempt.strftime('%Y-%m-%d %H:%M:%S'), now_china.strftime('%Y-%m-%d %H:%M:%S')))

            task_id = cursor.lastrowid
            logger.info(f"✅ 添加校准任务: note_id={note_id}, task_id={task_id}, 将在 {next_attempt.strftime('%H:%M:%S')} 执行")
            return task_id

    except Exception as e:
        logger.error(f"添加校准任务失败: {e}")
        return None


def get_pending_calibration_tasks(limit=100):
    """获取待执行的校准任务"""
    from datetime import datetime

    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        now = datetime.now(CHINA_TZ).strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
            SELECT * FROM calibration_tasks
            WHERE status IN ('pending', 'retrying')
            AND next_attempt <= ?
            ORDER BY next_attempt ASC
            LIMIT ?
        ''', (now, limit))

        return [dict(row) for row in cursor.fetchall()]


def update_calibration_task(task_id, status, error_message=None, next_retry_seconds=None):
    """更新校准任务状态

    Args:
        task_id: 任务ID
        status: 新状态 ('success', 'failed', 'retrying')
        error_message: 错误消息（可选）
        next_retry_seconds: 下次重试延迟（秒，仅status='retrying'时有效）
    """
    from datetime import datetime, timedelta

    with get_db_connection() as conn:
        cursor = conn.cursor()

        now = datetime.now(CHINA_TZ).strftime('%Y-%m-%d %H:%M:%S')

        if status == 'retrying' and next_retry_seconds:
            next_attempt = datetime.now(CHINA_TZ) + timedelta(seconds=next_retry_seconds)
            cursor.execute('''
                UPDATE calibration_tasks
                SET status = ?,
                    retry_count = retry_count + 1,
                    last_attempt = ?,
                    next_attempt = ?,
                    error_message = ?
                WHERE id = ?
            ''', (status, now, next_attempt.strftime('%Y-%m-%d %H:%M:%S'), error_message, task_id))
        else:
            cursor.execute('''
                UPDATE calibration_tasks
                SET status = ?,
                    last_attempt = ?,
                    error_message = ?
                WHERE id = ?
            ''', (status, now, error_message, task_id))

        return cursor.rowcount > 0


def get_calibration_stats():
    """获取校准任务统计信息"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        stats = {}

        # 总任务数
        cursor.execute('SELECT COUNT(*) FROM calibration_tasks')
        stats['total'] = cursor.fetchone()[0]

        # 各状态任务数
        cursor.execute('''
            SELECT status, COUNT(*) as count
            FROM calibration_tasks
            GROUP BY status
        ''')
        stats['by_status'] = {row[0]: row[1] for row in cursor.fetchall()}

        # 待处理任务数
        from datetime import datetime
        now = datetime.now(CHINA_TZ).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            SELECT COUNT(*) FROM calibration_tasks
            WHERE status IN ('pending', 'retrying') AND next_attempt <= ?
        ''', (now,))
        stats['ready_to_process'] = cursor.fetchone()[0]

        return stats


def delete_calibration_task(task_id):
    """删除校准任务"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM calibration_tasks WHERE id = ?', (task_id,))
        return cursor.rowcount > 0


def delete_calibration_tasks_by_note_id(note_id):
    """删除指定笔记的所有校准任务（用于手动校准成功后清理）

    Args:
        note_id: 笔记ID

    Returns:
        int: 删除的任务数量
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM calibration_tasks WHERE note_id = ?', (note_id,))
        deleted_count = cursor.rowcount
        logger.info(f"清理了 {deleted_count} 个自动校准任务（note_id={note_id}）")
        return deleted_count


def clear_completed_calibration_tasks(days=7):
    """清理已完成的校准任务

    Args:
        days: 保留最近N天的记录
    """
    from datetime import datetime, timedelta

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cutoff_date = (datetime.now(CHINA_TZ) - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
            DELETE FROM calibration_tasks
            WHERE status = 'success'
            AND created_at < ?
        ''', (cutoff_date,))

        deleted = cursor.rowcount
        logger.info(f"清理了 {deleted} 条已完成的校准任务（{days}天前）")
        return deleted


def get_all_calibration_tasks(status=None, limit=100, offset=0):
    """获取所有校准任务（用于Web界面显示）

    Args:
        status: 过滤状态（可选）
        limit: 返回数量限制
        offset: 偏移量
    """
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = 'SELECT * FROM calibration_tasks WHERE 1=1'
        params = []

        if status:
            query += ' AND status = ?'
            params.append(status)

        query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def toggle_favorite(note_id):
    """切换笔记收藏状态"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE notes SET is_favorite = 1 - is_favorite WHERE id = ?', (note_id,))
        return cursor.rowcount > 0


# 初始化数据库（确保表和默认用户存在）
init_database()
