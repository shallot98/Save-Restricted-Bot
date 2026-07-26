#!/usr/bin/env python3
"""
修复缺失校准任务的脚本
批量为没有文件名但有磁力链接的笔记添加校准任务
"""
import sqlite3
import logging
from urllib.parse import parse_qs, urlparse, unquote
from typing import List, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = 'data/notes.db'


def is_valid_filename(dn_value: str) -> bool:
    """
    判断 dn 参数是否是有效的文件名

    Args:
        dn_value: dn 参数值

    Returns:
        True 如果是有效文件名（不是简单数字或太短）
    """
    if not dn_value:
        return False

    # 去除首尾空格
    dn_value = dn_value.strip()

    # 如果是纯数字，认为不是有效文件名（无论长度）
    if dn_value.isdigit():
        return False

    # 如果有文件扩展名，认为是有效文件名
    if '.' in dn_value:
        return True

    # 如果长度太短（小于10）且没有扩展名，认为不是有效文件名
    if len(dn_value) < 10:
        return False

    return True


def extract_magnet_hash(magnet_link: str) -> str:
    """
    从磁力链接提取 info hash

    Args:
        magnet_link: 磁力链接

    Returns:
        info hash（大写）
    """
    try:
        parsed = urlparse(magnet_link)
        if parsed.scheme != 'magnet':
            return None

        params = parse_qs(parsed.query)
        xt_values = params.get('xt', [])

        for xt in xt_values:
            if xt.startswith('urn:btih:'):
                hash_value = xt.replace('urn:btih:', '').strip()
                return hash_value.upper()

        return None
    except Exception as e:
        logger.error(f"解析磁力链接失败: {e}")
        return None


def get_notes_need_calibration() -> List[Tuple[int, str, str]]:
    """
    获取需要校准的笔记列表

    Returns:
        [(note_id, magnet_link, dn_value), ...]
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 查找所有有磁力链接但没有文件名的笔记
    cursor.execute("""
        SELECT n.id, n.magnet_link
        FROM notes n
        LEFT JOIN calibration_tasks ct ON n.id = ct.note_id
        WHERE (n.filename IS NULL OR n.filename = '')
          AND n.magnet_link IS NOT NULL
          AND ct.id IS NULL
        ORDER BY n.id
    """)

    results = []
    for row in cursor.fetchall():
        note_id, magnet_link = row

        # 解析 dn 参数
        try:
            parsed = urlparse(magnet_link)
            params = parse_qs(parsed.query)
            dn_values = params.get('dn', [])
            dn_value = unquote(dn_values[0]) if dn_values else ""
        except Exception:
            dn_value = ""

        # 检查是否需要校准
        # 如果没有 dn 参数，或者 dn 参数不是有效文件名，需要校准
        if not dn_value or not is_valid_filename(dn_value):
            results.append((note_id, magnet_link, dn_value))

    conn.close()
    return results


def add_calibration_task(note_id: int, magnet_hash: str, delay: int = 600) -> bool:
    """
    添加校准任务

    Args:
        note_id: 笔记ID
        magnet_hash: 磁力链接hash
        delay: 首次执行延迟（秒）

    Returns:
        是否成功
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 检查是否已存在该任务
        cursor.execute("""
            SELECT id FROM calibration_tasks
            WHERE note_id = ? AND magnet_hash = ?
        """, (note_id, magnet_hash))

        if cursor.fetchone():
            logger.debug(f"任务已存在: note_id={note_id}, hash={magnet_hash[:16]}...")
            return False

        # 创建任务
        cursor.execute("""
            INSERT INTO calibration_tasks
            (note_id, magnet_hash, status, retry_count, next_attempt)
            VALUES (?, ?, 'pending', 0, datetime('now', '+' || ? || ' seconds'))
        """, (note_id, magnet_hash, delay))

        conn.commit()
        return True

    except Exception as e:
        logger.error(f"添加校准任务失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("开始修复缺失的校准任务...")
    logger.info("=" * 60)

    # 获取需要校准的笔记
    logger.info("🔍 扫描需要校准的笔记...")
    notes = get_notes_need_calibration()

    logger.info(f"📊 发现 {len(notes)} 个笔记需要添加校准任务")

    if not notes:
        logger.info("✅ 所有笔记都已有校准任务！")
        return

    # 显示前5个示例
    logger.info("\n示例笔记:")
    for i, (note_id, magnet_link, dn_value) in enumerate(notes[:5], 1):
        logger.info(f"  {i}. 笔记ID: {note_id}")
        logger.info(f"     磁力链接: {magnet_link[:60]}...")
        logger.info(f"     当前dn值: '{dn_value}'")

    if len(notes) > 5:
        logger.info(f"  ... 还有 {len(notes) - 5} 个笔记")

    # 确认是否继续
    print("\n⚠️  即将为这些笔记添加校准任务")
    confirm = input("是否继续？(yes/no): ").strip().lower()

    if confirm != 'yes':
        logger.info("❌ 用户取消操作")
        return

    # 批量添加校准任务
    logger.info("\n🔄 开始批量添加校准任务...")
    added_count = 0
    failed_count = 0

    for i, (note_id, magnet_link, dn_value) in enumerate(notes, 1):
        # 提取 hash
        magnet_hash = extract_magnet_hash(magnet_link)

        if not magnet_hash:
            logger.warning(f"⚠️  [{i}/{len(notes)}] 笔记 {note_id}: 无法提取hash")
            failed_count += 1
            continue

        # 添加任务
        if add_calibration_task(note_id, magnet_hash):
            added_count += 1
            if i % 50 == 0:
                logger.info(f"✅ [{i}/{len(notes)}] 已添加 {added_count} 个任务...")
        else:
            failed_count += 1

    # 统计结果
    logger.info("\n" + "=" * 60)
    logger.info("修复完成！")
    logger.info("=" * 60)
    logger.info(f"📊 总计处理: {len(notes)} 个笔记")
    logger.info(f"✅ 成功添加: {added_count} 个校准任务")
    logger.info(f"❌ 失败/跳过: {failed_count} 个")

    # 显示下一步操作
    logger.info("\n📝 下一步操作:")
    logger.info("  1. 确保校准服务正在运行")
    logger.info("  2. 校准任务将在10分钟后开始执行")
    logger.info("  3. 可以通过以下SQL查看任务状态:")
    logger.info("     SELECT status, COUNT(*) FROM calibration_tasks GROUP BY status;")


if __name__ == '__main__':
    main()
