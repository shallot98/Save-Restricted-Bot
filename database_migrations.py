"""
数据库迁移脚本
添加索引和优化查询性能
"""
import sqlite3
import logging
from database import DATABASE_FILE

logger = logging.getLogger(__name__)


def create_indexes():
    """创建数据库索引以提升查询性能"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    indexes = [
        # ==================== notes 表索引 ====================
        # 1. 单列索引 - 基础过滤
        ("idx_notes_user_id", "CREATE INDEX IF NOT EXISTS idx_notes_user_id ON notes(user_id)"),
        ("idx_notes_source_chat_id", "CREATE INDEX IF NOT EXISTS idx_notes_source_chat_id ON notes(source_chat_id)"),
        ("idx_notes_timestamp", "CREATE INDEX IF NOT EXISTS idx_notes_timestamp ON notes(timestamp DESC)"),

        # 2. 复合索引 - 最常用查询模式（用户+来源+时间排序）
        ("idx_notes_user_source_time", "CREATE INDEX IF NOT EXISTS idx_notes_user_source_time ON notes(user_id, source_chat_id, timestamp DESC)"),

        # 3. 部分索引 - 媒体组去重（仅索引非空值）
        ("idx_notes_media_group_dedup", "CREATE INDEX IF NOT EXISTS idx_notes_media_group_dedup ON notes(user_id, source_chat_id, media_group_id) WHERE media_group_id IS NOT NULL"),

        # 4. 部分索引 - 收藏过滤（仅索引收藏项）
        ("idx_notes_favorite", "CREATE INDEX IF NOT EXISTS idx_notes_favorite ON notes(user_id, is_favorite) WHERE is_favorite = 1"),

        # 5. 部分索引 - 磁力链接（仅索引非空值）
        ("idx_notes_magnet_link", "CREATE INDEX IF NOT EXISTS idx_notes_magnet_link ON notes(magnet_link) WHERE magnet_link IS NOT NULL"),

        # 6. 覆盖索引 - 搜索优化
        ("idx_notes_search", "CREATE INDEX IF NOT EXISTS idx_notes_search ON notes(user_id, source_chat_id, message_text)"),

        # ==================== calibration_tasks 表索引 ====================
        ("idx_calibration_status", "CREATE INDEX IF NOT EXISTS idx_calibration_status ON calibration_tasks(status, next_attempt)"),
        ("idx_calibration_note", "CREATE INDEX IF NOT EXISTS idx_calibration_note ON calibration_tasks(note_id)"),
        ("idx_calibration_created", "CREATE INDEX IF NOT EXISTS idx_calibration_created ON calibration_tasks(created_at DESC)"),
    ]

    created_count = 0
    for index_name, sql in indexes:
        try:
            cursor.execute(sql)
            logger.info(f"✅ 索引已创建/确认: {index_name}")
            created_count += 1
        except sqlite3.Error as e:
            logger.error(f"❌ 创建索引失败 {index_name}: {e}")

    conn.commit()
    conn.close()

    logger.info(f"📊 索引创建完成: {created_count}/{len(indexes)}")
    return created_count


def analyze_database():
    """分析数据库以优化查询计划"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    try:
        cursor.execute("ANALYZE")
        conn.commit()
        logger.info("✅ 数据库分析完成")
    except sqlite3.Error as e:
        logger.error(f"❌ 数据库分析失败: {e}")
    finally:
        conn.close()


def vacuum_database():
    """清理数据库碎片，优化存储"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    try:
        cursor.execute("VACUUM")
        logger.info("✅ 数据库清理完成")
    except sqlite3.Error as e:
        logger.error(f"❌ 数据库清理失败: {e}")
    finally:
        conn.close()


def get_database_stats():
    """获取数据库统计信息"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    stats = {}

    try:
        # 表记录数
        cursor.execute("SELECT COUNT(*) FROM notes")
        stats['notes_count'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM calibration_tasks")
        stats['calibration_tasks_count'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users")
        stats['users_count'] = cursor.fetchone()[0]

        # 数据库大小
        cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
        stats['database_size_mb'] = round(cursor.fetchone()[0] / (1024 * 1024), 2)

        # 索引列表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'")
        stats['indexes'] = [row[0] for row in cursor.fetchall()]

        logger.info("📊 数据库统计信息:")
        logger.info(f"   - 笔记数量: {stats['notes_count']}")
        logger.info(f"   - 校准任务数量: {stats['calibration_tasks_count']}")
        logger.info(f"   - 用户数量: {stats['users_count']}")
        logger.info(f"   - 数据库大小: {stats['database_size_mb']} MB")
        logger.info(f"   - 索引数量: {len(stats['indexes'])}")

    except sqlite3.Error as e:
        logger.error(f"❌ 获取统计信息失败: {e}")
    finally:
        conn.close()

    return stats


def optimize_database():
    """执行完整的数据库优化"""
    logger.info("🔧 开始数据库优化...")

    # 1. 创建索引
    create_indexes()

    # 2. 分析数据库
    analyze_database()

    # 3. 获取统计信息
    stats = get_database_stats()

    # 4. 如果数据库较大，执行VACUUM
    if stats.get('database_size_mb', 0) > 100:
        logger.info("💾 数据库较大，执行清理...")
        vacuum_database()

    logger.info("✅ 数据库优化完成！")
    return stats


def explain_query(query: str, params: tuple = ()) -> list:
    """分析查询执行计划

    Args:
        query: SQL 查询语句
        params: 查询参数

    Returns:
        执行计划列表
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    try:
        cursor.execute(f"EXPLAIN QUERY PLAN {query}", params)
        plan = cursor.fetchall()
        logger.info(f"📋 查询执行计划:")
        for row in plan:
            logger.info(f"   {row}")
        return plan
    except sqlite3.Error as e:
        logger.error(f"❌ 分析查询失败: {e}")
        return []
    finally:
        conn.close()


def check_index_usage() -> dict:
    """检查索引使用情况

    Returns:
        索引使用统计
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    result = {
        'indexes': [],
        'unused_indexes': [],
        'missing_indexes': []
    }

    try:
        # 获取所有索引
        cursor.execute("""
            SELECT name, tbl_name, sql
            FROM sqlite_master
            WHERE type='index' AND name NOT LIKE 'sqlite_%'
        """)
        result['indexes'] = [
            {'name': row[0], 'table': row[1], 'sql': row[2]}
            for row in cursor.fetchall()
        ]

        logger.info(f"📊 数据库索引统计:")
        logger.info(f"   - 总索引数: {len(result['indexes'])}")
        for idx in result['indexes']:
            logger.info(f"   - {idx['name']} ({idx['table']})")

    except sqlite3.Error as e:
        logger.error(f"❌ 检查索引失败: {e}")
    finally:
        conn.close()

    return result


def benchmark_queries() -> dict:
    """基准测试常用查询

    Returns:
        查询性能统计
    """
    import time

    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    benchmarks = {}

    test_queries = [
        ("get_notes_by_user", "SELECT * FROM notes WHERE user_id = 1 ORDER BY timestamp DESC LIMIT 50"),
        ("get_notes_by_source", "SELECT * FROM notes WHERE user_id = 1 AND source_chat_id = '-1001234567890' ORDER BY timestamp DESC LIMIT 50"),
        ("get_notes_count", "SELECT COUNT(*) FROM notes WHERE user_id = 1"),
        ("get_favorites", "SELECT * FROM notes WHERE user_id = 1 AND is_favorite = 1 ORDER BY timestamp DESC LIMIT 50"),
        ("search_notes", "SELECT * FROM notes WHERE user_id = 1 AND message_text LIKE '%test%' ORDER BY timestamp DESC LIMIT 50"),
        ("get_pending_calibration", "SELECT * FROM calibration_tasks WHERE status IN ('pending', 'retrying') ORDER BY next_attempt ASC LIMIT 100"),
    ]

    logger.info("⏱️ 开始查询基准测试...")

    for name, query in test_queries:
        try:
            start = time.perf_counter()
            cursor.execute(query)
            cursor.fetchall()
            elapsed = (time.perf_counter() - start) * 1000  # ms

            benchmarks[name] = {
                'time_ms': round(elapsed, 2),
                'status': 'fast' if elapsed < 10 else 'slow' if elapsed > 100 else 'normal'
            }
            logger.info(f"   - {name}: {elapsed:.2f}ms [{benchmarks[name]['status']}]")
        except sqlite3.Error as e:
            benchmarks[name] = {'error': str(e)}
            logger.error(f"   - {name}: 错误 - {e}")

    conn.close()
    return benchmarks


if __name__ == '__main__':
    import sys

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # 解析命令行参数
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == 'optimize':
            optimize_database()
        elif command == 'indexes':
            create_indexes()
        elif command == 'analyze':
            analyze_database()
        elif command == 'vacuum':
            vacuum_database()
        elif command == 'stats':
            get_database_stats()
        elif command == 'benchmark':
            benchmark_queries()
        elif command == 'check':
            check_index_usage()
        else:
            print(f"未知命令: {command}")
            print("可用命令: optimize, indexes, analyze, vacuum, stats, benchmark, check")
    else:
        # 默认执行完整优化
        optimize_database()
