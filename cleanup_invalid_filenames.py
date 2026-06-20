#!/usr/bin/env python3
"""
清理错误文件名并重新校准
"""
import sqlite3
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = 'data/notes.db'

# 受影响的笔记ID
AFFECTED_NOTE_IDS = [201, 730, 1044, 1257, 1258, 1265, 1266]


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("开始清理错误文件名并重新校准...")
    logger.info("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 显示受影响的笔记
        logger.info(f"\n📋 受影响的笔记: {len(AFFECTED_NOTE_IDS)} 个")
        for note_id in AFFECTED_NOTE_IDS:
            cursor.execute("SELECT filename FROM notes WHERE id = ?", (note_id,))
            row = cursor.fetchone()
            if row:
                logger.info(f"  笔记 {note_id}: {row[0][:60]}...")

        # 确认
        print("\n⚠️  即将执行以下操作:")
        print("  1. 清空这些笔记的 filename 字段")
        print("  2. 重置校准任务状态为 pending")
        print("  3. 设置重新校准时间为10分钟后")
        confirm = input("\n是否继续？(yes/no): ").strip().lower()

        if confirm != 'yes':
            logger.info("❌ 用户取消操作")
            return

        # 清空文件名
        logger.info("\n🔄 步骤1: 清空错误的文件名...")
        for note_id in AFFECTED_NOTE_IDS:
            cursor.execute(
                "UPDATE notes SET filename = NULL WHERE id = ?",
                (note_id,)
            )
        logger.info(f"✅ 已清空 {len(AFFECTED_NOTE_IDS)} 个笔记的文件名")

        # 重置校准任务
        logger.info("\n🔄 步骤2: 重置校准任务...")
        reset_count = 0
        for note_id in AFFECTED_NOTE_IDS:
            cursor.execute("""
                UPDATE calibration_tasks
                SET status = 'pending',
                    retry_count = 0,
                    error_message = '重新校准（之前的文件名格式错误）',
                    next_attempt = datetime('now', '+10 minutes')
                WHERE note_id = ?
            """, (note_id,))

            if cursor.rowcount > 0:
                reset_count += 1

        logger.info(f"✅ 已重置 {reset_count} 个校准任务")

        # 提交更改
        conn.commit()

        # 验证结果
        logger.info("\n🔍 验证结果...")
        cursor.execute("""
            SELECT COUNT(*) FROM notes
            WHERE id IN ({})
              AND (filename IS NULL OR filename = '')
        """.format(','.join('?' * len(AFFECTED_NOTE_IDS))), AFFECTED_NOTE_IDS)

        null_count = cursor.fetchone()[0]
        logger.info(f"  文件名已清空: {null_count}/{len(AFFECTED_NOTE_IDS)}")

        cursor.execute("""
            SELECT COUNT(*) FROM calibration_tasks
            WHERE note_id IN ({})
              AND status = 'pending'
        """.format(','.join('?' * len(AFFECTED_NOTE_IDS))), AFFECTED_NOTE_IDS)

        pending_count = cursor.fetchone()[0]
        logger.info(f"  校准任务已重置: {pending_count}/{len(AFFECTED_NOTE_IDS)}")

        # 总结
        logger.info("\n" + "=" * 60)
        logger.info("清理完成！")
        logger.info("=" * 60)
        logger.info(f"📊 处理结果:")
        logger.info(f"  - 清空文件名: {null_count} 个")
        logger.info(f"  - 重置校准任务: {pending_count} 个")
        logger.info(f"\n⏰ 这些笔记将在10分钟后重新校准")
        logger.info(f"   （使用修复后的解析脚本，会正确处理空文件名）")

    except Exception as e:
        logger.error(f"❌ 操作失败: {e}", exc_info=True)
        conn.rollback()
    finally:
        conn.close()


if __name__ == '__main__':
    main()
