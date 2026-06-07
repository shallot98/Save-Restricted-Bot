"""Calibration task processing helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional
from urllib.parse import parse_qs, unquote, urlparse

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CalibrationTaskContext:
    task_id: int
    note_id: int
    magnet_hash: str
    retry_count: int


@dataclass(frozen=True)
class SuccessfulCalibrationContext:
    task: CalibrationTaskContext
    note: Dict
    target_magnet: Dict
    filename: str


class CalibrationTaskProcessorMixin:
    def process_calibration_task(self, task: Dict) -> bool:
        context = CalibrationTaskContext(
            task["id"],
            task["note_id"],
            task["magnet_hash"],
            task["retry_count"],
        )
        self._log_task_start(context)
        try:
            note = self._load_task_note(context)
            if not note:
                return False
            target_magnet = self._find_task_magnet(context, note)
            if not target_magnet:
                return False
            if self._target_already_calibrated(context, target_magnet):
                return True
            return self._calibrate_and_update_note(context, note, target_magnet)
        except Exception as exc:
            logger.error(f"处理校准任务时出错: {exc}", exc_info=True)
            self._update_calibration_task(context.task_id, "failed", str(exc))
            return False

    @staticmethod
    def _log_task_start(context: CalibrationTaskContext) -> None:
        logger.info(
            "🔧 开始处理校准任务: task_id=%s, note_id=%s, hash=%s..., retry=%s",
            context.task_id,
            context.note_id,
            context.magnet_hash[:16],
            context.retry_count,
        )

    def _load_task_note(self, context: CalibrationTaskContext) -> Optional[Dict]:
        note = self._get_note_by_id(context.note_id)
        if note:
            return note
        logger.warning(f"笔记 {context.note_id} 不存在，删除任务")
        self._update_calibration_task(context.task_id, "failed", "笔记不存在")
        return None

    def _find_task_magnet(self, context: CalibrationTaskContext, note: Dict) -> Optional[Dict]:
        all_dns = self.extract_all_dns_from_note(note)
        if not all_dns:
            logger.warning(f"⚠️ 笔记 {context.note_id} 没有找到磁力链接")
            self._update_calibration_task(context.task_id, "failed", "没有找到磁力链接")
            return None

        for dn_info in all_dns:
            if dn_info["info_hash"] == context.magnet_hash:
                return dn_info
        logger.warning(f"⚠️ 笔记 {context.note_id} 中未找到 hash={context.magnet_hash[:16]}... 的磁力链接")
        self._update_calibration_task(context.task_id, "failed", "磁力链接不存在")
        return None

    def _target_already_calibrated(self, context, target_magnet: Dict) -> bool:
        if not target_magnet.get("dn"):
            return False
        if not self._has_calibrated_dn(target_magnet["magnet"]):
            return False
        logger.info(f"✅ 磁力链接 {context.magnet_hash[:16]}... 已经校准过，直接标记任务成功")
        self._update_calibration_task(context.task_id, "success")
        return True

    @staticmethod
    def _has_calibrated_dn(magnet: str) -> bool:
        try:
            parsed = urlparse(magnet)
            params = parse_qs(parsed.query)
            dn_values = params.get("dn", [])
            if not dn_values:
                return False
            dn_decoded = unquote(dn_values[0])
            return len(dn_decoded) > 10 and not dn_decoded.isdigit()
        except Exception:
            return False

    def _calibrate_and_update_note(self, context, note: Dict, target_magnet: Dict) -> bool:
        logger.info(f"🔄 开始校准磁力链接: {context.magnet_hash[:16]}...")
        timeout = self.config.get("timeout_per_magnet", 30)
        filename = self.calibrate_magnet(context.magnet_hash, timeout, prefer_bot=True)
        if not filename:
            return self._schedule_retry_or_fail(context)
        return self._save_successful_calibration(
            SuccessfulCalibrationContext(context, note, target_magnet, filename)
        )

    def _save_successful_calibration(self, context: SuccessfulCalibrationContext) -> bool:
        logger.info(f"✅ 磁力链接校准成功: {context.filename[:50]}...")
        calibrated_results = [self._calibrated_result(context)]
        update_success = self._update_note_with_calibrated_dns(context.task.note_id, calibrated_results)
        if update_success:
            logger.info(
                f"✅ 笔记 {context.task.note_id} 更新成功"
                f"（磁力链接 {context.task.magnet_hash[:16]}... 已校准）"
            )
            self._invalidate_note_cache(context.task.note_id, context.note)
            self._update_calibration_task(context.task.task_id, "success")
            return True
        logger.error(f"❌ 更新笔记 {context.task.note_id} 失败")
        self._update_calibration_task(context.task.task_id, "failed", "更新笔记失败")
        return False

    @staticmethod
    def _calibrated_result(context: SuccessfulCalibrationContext) -> Dict:
        return {
            "info_hash": context.task.magnet_hash,
            "old_magnet": context.target_magnet["magnet"],
            "filename": context.filename,
            "success": True,
        }

    def _invalidate_note_cache(self, note_id: int, note: Dict) -> None:
        try:
            from src.infrastructure.cache.managers import get_note_cache_manager

            cache_manager = get_note_cache_manager()
            user_id = note.get("user_id")
            if user_id:
                invalidated = cache_manager.invalidate_note(note_id, user_id)
                logger.info(f"✅ 已失效笔记 {note_id} 的用户缓存 ({invalidated} 个条目)")
            deleted = cache_manager._cache.delete_pattern(f"{cache_manager._key_prefix}:list:all:*")
            deleted += cache_manager._cache.delete_pattern(f"{cache_manager._key_prefix}:count:all:*")
            logger.info(f"✅ 已失效全局笔记列表缓存 ({deleted} 个条目)")
        except Exception as exc:
            logger.error(f"❌ 缓存失效失败: {exc}")
            import traceback

            traceback.print_exc()

    def _schedule_retry_or_fail(self, context: CalibrationTaskContext) -> bool:
        max_retries = self.config.get("max_retries", 3)
        if context.retry_count < max_retries:
            next_delay = self._next_retry_delay(context.retry_count)
            logger.info(f"⏰ 磁力链接校准失败，将在 {next_delay // 3600} 小时后重试")
            self._update_calibration_task(context.task_id, "retrying", "校准失败，等待重试", next_delay)
            return False

        logger.warning(f"❌ 磁力链接校准失败（已重试{max_retries}次）: hash={context.magnet_hash[:16]}...")
        self._update_calibration_task(context.task_id, "failed", f"校准失败（已重试{max_retries}次）")
        return False

    def _next_retry_delay(self, retry_count: int) -> int:
        retry_delays = [
            self.config.get("retry_delay_1", 3600),
            self.config.get("retry_delay_2", 14400),
            self.config.get("retry_delay_3", 28800),
        ]
        return retry_delays[min(retry_count, len(retry_delays) - 1)]

    def process_pending_tasks(self, max_concurrent: int = 5) -> None:
        if not self.is_enabled():
            logger.debug("自动校准未启用")
            return
        try:
            self._process_pending_task_batch(max_concurrent)
        except Exception as exc:
            logger.error(f"批量处理校准任务失败: {exc}", exc_info=True)

    def _process_pending_task_batch(self, max_concurrent: int) -> None:
        tasks = self._get_pending_calibration_tasks(limit=max_concurrent)
        if not tasks:
            logger.debug("没有待处理的校准任务")
            return

        logger.info(f"📋 发现 {len(tasks)} 个待处理的校准任务")
        success_count = 0
        for task in tasks:
            try:
                if self.process_calibration_task(task):
                    success_count += 1
            except Exception as exc:
                logger.error(f"处理任务 {task['id']} 时出错: {exc}", exc_info=True)
        logger.info(f"✅ 批量处理完成: 成功 {success_count}/{len(tasks)}")
