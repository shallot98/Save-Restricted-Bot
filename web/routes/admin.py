"""
管理后台路由模块

遵循 SRP 原则：负责管理后台相关功能
包括：密码管理、WebDAV 配置、观看网站配置、校准配置

Architecture: Uses new layered architecture
- src/core/container for service access
- src/application/services for business logic
"""
import logging
import threading
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, current_app

# New architecture imports
from src.core.container import get_calibration_service, get_note_service

# Legacy imports (for backward compatibility)
from database import verify_user, update_password
from config import (
    load_webdav_config, save_webdav_config,
    load_viewer_config, save_viewer_config
)
from bot.storage.webdav_client import WebDAVClient
from web.auth import login_required, api_login_required
from web.utils.storage import init_storage_manager

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('', methods=['GET', 'POST'])
@login_required
def admin():
    """管理后台主页 - 仪表盘"""
    from flask import session
    
    # 获取统计数据
    note_service = get_note_service()
    calibration_service = get_calibration_service()
    
    # 获取笔记总数
    try:
        notes_result = note_service.get_notes(user_id=None, page_size=1)
        total_notes = notes_result.total
        sources = note_service.get_all_sources()
        total_sources = len(sources)
    except Exception as e:
        logger.error(f"获取笔记统计失败: {e}")
        total_notes = 0
        total_sources = 0

    # 获取校准任务统计
    try:
        calib_stats = calibration_service.get_stats()
    except Exception as e:
        logger.error(f"获取校准统计失败: {e}")
        calib_stats = {'total': 0, 'by_status': {}}

    context = {
        'total_count': total_notes,
        'total_sources': total_sources,
        'calib_stats': calib_stats,
        'sources': sources if 'sources' in locals() else [],
        'must_change_password': bool(session.get("must_change_password")),
    }

    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        # 验证当前密码
        if not verify_user(session['username'], current_password):
            return render_template('admin.html', error='当前密码不正确', **context)

        # 验证新密码
        if len(new_password) < 6:
            return render_template('admin.html', error='新密码长度至少为 6 个字符', **context)

        if new_password != confirm_password:
            return render_template('admin.html', error='两次输入的新密码不一致', **context)

        # 更新密码
        update_password(session['username'], new_password)
        session.pop("must_change_password", None)
        context["must_change_password"] = False
        return render_template('admin.html', success='密码更新成功', **context)

    return render_template('admin.html', **context)


@admin_bp.route('/webdav', methods=['GET', 'POST'])
@login_required
def admin_webdav():
    """WebDAV 配置管理"""
    if request.method == 'POST':
        try:
            # 获取表单数据
            enabled = request.form.get('enabled') == 'on'
            url = request.form.get('url', '').strip()
            username = request.form.get('webdav_username', '').strip()
            password = request.form.get('webdav_password', '').strip()
            base_path = request.form.get('base_path', '/telegram_media').strip()
            keep_local_copy = request.form.get('keep_local_copy') == 'on'

            # 构建配置
            config = {
                'enabled': enabled,
                'url': url,
                'username': username,
                'password': password,
                'base_path': base_path,
                'keep_local_copy': keep_local_copy
            }

            # 如果启用了 WebDAV，测试连接
            if enabled and url and username and password:
                try:
                    test_client = WebDAVClient(url, username, password, base_path)
                    if not test_client.test_connection():
                        return render_template(
                            'admin_webdav.html',
                            config=config,
                            error='WebDAV 连接测试失败，请检查配置'
                        )
                except Exception as e:
                    return render_template(
                        'admin_webdav.html',
                        config=config,
                        error=f'WebDAV 连接失败: {str(e)}'
                    )

            # 保存配置
            save_webdav_config(config)

            # 重新初始化存储管理器
            current_app.storage_manager = init_storage_manager()

            return render_template(
                'admin_webdav.html',
                config=config,
                success='WebDAV 配置已保存'
            )

        except Exception as e:
            config = load_webdav_config()
            return render_template(
                'admin_webdav.html',
                config=config,
                error=f'保存配置失败: {str(e)}'
            )

    # GET 请求，加载当前配置
    config = load_webdav_config()
    return render_template('admin_webdav.html', config=config)


@admin_bp.route('/viewer', methods=['GET', 'POST'])
@login_required
def admin_viewer():
    """观看网站配置管理"""
    if request.method == 'POST':
        try:
            viewer_url = request.form.get('viewer_url', '').strip()

            # 验证 URL 格式
            if not viewer_url:
                return render_template(
                    'admin_viewer.html',
                    config={'viewer_url': viewer_url},
                    error='观看网站URL不能为空'
                )

            if not (viewer_url.startswith('http://') or viewer_url.startswith('https://')):
                return render_template(
                    'admin_viewer.html',
                    config={'viewer_url': viewer_url},
                    error='URL必须以 http:// 或 https:// 开头'
                )

            config = {'viewer_url': viewer_url}
            save_viewer_config(config)

            return render_template(
                'admin_viewer.html',
                config=config,
                success='观看网站配置已保存'
            )

        except Exception as e:
            config = load_viewer_config()
            return render_template(
                'admin_viewer.html',
                config=config,
                error=f'保存配置失败: {str(e)}'
            )

    config = load_viewer_config()
    return render_template('admin_viewer.html', config=config)


@admin_bp.route('/calibration', methods=['GET', 'POST'])
@login_required
def admin_calibration():
    """自动校准配置管理

    Uses CalibrationService for configuration management.
    """
    calibration_service = get_calibration_service()

    if request.method == 'POST':
        try:
            config_data = {
                'enabled': 1 if request.form.get('enabled') == 'on' else 0,
                'filter_mode': request.form.get('filter_mode', 'empty_only'),
                'first_delay': int(request.form.get('first_delay', 600)),
                'retry_delay_1': int(request.form.get('retry_delay_1', 3600)),
                'retry_delay_2': int(request.form.get('retry_delay_2', 14400)),
                'retry_delay_3': int(request.form.get('retry_delay_3', 28800)),
                'max_retries': int(request.form.get('max_retries', 3)),
                'concurrent_limit': int(request.form.get('concurrent_limit', 5)),
                'timeout_per_magnet': int(request.form.get('timeout_per_magnet', 30)),
                'batch_timeout': int(request.form.get('batch_timeout', 300))
            }

            # 使用 CalibrationService 更新配置
            calibration_service.update_config(config_data)

            # 重新加载校准管理器配置
            _reload_calibration_config()

            stats = calibration_service.get_stats()
            return render_template(
                'admin_calibration.html',
                config=config_data,
                stats=stats,
                success='自动校准配置已保存'
            )

        except Exception as e:
            logger.exception(f"保存校准配置失败: {e}")
            config = calibration_service.get_config()
            stats = calibration_service.get_stats()
            return render_template(
                'admin_calibration.html',
                config=config.to_dict(),
                stats=stats,
                error=f'保存配置失败: {str(e)}'
            )

    config = calibration_service.get_config()
    stats = calibration_service.get_stats()
    return render_template('admin_calibration.html', config=config.to_dict(), stats=stats)


def _reload_calibration_config() -> None:
    """在独立线程中重新加载校准配置"""
    try:
        from bot.services.calibration_manager import get_calibration_manager

        def reload_in_thread():
            try:
                manager = get_calibration_manager()
                manager.reload_config()
            except Exception as e:
                logger.error(f"重新加载校准配置失败: {e}")

        reload_thread = threading.Thread(target=reload_in_thread, daemon=True)
        reload_thread.start()
        reload_thread.join(timeout=2)
    except Exception as e:
        logger.warning(f"重新加载校准配置时出现警告: {e}")


@admin_bp.route('/calibration/queue')
@login_required
def admin_calibration_queue():
    """校准任务队列查看

    Uses CalibrationService for task management.
    """
    calibration_service = get_calibration_service()

    status_filter = request.args.get('status', '')
    page = int(request.args.get('page', 1))
    per_page = 50

    # 使用 CalibrationService 获取任务列表
    tasks = calibration_service.list_all(
        status=status_filter if status_filter else None,
        limit=per_page,
        offset=(page - 1) * per_page
    )

    # 将 CalibrationTask 转换为字典以便模板使用
    tasks_data = [task.to_dict() for task in tasks]

    # 使用 CalibrationService 获取统计信息
    stats = calibration_service.get_stats()

    return render_template(
        'admin_calibration_queue.html',
        tasks=tasks_data,
        stats=stats,
        status_filter=status_filter,
        page=page
    )
