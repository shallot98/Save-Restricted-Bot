"""
API 端点路由模块

遵循 SRP 原则：仅负责 JSON API 端点

Architecture: Uses new layered architecture
- 服务经 web.services.get_services() 从当前应用取（应用工厂注入）
- src/application/services for business logic

异步校准的任务函数跑在 ``AsyncCalibrationManager`` 的线程池里，那里**没有** Flask
应用上下文。因此 ``CalibrationWorkflowService`` 一律在请求内取好、作为参数传进
任务函数，不在后台线程里调 ``get_services()``。
"""
import logging
from typing import TYPE_CHECKING, Optional, Tuple

from flask import Blueprint, request, jsonify

# New architecture imports
from src.core.exceptions import NotFoundError, ValidationError

from bot.services.async_calibration_manager import get_async_calibration_manager, TaskStatus
from web.auth import api_login_required
from web.services import get_services

if TYPE_CHECKING:
    from src.application.services import CalibrationWorkflowService

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)


@api_bp.route('/calibration/task/<int:task_id>/retry', methods=['POST'])
@api_login_required
def retry_calibration_task(task_id: int):
    """手动重试校准任务

    Uses CalibrationService for task management.

    Args:
        task_id: 任务 ID

    Returns:
        JSON 响应
    """
    calibration_service = get_services().calibration_service

    try:
        # 使用新架构的 schedule_retry 方法
        success = calibration_service.schedule_retry(task_id)

        if success:
            return jsonify({'success': True, 'message': '任务已加入重试队列'})
        else:
            return jsonify({'success': False, 'error': '重试失败'}), 500
    except NotFoundError:
        return jsonify({'success': False, 'error': '任务不存在'}), 404
    except Exception as e:
        logger.exception(f"重试校准任务失败: {e}")
        return jsonify({'success': False, 'error': '重试失败'}), 500


@api_bp.route('/calibration/task/<int:task_id>/delete', methods=['POST'])
@api_login_required
def delete_calibration_task_api(task_id: int):
    """删除校准任务

    Uses CalibrationService for task management.

    Args:
        task_id: 任务 ID

    Returns:
        JSON 响应
    """
    calibration_service = get_services().calibration_service

    try:
        success = calibration_service.delete_task(task_id)

        if success:
            return jsonify({'success': True, 'message': '任务已删除'})
        else:
            return jsonify({'success': False, 'error': '任务不存在'}), 404
    except Exception as e:
        logger.exception(f"删除校准任务失败: {e}")
        return jsonify({'success': False, 'error': '删除失败'}), 500


@api_bp.route('/edit_note/<int:note_id>', methods=['POST'])
@api_login_required
def edit_note(note_id: int):
    """编辑笔记内容

    Args:
        note_id: 笔记 ID

    Returns:
        JSON 响应
    """
    note_service = get_services().note_service

    try:
        data = request.get_json(silent=True) or {}
        raw_text = data.get('message_text')
        if raw_text is None:
            raw_text = ""
        if not isinstance(raw_text, str):
            raise ValidationError("message_text 必须是字符串")
        new_text = raw_text.strip()
        note_service.update_text(note_id, new_text)
        return jsonify({'success': True})
    except ValidationError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except NotFoundError:
        return jsonify({'success': False, 'error': '笔记不存在'}), 404
    except Exception as e:
        logger.exception(f"编辑笔记失败: {e}")
        return jsonify({'success': False, 'error': '服务器错误'}), 500


@api_bp.route('/calibrate/<int:note_id>', methods=['POST'])
@api_login_required
def calibrate(note_id: int):
    """校准磁力链接的 dn 参数

    支持多个磁力链接的批量校准

    Uses NoteService and CalibrationService.

    Args:
        note_id: 笔记 ID

    Returns:
        JSON 响应
    """
    try:
        payload, error, status_code = _calibrate_note_and_update(
            note_id, get_services().calibration_workflow_service
        )
        if error:
            return jsonify({'success': False, 'error': error}), status_code
        return jsonify(payload), 200

    except Exception as e:
        logger.exception(f"校准API异常: {e}")
        return jsonify({'success': False, 'error': '服务器错误'}), 500


@api_bp.route('/calibrate/async', methods=['POST'])
@api_login_required
def calibrate_async():
    """异步校准接口：提交任务，立即返回 task_id

    请求体（JSON）：
    - { "note_id": 123 }  # 推荐：异步校准并更新该笔记
    - { "info_hash": "ABC..." }  # 兼容方案：只校准单个 info_hash，返回 filename
    """
    data = request.get_json() or {}
    note_id = data.get('note_id')
    info_hash = data.get('info_hash')

    if note_id is None and not info_hash:
        return jsonify({'success': False, 'error': '缺少 note_id 或 info_hash 参数'}), 400

    manager = get_async_calibration_manager()
    # 请求上下文内取服务；后台线程里没有 app context，取不到。
    workflow_service = get_services().calibration_workflow_service

    if note_id is not None:
        try:
            note_id_int = int(note_id)
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': 'note_id 必须是整数'}), 400

        task_id = manager.submit_task(
            info_hash=f"note:{note_id_int}",
            calibration_func=_async_calibrate_note_job,
            note_id=note_id_int,
            workflow_service=workflow_service,
        )
    else:
        if not isinstance(info_hash, str) or not info_hash.strip():
            return jsonify({'success': False, 'error': 'info_hash 必须是非空字符串'}), 400

        # 注意：这里必须直接展开关键字参数。原写法 `kwargs={'info_hash': ...}`
        # 会被 submit_task(**kwargs) 再包一层，任务函数收到的是 kwargs=<dict>，
        # 必然 TypeError（任务显示 FAILED）。
        task_id = manager.submit_task(
            info_hash=info_hash.strip(),
            calibration_func=_async_calibrate_info_hash_job,
            info_hash_value=info_hash.strip(),
            workflow_service=workflow_service,
        )

    return jsonify({'success': True, 'task_id': task_id, 'status': TaskStatus.PENDING.value}), 200


@api_bp.route('/calibrate/status/<task_id>', methods=['GET'])
@api_login_required
def calibrate_status(task_id: str):
    """查询异步校准任务状态（轮询用）"""
    manager = get_async_calibration_manager()
    task = manager.get_task_status(task_id)
    if not task:
        return jsonify({'success': False, 'error': '任务不存在或已过期'}), 404

    response = {
        'success': True,
        'task_id': task.task_id,
        'status': task.status.value,
        'info_hash': task.info_hash,
        'created_at': task.created_at,
        'completed_at': task.completed_at,
    }

    if task.status == TaskStatus.COMPLETED:
        response['result'] = task.result
    elif task.status == TaskStatus.FAILED:
        response['error'] = task.error

    return jsonify(response), 200


@api_bp.route('/download/<int:note_id>', methods=['POST'])
@api_login_required
def download_note(note_id: int):
    """将笔记中的磁力链接添加到 qBittorrent 下载队列"""
    services = get_services()
    note_service = services.note_service
    qbittorrent_service = services.qbittorrent_service
    data = request.get_json(silent=True) or {}

    try:
        note_dto = note_service.get_note(note_id)
    except NotFoundError:
        return jsonify({'success': False, 'error': '笔记不存在'}), 404

    try:
        payload, status_code = qbittorrent_service.add_note_download(
            note_dto,
            data.get('magnet_index'),
        )
        return jsonify(payload), status_code
    except Exception as e:
        logger.exception(f"添加下载任务失败: {e}")
        return jsonify({'success': False, 'error': '服务器错误'}), 500


@api_bp.route('/download/status/<info_hash>', methods=['GET'])
@api_login_required
def download_status(info_hash: str):
    """查询 qBittorrent 下载进度（轮询用）"""
    try:
        payload, status_code = get_services().qbittorrent_service.get_download_status(info_hash)
        return jsonify(payload), status_code
    except Exception as e:
        logger.exception(f"查询下载状态失败: {e}")
        return jsonify({'success': False, 'error': '服务器错误'}), 500


def _async_calibrate_note_job(
    note_id: int,
    workflow_service: "CalibrationWorkflowService",
) -> Tuple[Optional[dict], Optional[str]]:
    """后台线程中执行：校准并更新笔记（返回 (result, error)）"""
    payload, error, _status = _calibrate_note_and_update(note_id, workflow_service)
    if error:
        return None, error
    return payload, None


def _async_calibrate_info_hash_job(
    info_hash_value: str,
    workflow_service: "CalibrationWorkflowService",
) -> Tuple[Optional[str], Optional[str]]:
    """后台线程中执行：仅校准 info_hash（返回 (filename, error)）"""
    filename, error = _calibrate_info_hash_filename(info_hash_value, workflow_service)
    if filename:
        return filename, None
    return None, error or '所有校准方式都失败'


def _calibrate_note_and_update(
    note_id: int,
    workflow_service: "CalibrationWorkflowService",
) -> Tuple[Optional[dict], Optional[str], int]:
    """复用同步校准逻辑：校准并更新数据库。"""
    return workflow_service.calibrate_note(note_id)


def _calibrate_info_hash_filename(
    info_hash: str,
    workflow_service: "CalibrationWorkflowService",
) -> Tuple[Optional[str], Optional[str]]:
    """获取 info_hash 对应的 filename（优先 qBittorrent，失败回退机器人）。"""
    return workflow_service.calibrate_info_hash_filename(info_hash)


@api_bp.route('/calibrate/batch', methods=['POST'])
@api_login_required
def batch_calibrate():
    """批量添加笔记到校准队列。"""
    try:
        data = request.get_json() or {}
        count = data.get('count', 100)
        force = data.get('force', False)

        # bool 是 int 的子类：`{"count": true}` 会被 isinstance(count, int) 放行，
        # 变成静默的 count=1 批量校准。显式拒绝。
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0 or count > 1000:
            return jsonify({'success': False, 'error': '数量必须在1-1000之间'}), 400

        payload = get_services().calibration_workflow_service.batch_schedule_recent_notes(
            count, force
        )
        if payload.get('total', 0) == 0:
            return jsonify({'success': False, 'error': '没有找到笔记'}), 404
        return jsonify(payload)
    except Exception as e:
        logger.exception(f"批量校准API异常: {e}")
        return jsonify({'success': False, 'error': '服务器错误'}), 500
