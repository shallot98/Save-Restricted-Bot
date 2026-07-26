#!/usr/bin/env python3
"""
同步文件名修复脚本
将磁力链接中有效的dn参数同步到filename字段
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
        True 如果是有效文件名
    """
    if not dn_value:
        return False

    # 去除首尾空格
    dn_value = dn_value.strip()

    # 如果是纯数字，认为不是有效文件名
    if dn_value.isdigit():
        return False

    # 如果有文件扩展名，认为是有效文件名
    if '.' in dn_value:
        return True

    # 如果长度太短（小于10）且没有扩展名，认为不是有效文件名
    if len(dn_value) < 10:
        return False

    return True


def extract_dn_from_magnet(magnet_link: str) -> str:
    """
    从磁力链接提取 dn 参数

    Args:
        magnet_link: 磁力链接

    Returns:
        dn 参数值
    """
    try:
        parsed = urlparse(magnet_link)
        params = parse_qs(parsed.query)
        dn_values = params.get('dn', [])

        if dn_values:
            return unquote(dn_values[0])

        return ""
    except Exception as e:
        logger.error(f"解析磁力链接失败: {e}")
        return ""


def get_notes_with_valid_dn() -> List[Tuple[int, str, str]]:
    """
    获取有有效dn但filename为空的笔记

    Returns:
        [(note_id, magnet_link, dn_value), ...]
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 查找所有有磁力链接但filename为空的笔记
    cursor.execute("""
        SELECT id, magnet_link
        FROM notes
        WHERE (filename IS NULL OR filename = '')
          AND magnet_link IS NOT NULL
        ORDER BY id
    """)

    results = []
    for note_id, magnet_link in cursor.fetchall():
        dn_value = extract_dn_from_magnet(magnet_link)

        if dn_value and is_valid_filename(dn_value):
            results.append((note_id, magnet_link, dn_value))

    conn.close()
    return results


def update_filename(note_id: int, filename: str) -> bool:
    """
    更新笔记的filename字段

    Args:
        note_id: 笔记ID
        filename: 文件名

    Returns:
        是否成功
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE notes
            SET filename = ?
            WHERE id = ?
        """, (filename, note_id))

        conn.commit()
        return True

    except Exception as e:
        logger.error(f"更新filename失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("开始同步filename字段...")
    logger.info("=" * 60)

    # 获取需要同步的笔记
    logger.info("🔍 扫描有有效dn但filename为空的笔记...")
    notes = get_notes_with_valid_dn()

    logger.info(f"📊 发现 {len(notes)} 个笔记需要同步filename")

    if not notes:
        logger.info("✅ 所有笔记的filename都已同步！")
        return

    # 显示前5个示例
    logger.info("\n示例笔记:")
    for i, (note_id, magnet_link, dn_value) in enumerate(notes[:5], 1):
        logger.info(f"  {i}. 笔记ID: {note_id}")
        logger.info(f"     文件名: {dn_value[:60]}...")

    if len(notes) > 5:
        logger.info(f"  ... 还有 {len(notes) - 5} 个笔记")

    # 确认是否继续
    print("\n⚠️  即将将dn参数同步到filename字段")
    confirm = input("是否继续？(yes/no): ").strip().lower()

    if confirm != 'yes':
        logger.info("❌ 用户取消操作")
        return

    # 批量更新
    logger.info("\n🔄 开始批量更新filename...")
    updated_count = 0
    failed_count = 0

    for i, (note_id, magnet_link, dn_value) in enumerate(notes, 1):
        if update_filename(note_id, dn_value):
            updated_count += 1
            if i % 50 == 0:
                logger.info(f"✅ [{i}/{len(notes)}] 已更新 {updated_count} 个笔记...")
        else:
            failed_count += 1

    # 统计结果
    logger.info("\n" + "=" * 60)
    logger.info("同步完成！")
    logger.info("=" * 60)
    logger.info(f"📊 总计处理: {len(notes)} 个笔记")
    logger.info(f"✅ 成功更新: {updated_count} 个")
    logger.info(f"❌ 失败: {failed_count} 个")

    # 验证结果
    logger.info("\n🔍 验证结果...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM notes
        WHERE (filename IS NULL OR filename = '')
          AND magnet_link IS NOT NULL
    """)
    remaining = cursor.fetchone()[0]

    logger.info(f"📊 剩余没有filename的笔记: {remaining} 个")
    logger.info("    （这些笔记的dn参数无效，需要通过校准获取文件名）")

    conn.close()


if __name__ == '__main__':
    main()
