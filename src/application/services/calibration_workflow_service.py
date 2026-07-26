"""
Calibration Workflow Service
============================

Application orchestration for manual calibration and related web API flows.
"""

from __future__ import annotations

import logging
import subprocess
from typing import Optional, Tuple, Dict, Any, List

from src.core.utils.script_paths import resolve_runtime_script
from src.domain.magnet import extract_all_dns_from_note
from src.application.services.calibration_service import CalibrationService
from src.application.services.note_service import NoteService
from src.core.exceptions import ConfigurationError, NotFoundError
from src.core.interfaces import CalibrationScheduler, CalibrationSchedulerProvider

logger = logging.getLogger(__name__)


class CalibrationWorkflowService:
    """Encapsulate manual calibration orchestration for web routes."""

    def __init__(
        self,
        note_service: NoteService,
        calibration_service: CalibrationService,
        calibration_scheduler_provider: Optional[CalibrationSchedulerProvider] = None,
    ) -> None:
        self._note_service = note_service
        self._calibration_service = calibration_service
        self._calibration_scheduler_provider = calibration_scheduler_provider

    def calibrate_note(self, note_id: int) -> Tuple[Optional[dict], Optional[str], int]:
        try:
            note_dto = self._note_service.get_note(note_id)
        except NotFoundError:
            return None, '笔记不存在', 404

        note_payload = {
            'id': note_dto.id,
            'message_text': note_dto.message_text,
            'magnet_link': note_dto.magnet_link,
        }
        all_dns = extract_all_dns_from_note(note_payload)
        if not all_dns:
            return None, '没有找到磁力链接', 404

        calibrated_results = self._calibrate_magnets(all_dns)
        try:
            self._note_service.apply_calibrated_magnets(note_id, calibrated_results)
        except NotFoundError:
            return None, '笔记不存在', 404
        except Exception as exc:
            logger.error(f'更新笔记失败: {exc}')
            return None, '更新数据库失败', 500

        success_count = sum(1 for item in calibrated_results if item.get('success'))
        fail_count = len(calibrated_results) - success_count
        if success_count > 0:
            self._cleanup_calibration_tasks(note_id)

        return {
            'success': True,
            'total': len(calibrated_results),
            'success_count': success_count,
            'fail_count': fail_count,
            'results': calibrated_results,
        }, None, 200

    def calibrate_info_hash_filename(self, info_hash: str) -> Tuple[Optional[str], Optional[str]]:
        qbt_script = self._get_script_path('calibrate_qbt_helper.py')
        bot_script = self._get_script_path('calibrate_bot_helper.py')

        last_error = 'qBittorrent 脚本不存在'
        if qbt_script:
            filename, error = self._run_calibration_script(qbt_script, info_hash, timeout=30)
            if filename:
                return filename, None
            last_error = error or last_error

        if bot_script:
            filename, error = self._run_calibration_script(bot_script, info_hash, timeout=60)
            if filename:
                return filename, None
            last_error = error or last_error

        return None, last_error

    def batch_schedule_recent_notes(self, count: int, force: bool) -> Dict[str, Any]:
        manager = self._require_calibration_scheduler()
        notes = self._note_service.get_notes(page=1, page_size=count).items
        counts = {'added': 0, 'skipped': 0, 'error': 0}

        for note in notes:
            counts[self._schedule_recent_note(manager, note, force)] += 1

        mode_text = '强制重新校准' if force else '自动校准'
        return {
            'success': True,
            'total': len(notes),
            'added': counts['added'],
            'skipped': counts['skipped'],
            'errors': counts['error'],
            'force': force,
            'message': f"成功添加 {counts['added']} 条笔记到校准队列（{mode_text}模式）",
        }

    def _require_calibration_scheduler(self) -> CalibrationScheduler:
        """Fail loudly when the composition root did not wire a scheduler."""
        scheduler = (
            self._calibration_scheduler_provider()
            if self._calibration_scheduler_provider is not None
            else None
        )
        if scheduler is None:
            raise ConfigurationError(
                "校准调度器未装配，无法批量排队（组合根未完成 wiring）",
                config_key="calibration_scheduler",
            )
        return scheduler

    def _schedule_recent_note(self, manager: CalibrationScheduler, note, force: bool) -> str:
        try:
            note_dict = dict(vars(note))
            if not force and not manager.should_calibrate_note(note_dict):
                return 'skipped'
            if manager.add_note_to_calibration_queue(note.id, force=force):
                return 'added'
            return 'skipped'
        except Exception as exc:
            logger.error(f'添加笔记 {note.id} 到校准队列失败: {exc}')
            return 'error'

    def _calibrate_magnets(self, all_dns: List[dict]) -> List[dict]:
        results: List[dict] = []
        for dn_info in all_dns:
            info_hash = dn_info.get('info_hash')
            if not info_hash:
                continue
            results.append(self._calibrate_single_magnet(info_hash, dn_info.get('magnet') or ''))
        return results

    def _calibrate_single_magnet(self, info_hash: str, original_magnet: str) -> dict:
        qbt_script = self._get_script_path('calibrate_qbt_helper.py')
        bot_script = self._get_script_path('calibrate_bot_helper.py')
        filename = None
        error_msg = None

        if qbt_script:
            filename, error_msg = self._run_calibration_script(qbt_script, info_hash, timeout=30)
        if not filename and bot_script:
            filename, error_msg = self._run_calibration_script(bot_script, info_hash, timeout=60)

        if filename:
            return {
                'info_hash': info_hash,
                'old_magnet': original_magnet,
                'filename': filename,
                'success': True,
            }
        return {
            'info_hash': info_hash,
            'old_magnet': original_magnet,
            'error': error_msg or '所有校准方式都失败',
            'success': False,
        }

    def _cleanup_calibration_tasks(self, note_id: int) -> None:
        try:
            deleted = self._calibration_service.delete_tasks_for_note(note_id)
            if deleted > 0:
                logger.info(f'已清理 {deleted} 个自动校准任务（note_id={note_id}）')
        except Exception as exc:
            logger.warning(f'清理自动校准任务失败（不影响手动校准）: {exc}')

    @staticmethod
    def _get_script_path(script_name: str) -> Optional[str]:
        """Resolve a runtime script; missing files are logged by the resolver."""
        path = resolve_runtime_script(script_name)
        return str(path) if path else None

    @staticmethod
    def _run_calibration_script(
        script_path: str,
        info_hash: str,
        timeout: int,
    ) -> Tuple[Optional[str], Optional[str]]:
        try:
            result = subprocess.run(
                ['python3', script_path, info_hash],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip(), None
            return None, result.stderr.strip() if result.stderr else '未知错误'
        except subprocess.TimeoutExpired:
            return None, f'校准超时（{timeout}秒）'
        except Exception as exc:
            return None, f'执行失败: {exc}'
