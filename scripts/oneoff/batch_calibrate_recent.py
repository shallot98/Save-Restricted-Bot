#!/usr/bin/env python3
"""
批量校准最近的笔记

使用方法:
    python3 batch_calibrate_recent.py              # 校准最近100条笔记（仅未校准的）
    python3 batch_calibrate_recent.py --force      # 强制重新校准最近100条笔记（包括已校准的）
    python3 batch_calibrate_recent.py --count 50   # 校准最近50条笔记
"""

import sys
import os
import argparse

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(__file__))

from database import get_notes
from composition.calibration import get_calibration_manager
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def batch_calibrate(count=100, force=False):
    """批量校准笔记

    Args:
        count: 笔记数量
        force: 是否强制重新校准
    """
    logger.info("=" * 80)
    logger.info("批量校准工具")
    logger.info("=" * 80)
    logger.info(f"参数: count={count}, force={force}")

    # 获取最近的笔记
    logger.info(f"\n📋 正在获取最近 {count} 条笔记...")
    notes = get_notes(limit=count, offset=0)

    if not notes:
        logger.error("❌ 没有找到笔记")
        return

    logger.info(f"✅ 找到 {len(notes)} 条笔记")

    # 获取校准管理器
    calibration_manager = get_calibration_manager()

    if not calibration_manager.is_enabled():
        logger.warning("⚠️ 自动校准功能未启用")
        logger.info("💡 请在 Web 界面的「设置」->「校准设置」中启用自动校准")
        return

    # 批量添加到校准队列
    added_count = 0
    skipped_count = 0
    error_count = 0

    logger.info(f"\n🔄 开始处理笔记...")
    logger.info(f"模式: {'强制重新校准' if force else '仅校准未校准的笔记'}")
    logger.info("-" * 80)

    for idx, note in enumerate(notes, 1):
        note_id = note['id']
        try:
            # 如果强制模式，跳过校准检查
            should_add = force or calibration_manager.should_calibrate_note(note)

            if should_add:
                # 添加到校准队列（传递 force 参数）
                if calibration_manager.add_note_to_calibration_queue(note_id, force=force):
                    added_count += 1
                    mode_text = "（强制）" if force else ""
                    logger.info(f"[{idx}/{len(notes)}] ✅ 笔记 {note_id} 已添加到校准队列 {mode_text}")
                else:
                    skipped_count += 1
                    logger.info(f"[{idx}/{len(notes)}] ⏭️ 笔记 {note_id} 已在队列中，跳过")
            else:
                skipped_count += 1
                logger.info(f"[{idx}/{len(notes)}] ⏭️ 笔记 {note_id} 不需要校准，跳过")
        except Exception as e:
            logger.error(f"[{idx}/{len(notes)}] ❌ 笔记 {note_id} 处理失败: {e}")
            error_count += 1

    # 输出统计信息
    logger.info("-" * 80)
    logger.info("\n" + "=" * 80)
    logger.info("批量校准完成")
    logger.info("=" * 80)
    logger.info(f"总计: {len(notes)} 条笔记")
    logger.info(f"成功添加: {added_count} 条")
    logger.info(f"跳过: {skipped_count} 条")
    logger.info(f"错误: {error_count} 条")
    logger.info("=" * 80)

    if added_count > 0:
        logger.info("\n💡 提示:")
        logger.info("  - 校准任务已添加到队列，将在后台自动处理")
        logger.info("  - 可以在 Web 界面的「设置」->「校准设置」中查看进度")
        logger.info("  - 首次校准会在10分钟后开始，后续任务会根据配置的延迟时间执行")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='批量校准最近的笔记',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                    # 校准最近100条笔记（仅未校准的）
  %(prog)s --force            # 强制重新校准最近100条笔记（包括已校准的）
  %(prog)s --count 50         # 校准最近50条笔记
  %(prog)s --count 200 --force  # 强制重新校准最近200条笔记
        """
    )

    parser.add_argument(
        '--count',
        type=int,
        default=100,
        help='笔记数量（默认: 100，最大: 1000）'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='强制重新校准（包括已校准的笔记）'
    )

    args = parser.parse_args()

    # 验证参数
    if args.count <= 0 or args.count > 1000:
        logger.error("❌ 数量必须在 1-1000 之间")
        sys.exit(1)

    # 执行批量校准
    try:
        batch_calibrate(count=args.count, force=args.force)
    except KeyboardInterrupt:
        logger.info("\n\n⚠️ 用户中断操作")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ 批量校准失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
