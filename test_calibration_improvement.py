#!/usr/bin/env python3
"""
测试改进后的校准逻辑
验证：
1. 为多磁力链接笔记创建多个独立任务
2. 每个任务只处理对应的磁力链接
"""
import sys
import logging
from bot.services.calibration_manager import get_calibration_manager
from database import get_note_by_id, get_db_connection

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_calibration_improvement():
    """测试改进后的校准逻辑"""

    # 测试笔记ID
    test_note_id = 909

    logger.info("=" * 80)
    logger.info("开始测试改进后的校准逻辑")
    logger.info("=" * 80)

    # 1. 获取笔记信息
    logger.info(f"\n1️⃣ 获取笔记 {test_note_id} 的信息...")
    note = get_note_by_id(test_note_id)
    if not note:
        logger.error(f"笔记 {test_note_id} 不存在")
        return False

    logger.info(f"✅ 笔记已找到")
    logger.info(f"   message_text: {note.get('message_text', '')[:100]}...")

    # 2. 提取磁力链接
    logger.info(f"\n2️⃣ 提取笔记中的所有磁力链接...")
    manager = get_calibration_manager()
    all_dns = manager.extract_all_dns_from_note(note)

    logger.info(f"✅ 发现 {len(all_dns)} 个磁力链接:")
    for idx, dn_info in enumerate(all_dns, 1):
        logger.info(f"   {idx}. hash={dn_info['info_hash'][:16]}... magnet={dn_info['magnet'][:80]}...")

    # 3. 清理现有任务（测试用）
    logger.info(f"\n3️⃣ 清理笔记 {test_note_id} 的现有校准任务...")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM calibration_tasks WHERE note_id = ?", (test_note_id,))
        deleted_count = cursor.rowcount
        logger.info(f"✅ 已删除 {deleted_count} 个现有任务")

    # 4. 添加校准任务
    logger.info(f"\n4️⃣ 为笔记 {test_note_id} 添加校准任务...")
    success = manager.add_note_to_calibration_queue(test_note_id)

    if success:
        logger.info(f"✅ 校准任务添加成功")
    else:
        logger.error(f"❌ 校准任务添加失败")
        return False

    # 5. 查询创建的任务
    logger.info(f"\n5️⃣ 查询创建的校准任务...")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, note_id, magnet_hash, status, retry_count
            FROM calibration_tasks
            WHERE note_id = ?
            ORDER BY id
        """, (test_note_id,))
        tasks = cursor.fetchall()

    logger.info(f"✅ 找到 {len(tasks)} 个校准任务:")
    for task in tasks:
        task_dict = dict(task)
        logger.info(f"   task_id={task_dict['id']}, hash={task_dict['magnet_hash'][:16]}..., status={task_dict['status']}")

    # 6. 验证任务数量
    logger.info(f"\n6️⃣ 验证任务数量...")
    if len(tasks) == len(all_dns):
        logger.info(f"✅ 任务数量正确: {len(tasks)} 个任务对应 {len(all_dns)} 个磁力链接")
    else:
        logger.error(f"❌ 任务数量不匹配: {len(tasks)} 个任务 vs {len(all_dns)} 个磁力链接")
        return False

    # 7. 验证每个任务的hash
    logger.info(f"\n7️⃣ 验证每个任务的hash...")
    task_hashes = {dict(task)['magnet_hash'] for task in tasks}
    magnet_hashes = {dn_info['info_hash'] for dn_info in all_dns}

    if task_hashes == magnet_hashes:
        logger.info(f"✅ 所有磁力链接都有对应的任务")
    else:
        logger.error(f"❌ 任务hash不匹配")
        logger.error(f"   任务hash: {task_hashes}")
        logger.error(f"   磁力hash: {magnet_hashes}")
        return False

    logger.info("\n" + "=" * 80)
    logger.info("✅ 测试通过！改进后的校准逻辑工作正常")
    logger.info("=" * 80)

    return True


if __name__ == '__main__':
    try:
        success = test_calibration_improvement()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        sys.exit(1)
