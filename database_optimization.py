"""
数据库优化脚本
添加索引、优化查询性能
"""
import sqlite3
import os
import logging
from database import DATABASE_FILE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def add_indexes():
    """添加数据库索引以提升查询性能"""
    
    if not os.path.exists(DATABASE_FILE):
        logger.error(f"数据库文件不存在: {DATABASE_FILE}")
        return False
    
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        logger.info("=" * 60)
        logger.info("开始数据库优化...")
        logger.info("=" * 60)
        
        # 检查现有索引
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        existing_indexes = {row[0] for row in cursor.fetchall()}
        logger.info(f"现有索引: {existing_indexes}")
        
        # 定义需要创建的索引
        indexes = [
            ("idx_notes_timestamp", "CREATE INDEX IF NOT EXISTS idx_notes_timestamp ON notes(timestamp DESC)"),
            ("idx_notes_user_id", "CREATE INDEX IF NOT EXISTS idx_notes_user_id ON notes(user_id)"),
            ("idx_notes_source_chat_id", "CREATE INDEX IF NOT EXISTS idx_notes_source_chat_id ON notes(source_chat_id)"),
            ("idx_notes_media_group_id", "CREATE INDEX IF NOT EXISTS idx_notes_media_group_id ON notes(media_group_id)"),
            ("idx_notes_user_timestamp", "CREATE INDEX IF NOT EXISTS idx_notes_user_timestamp ON notes(user_id, timestamp DESC)"),
            ("idx_notes_source_timestamp", "CREATE INDEX IF NOT EXISTS idx_notes_source_timestamp ON notes(source_chat_id, timestamp DESC)"),
        ]
        
        # 创建索引
        created_count = 0
        for index_name, create_sql in indexes:
            if index_name not in existing_indexes:
                logger.info(f"创建索引: {index_name}")
                cursor.execute(create_sql)
                created_count += 1
            else:
                logger.info(f"索引已存在: {index_name}")
        
        # 全文搜索索引（如果需要）
        logger.info("\n检查全文搜索支持...")
        cursor.execute("PRAGMA compile_options")
        compile_options = [row[0] for row in cursor.fetchall()]
        
        if 'ENABLE_FTS5' in compile_options:
            logger.info("✅ SQLite 支持 FTS5 全文搜索")
            
            # 检查 FTS 表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notes_fts'")
            if not cursor.fetchone():
                logger.info("创建全文搜索表...")
                cursor.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
                        message_text,
                        content='notes',
                        content_rowid='id'
                    )
                """)
                
                # 填充 FTS 表
                logger.info("填充全文搜索索引...")
                cursor.execute("""
                    INSERT INTO notes_fts(rowid, message_text)
                    SELECT id, message_text FROM notes WHERE message_text IS NOT NULL
                """)
                logger.info("✅ 全文搜索表已创建")
            else:
                logger.info("全文搜索表已存在")
        else:
            logger.warning("⚠️ SQLite 不支持 FTS5，跳过全文搜索索引")
        
        # 提交事务
        conn.commit()

        # 执行 ANALYZE 统计
        logger.info("\n执行 ANALYZE 统计...")
        cursor.execute("ANALYZE")
        conn.commit()

        conn.close()

        # VACUUM 需要在事务外执行
        logger.info("\n执行 VACUUM 优化...")
        conn = sqlite3.connect(DATABASE_FILE)
        conn.execute("VACUUM")
        conn.close()
        
        logger.info("\n" + "=" * 60)
        logger.info(f"✅ 数据库优化完成！共创建 {created_count} 个新索引")
        logger.info("=" * 60)
        
        return True
        
    except sqlite3.Error as e:
        logger.error(f"❌ 数据库优化失败: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ 发生错误: {e}")
        return False


def analyze_query_performance():
    """分析查询性能"""
    
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        logger.info("\n" + "=" * 60)
        logger.info("查询性能分析")
        logger.info("=" * 60)
        
        # 测试查询
        test_queries = [
            ("按时间排序查询", "SELECT * FROM notes ORDER BY timestamp DESC LIMIT 50"),
            ("按用户查询", "SELECT * FROM notes WHERE user_id = 1 ORDER BY timestamp DESC LIMIT 50"),
            ("按来源查询", "SELECT * FROM notes WHERE source_chat_id = 'test' ORDER BY timestamp DESC LIMIT 50"),
        ]
        
        for query_name, query_sql in test_queries:
            cursor.execute(f"EXPLAIN QUERY PLAN {query_sql}")
            plan = cursor.fetchall()
            logger.info(f"\n{query_name}:")
            for row in plan:
                logger.info(f"  {row}")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"性能分析失败: {e}")


if __name__ == "__main__":
    print("\n🚀 开始数据库优化...\n")
    
    if add_indexes():
        print("\n📊 分析查询性能...\n")
        analyze_query_performance()
        print("\n✅ 优化完成！\n")
    else:
        print("\n❌ 优化失败！\n")
