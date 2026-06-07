"""Queue creation helpers for automatic calibration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CalibrationQueueTaskContext:
    note_id: int
    dn_info: Dict
    first_delay: int
    index: int
    total_count: int


class CalibrationQueueMixin:
    def add_note_to_calibration_queue(self, note_id: int, force: bool = False) -> bool:
        try:
            logger.info(f"🔄 开始处理校准任务: note_id={note_id}, force={force}")
            note = self._get_note_by_id(note_id)
            if not note:
                logger.warning(f"⚠️ 笔记 {note_id} 不存在")
                return False

            self._log_note_found(note_id, note)
            if not self._should_add_note_to_queue(note, note_id, force):
                return False

            all_dns = self.extract_all_dns_from_note(note)
            if not all_dns:
                logger.warning(f"⚠️ 无法从笔记 {note_id} 提取磁力链接")
                return False

            return self._add_magnet_tasks(note_id, all_dns)
        except Exception as exc:
            logger.error(f"❌ 添加校准任务异常: note_id={note_id}, error={exc}", exc_info=True)
            return False

    @staticmethod
    def _log_note_found(note_id: int, note: Dict) -> None:
        has_magnet = "有" if note.get("magnet_link") else "无"
        logger.info(f"✅ 笔记已找到: note_id={note_id}, magnet_link={has_magnet}")

    def _should_add_note_to_queue(self, note: Dict, note_id: int, force: bool) -> bool:
        if not force and not self.should_calibrate_note(note):
            filter_mode = self.config.get("filter_mode")
            logger.info(f"⏭️ 笔记 {note_id} 不需要校准（filter_mode={filter_mode}）")
            return False
        if force:
            logger.info(f"✅ 强制模式：跳过校准检查，直接添加笔记 {note_id}")
            return True
        logger.info(f"✅ 笔记需要校准: note_id={note_id}")
        return True

    def _add_magnet_tasks(self, note_id: int, all_dns: List[Dict]) -> bool:
        logger.info(f"✅ 发现 {len(all_dns)} 个磁力链接，为每个磁力链接创建独立任务")
        first_delay = self.config.get("first_delay", 600)
        added_count = 0
        for idx, dn_info in enumerate(all_dns, 1):
            context = CalibrationQueueTaskContext(note_id, dn_info, first_delay, idx, len(all_dns))
            if self._add_single_magnet_task(context):
                added_count += 1
        return self._log_queue_result(note_id, added_count, len(all_dns))

    def _add_single_magnet_task(self, context: CalibrationQueueTaskContext) -> bool:
        magnet_hash = context.dn_info["info_hash"]
        task_id = self._add_calibration_task(context.note_id, magnet_hash, context.first_delay)
        if task_id:
            logger.info(
                f"✅ 第 {context.index}/{context.total_count} 个磁力链接任务已添加: "
                f"task_id={task_id}, hash={magnet_hash[:16]}..."
            )
            return True
        logger.warning(
            f"⚠️ 第 {context.index}/{context.total_count} 个磁力链接任务添加失败（可能已存在）: "
            f"hash={magnet_hash[:16]}..."
        )
        return False

    @staticmethod
    def _log_queue_result(note_id: int, added_count: int, total_count: int) -> bool:
        if added_count > 0:
            logger.info(f"🎉 校准任务添加完成: note_id={note_id}, 成功添加 {added_count}/{total_count} 个任务")
            return True
        logger.warning(f"⚠️ 没有添加任何新任务: note_id={note_id}")
        return False
