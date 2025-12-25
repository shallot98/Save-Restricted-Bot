"""
API 端点路由模块

遵循 SRP 原则：仅负责 JSON API 端点

Architecture: Uses new layered architecture
- src/core/container for service access
- src/application/services for business logic
"""
import os
import subprocess
import logging
from typing import Optional, Tuple
from flask import Blueprint, request, jsonify

# New architecture imports
from src.core.container import get_note_service, get_calibration_service
from src.core.exceptions import NotFoundError, ValidationError

# Legacy imports (for calibration scripts and magnet utils)
from database import (
    update_calibration_task,
    update_note_with_calibrated_dns, get_note_by_id
)
from bot.utils.magnet_utils import extract_all_dns_from_note
from bot.services.async_calibration_manager import get_async_calibration_manager, TaskStatus
from web.auth import api_login_required

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
    calibration_service = get_calibration_service()

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
        return jsonify({'success': False, 'error': str(e)}), 500


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
    calibration_service = get_calibration_service()

    try:
        success = calibration_service.delete_task(task_id)

        if success:
            return jsonify({'success': True, 'message': '任务已删除'})
        else:
            return jsonify({'success': False, 'error': '任务不存在'}), 404
    except Exception as e:
        logger.exception(f"删除校准任务失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/edit_note/<int:note_id>', methods=['POST'])
@api_login_required
def edit_note(note_id: int):
    """编辑笔记内容

    Args:
        note_id: 笔记 ID

    Returns:
        JSON 响应
    """
    note_service = get_note_service()

    try:
        data = request.get_json() or {}
        new_text = (data.get('message_text') or '').strip()
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
    note_service = get_note_service()
    calibration_service = get_calibration_service()

    try:
        payload, error, status_code = _calibrate_note_and_update(note_id)
        if error:
            return jsonify({'success': False, 'error': error}), status_code
        return jsonify(payload), 200

    except Exception as e:
        import traceback
        logger.error(f"校准API异常: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'服务器错误: {str(e)}'}), 500


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

    if note_id is not None:
        try:
            note_id_int = int(note_id)
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': 'note_id 必须是整数'}), 400

        task_id = manager.submit_task(
            info_hash=f"note:{note_id_int}",
            calibration_func=_async_calibrate_note_job,
            note_id=note_id_int,
        )
    else:
        if not isinstance(info_hash, str) or not info_hash.strip():
            return jsonify({'success': False, 'error': 'info_hash 必须是非空字符串'}), 400

        task_id = manager.submit_task(
            info_hash=info_hash.strip(),
            calibration_func=_async_calibrate_info_hash_job,
            kwargs={'info_hash': info_hash.strip()}
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


def _async_calibrate_note_job(note_id: int) -> Tuple[Optional[dict], Optional[str]]:
    """后台线程中执行：校准并更新笔记（返回 (result, error)）"""
    payload, error, _status = _calibrate_note_and_update(note_id)
    if error:
        return None, error
    return payload, None


def _async_calibrate_info_hash_job(info_hash: str) -> Tuple[Optional[str], Optional[str]]:
    """后台线程中执行：仅校准 info_hash（返回 (filename, error)）"""
    filename, error = _calibrate_info_hash_filename(info_hash)
    if filename:
        return filename, None
    return None, error or '所有校准方式都失败'


def _calibrate_note_and_update(note_id: int) -> Tuple[Optional[dict], Optional[str], int]:
    """复用同步校准逻辑：校准并更新数据库，返回 (payload, error, http_status)"""
    note_service = get_note_service()

    try:
        note_dto = note_service.get_note(note_id)
        note = {
            'id': note_dto.id,
            'message_text': note_dto.message_text,
            'magnet_link': note_dto.magnet_link,
        }
    except NotFoundError:
        return None, '笔记不存在', 404

    all_dns = extract_all_dns_from_note(note)
    if not all_dns:
        return None, '没有找到磁力链接', 404

    calibrated_results = _calibrate_magnets(all_dns)

    if not update_note_with_calibrated_dns(note_id, calibrated_results):
        return None, '更新数据库失败', 500

    success_count = sum(1 for r in calibrated_results if r.get('success'))
    fail_count = len(calibrated_results) - success_count

    updated_note = get_note_by_id(note_id) or {}
    logger.info(f"校准后笔记 {note_id}: message_text={(updated_note.get('message_text') or '')[:200]}")

    _invalidate_note_caches(note_id, updated_note)

    if success_count > 0:
        _cleanup_calibration_tasks(note_id)

    return {
        'success': True,
        'total': len(calibrated_results),
        'success_count': success_count,
        'fail_count': fail_count,
        'results': calibrated_results,
    }, None, 200


def _invalidate_note_caches(note_id: int, updated_note: dict) -> None:
    """使缓存失效，确保刷新页面后能看到更新后的数据（失败不影响主流程）。"""
    try:
        from src.infrastructure.cache.managers import get_note_cache_manager

        cache_manager = get_note_cache_manager()
        user_id = updated_note.get('user_id')

        if user_id:
            invalidated = cache_manager.invalidate_note(note_id, user_id)
            logger.info(f"✅ 已失效笔记 {note_id} 的用户缓存 ({invalidated} 个条目)")

        deleted = cache_manager._cache.delete_pattern(f"{cache_manager._key_prefix}:list:all:*")
        deleted += cache_manager._cache.delete_pattern(f"{cache_manager._key_prefix}:count:all:*")
        logger.info(f"✅ 已失效全局笔记列表缓存 ({deleted} 个条目)")

    except Exception as e:
        logger.error(f"❌ 缓存失效失败: {e}")


def _calibrate_info_hash_filename(info_hash: str) -> Tuple[Optional[str], Optional[str]]:
    """获取 info_hash 对应的 filename（优先 qBittorrent，失败回退机器人）"""
    qbt_script = _get_script_path('calibrate_qbt_helper.py')
    bot_script = _get_script_path('calibrate_bot_helper.py')

    if qbt_script:
        filename, error_msg = _run_calibration_script(qbt_script, info_hash, timeout=30)
        if filename:
            return filename, None
        last_error = error_msg
    else:
        last_error = 'qBittorrent 脚本不存在'

    if bot_script:
        filename, error_msg = _run_calibration_script(bot_script, info_hash, timeout=60)
        if filename:
            return filename, None
        last_error = error_msg or last_error

    return None, last_error


@api_bp.route('/calibrate/batch', methods=['POST'])
@api_login_required
def batch_calibrate():
    """批量添加笔记到校准队列

    从最近的笔记中选择指定数量添加到自动校准队列

    参数:
        count: 笔记数量，默认100，最大1000
        force: 是否强制重新校准（忽略已校准的笔记），默认False

    Returns:
        JSON 响应
    """
    from database import get_notes
    from bot.services.calibration_manager import get_calibration_manager

    try:
        # 获取请求参数
        data = request.get_json() or {}
        count = data.get('count', 100)  # 默认100条
        force = data.get('force', False)  # 默认不强制

        # 验证参数
        if not isinstance(count, int) or count <= 0 or count > 1000:
            return jsonify({'success': False, 'error': '数量必须在1-1000之间'}), 400

        # 获取最近的笔记
        notes = get_notes(limit=count, offset=0)

        if not notes:
            return jsonify({'success': False, 'error': '没有找到笔记'}), 404

        # 获取校准管理器
        calibration_manager = get_calibration_manager()

        # 批量添加到校准队列
        added_count = 0
        skipped_count = 0
        error_count = 0

        logger.info(f"📋 开始批量校准: count={count}, force={force}, 找到 {len(notes)} 条笔记")

        for note in notes:
            try:
                # 如果强制模式，跳过校准检查
                should_add = force or calibration_manager.should_calibrate_note(note)

                if should_add:
                    # 添加到校准队列（传递 force 参数）
                    if calibration_manager.add_note_to_calibration_queue(note['id'], force=force):
                        added_count += 1
                        if force:
                            logger.debug(f"✅ 强制添加笔记 {note['id']} 到校准队列")
                    else:
                        skipped_count += 1
                        logger.debug(f"⏭️ 笔记 {note['id']} 已在队列中，跳过")
                else:
                    skipped_count += 1
                    logger.debug(f"⏭️ 笔记 {note['id']} 不需要校准，跳过")
            except Exception as e:
                logger.error(f"添加笔记 {note['id']} 到校准队列失败: {e}")
                error_count += 1

        mode_text = "强制重新校准" if force else "自动校准"
        logger.info(f"✅ 批量校准完成: 模式={mode_text}, 成功={added_count}, 跳过={skipped_count}, 错误={error_count}")

        return jsonify({
            'success': True,
            'total': len(notes),
            'added': added_count,
            'skipped': skipped_count,
            'errors': error_count,
            'force': force,
            'message': f'成功添加 {added_count} 条笔记到校准队列（{mode_text}模式）'
        })

    except Exception as e:
        import traceback
        logger.error(f"批量校准API异常: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'服务器错误: {str(e)}'}), 500


def _calibrate_magnets(all_dns: list) -> list:
    """校准磁力链接列表

    Args:
        all_dns: 磁力链接信息列表

    Returns:
        list: 校准结果列表
    """
    calibrated_results = []

    for dn_info in all_dns:
        info_hash = dn_info['info_hash']
        if not info_hash:
            continue

        result = _calibrate_single_magnet(info_hash, dn_info['magnet'])
        calibrated_results.append(result)

    return calibrated_results


def _calibrate_single_magnet(info_hash: str, original_magnet: str) -> dict:
    """校准单个磁力链接

    Args:
        info_hash: 磁力链接的 info_hash
        original_magnet: 原始磁力链接

    Returns:
        dict: 校准结果
    """
    # 确定脚本路径
    qbt_script = _get_script_path('calibrate_qbt_helper.py')
    bot_script = _get_script_path('calibrate_bot_helper.py')

    filename = None
    error_msg = None

    # 优先尝试 qBittorrent API
    if qbt_script:
        logger.info(f"尝试使用qBittorrent API校准: {info_hash[:16]}...")
        filename, error_msg = _run_calibration_script(qbt_script, info_hash, timeout=30)

        if filename:
            logger.info(f"qBittorrent API校准成功: {filename[:50]}...")
        else:
            logger.warning(f"qBittorrent API校准失败: {error_msg[:100] if error_msg else '未知错误'}")

    # 回退到 Telegram 机器人
    if not filename and bot_script:
        logger.info(f"使用Telegram机器人校准: {info_hash[:16]}...")
        filename, error_msg = _run_calibration_script(bot_script, info_hash, timeout=60)

        if filename:
            logger.info(f"Telegram机器人校准成功: {filename[:50]}...")
        else:
            logger.warning(f"Telegram机器人校准失败: {error_msg[:100] if error_msg else '未知错误'}")

    if filename:
        return {
            'info_hash': info_hash,
            'old_magnet': original_magnet,
            'filename': filename,
            'success': True
        }
    else:
        return {
            'info_hash': info_hash,
            'old_magnet': original_magnet,
            'error': error_msg or '所有校准方式都失败',
            'success': False
        }


def _get_script_path(script_name: str) -> Optional[str]:
    """获取脚本路径

    Args:
        script_name: 脚本文件名

    Returns:
        Optional[str]: 脚本路径，不存在则返回 None
    """
    # Docker 环境路径
    docker_path = f'/app/{script_name}'
    if os.path.exists(docker_path):
        return docker_path

    # 本地开发环境路径
    local_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), script_name)
    if os.path.exists(local_path):
        return local_path

    return None


def _run_calibration_script(script_path: str, info_hash: str, timeout: int) -> Tuple[Optional[str], Optional[str]]:
    """运行校准脚本

    Args:
        script_path: 脚本路径
        info_hash: 磁力链接的 info_hash
        timeout: 超时时间（秒）

    Returns:
        tuple: (filename, error_msg)
    """
    try:
        result = subprocess.run(
            ['python3', script_path, info_hash],
            capture_output=True,
            text=True,
            timeout=timeout
        )

        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip(), None
        else:
            return None, result.stderr.strip() if result.stderr else '未知错误'

    except subprocess.TimeoutExpired:
        return None, f'校准超时（{timeout}秒）'
    except Exception as e:
        return None, f'执行失败: {str(e)}'


def _cleanup_calibration_tasks(note_id: int) -> None:
    """清理自动校准任务

    Uses CalibrationService for task management.

    Args:
        note_id: 笔记 ID
    """
    try:
        calibration_service = get_calibration_service()
        deleted = calibration_service.delete_tasks_for_note(note_id)
        if deleted > 0:
            logger.info(f"已清理 {deleted} 个自动校准任务（note_id={note_id}）")
    except Exception as e:
        logger.warning(f"清理自动校准任务失败（不影响手动校准）: {e}")
