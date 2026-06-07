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
from flask import Blueprint, render_template, request, current_app

# New architecture imports
from src.core.container import get_calibration_service, get_note_service

# Legacy imports (for backward compatibility)
from database import verify_user, update_password
from config import (
    load_webdav_config, save_webdav_config,
    load_viewer_config, save_viewer_config
)
from bot.storage.webdav_client import WebDAVClient
from web.auth import login_required
from web.routes.admin_helpers import (
    PasswordChangeDeps,
    WebDAVSaveDeps,
    build_admin_context,
    change_password,
    read_password_change_form,
    read_viewer_config,
    read_webdav_config,
    save_webdav_settings,
    validate_viewer_config,
    validate_webdav_config,
)
from web.utils.storage import init_storage_manager

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('', methods=['GET', 'POST'])
@login_required
def admin():
    """管理后台主页 - 仪表盘"""
    from flask import session

    note_service = get_note_service()
    calibration_service = get_calibration_service()
    context = build_admin_context(
        note_service,
        calibration_service,
        must_change_password=bool(session.get("must_change_password")),
    )

    if request.method == 'POST':
        change = read_password_change_form(request.form, session['username'])
        error = change_password(change, PasswordChangeDeps(verify_user, update_password))
        if error:
            return render_template('admin.html', error=error, **context)

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
            config = read_webdav_config(request.form)
            error = validate_webdav_config(config, WebDAVClient)
            if error:
                return render_template('admin_webdav.html', config=config, error=error)

            deps = WebDAVSaveDeps(save_webdav_config, init_storage_manager, current_app)
            save_webdav_settings(config, deps)

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
            config = read_viewer_config(request.form)
            error = validate_viewer_config(config)
            if error:
                return render_template('admin_viewer.html', config=config, error=error)

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
