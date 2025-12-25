"""
数据库安全访问层
提供参数化查询和 SQL 注入防护
"""
import sqlite3
import logging
from typing import List, Tuple, Any, Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class SecureDatabase:
    """安全的数据库访问类"""
    
    def __init__(self, db_path: str):
        """
        初始化数据库连接
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
    
    @contextmanager
    def get_connection(self):
        """
        获取数据库连接的上下文管理器
        
        Yields:
            sqlite3.Connection: 数据库连接对象
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row  # 返回字典式结果
            try:
                from src.infrastructure.monitoring.performance.db_tracer import get_db_tracer

                conn = get_db_tracer().enable(conn)
            except Exception as e:
                logger.debug("db_tracer 启用失败，已忽略: %s", e, exc_info=True)
            yield conn
            conn.commit()
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            logger.error(f"数据库错误: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def execute_query(self, query: str, params: Tuple = ()) -> List[sqlite3.Row]:
        """
        执行查询并返回结果
        
        Args:
            query: SQL 查询语句（使用 ? 占位符）
            params: 查询参数元组
            
        Returns:
            List[sqlite3.Row]: 查询结果列表
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()
    
    def execute_update(self, query: str, params: Tuple = ()) -> int:
        """
        执行更新操作
        
        Args:
            query: SQL 更新语句（使用 ? 占位符）
            params: 更新参数元组
            
        Returns:
            int: 受影响的行数
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.rowcount
    
    def execute_insert(self, query: str, params: Tuple = ()) -> int:
        """
        执行插入操作
        
        Args:
            query: SQL 插入语句（使用 ? 占位符）
            params: 插入参数元组
            
        Returns:
            int: 新插入行的 ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.lastrowid
    
    def execute_many(self, query: str, params_list: List[Tuple]) -> int:
        """
        批量执行操作
        
        Args:
            query: SQL 语句（使用 ? 占位符）
            params_list: 参数元组列表
            
        Returns:
            int: 受影响的总行数
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            return cursor.rowcount


# 安全查询示例
class NotesRepository:
    """笔记数据访问对象（DAO）"""
    
    def __init__(self, db: SecureDatabase):
        self.db = db
    
    def get_notes_by_user(self, user_id: int, limit: int = 50, offset: int = 0) -> List[sqlite3.Row]:
        """
        获取用户的笔记列表（安全的参数化查询）
        
        Args:
            user_id: 用户 ID
            limit: 返回数量限制
            offset: 偏移量
            
        Returns:
            List[sqlite3.Row]: 笔记列表
        """
        query = """
            SELECT * FROM notes 
            WHERE user_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ? OFFSET ?
        """
        return self.db.execute_query(query, (user_id, limit, offset))
    
    def search_notes(self, user_id: int, search_term: str, limit: int = 50) -> List[sqlite3.Row]:
        """
        搜索笔记（安全的 LIKE 查询）
        
        Args:
            user_id: 用户 ID
            search_term: 搜索关键词
            limit: 返回数量限制
            
        Returns:
            List[sqlite3.Row]: 匹配的笔记列表
        """
        query = """
            SELECT * FROM notes 
            WHERE user_id = ? AND message_text LIKE ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        """
        # 安全地处理 LIKE 查询
        search_pattern = f"%{search_term}%"
        return self.db.execute_query(query, (user_id, search_pattern, limit))
    
    def get_note_by_id(self, note_id: int, user_id: int) -> Optional[sqlite3.Row]:
        """
        根据 ID 获取笔记（带权限检查）
        
        Args:
            note_id: 笔记 ID
            user_id: 用户 ID
            
        Returns:
            Optional[sqlite3.Row]: 笔记对象或 None
        """
        query = "SELECT * FROM notes WHERE id = ? AND user_id = ?"
        results = self.db.execute_query(query, (note_id, user_id))
        return results[0] if results else None
    
    def update_note(self, note_id: int, user_id: int, message_text: str) -> bool:
        """
        更新笔记内容（带权限检查）
        
        Args:
            note_id: 笔记 ID
            user_id: 用户 ID
            message_text: 新的笔记内容
            
        Returns:
            bool: 是否更新成功
        """
        query = "UPDATE notes SET message_text = ? WHERE id = ? AND user_id = ?"
        rows_affected = self.db.execute_update(query, (message_text, note_id, user_id))
        return rows_affected > 0
    
    def delete_note(self, note_id: int, user_id: int) -> bool:
        """
        删除笔记（带权限检查）
        
        Args:
            note_id: 笔记 ID
            user_id: 用户 ID
            
        Returns:
            bool: 是否删除成功
        """
        query = "DELETE FROM notes WHERE id = ? AND user_id = ?"
        rows_affected = self.db.execute_update(query, (note_id, user_id))
        return rows_affected > 0
    
    def insert_note(self, user_id: int, source_chat_id: str, message_text: str, 
                   media_type: Optional[str] = None, media_path: Optional[str] = None) -> int:
        """
        插入新笔记
        
        Args:
            user_id: 用户 ID
            source_chat_id: 来源聊天 ID
            message_text: 笔记内容
            media_type: 媒体类型
            media_path: 媒体路径
            
        Returns:
            int: 新插入笔记的 ID
        """
        query = """
            INSERT INTO notes (user_id, source_chat_id, message_text, media_type, media_path)
            VALUES (?, ?, ?, ?, ?)
        """
        return self.db.execute_insert(query, (user_id, source_chat_id, message_text, media_type, media_path))
