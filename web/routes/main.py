"""
主页和健康检查路由

遵循 SRP 原则：仅负责主页重定向和健康检查端点
"""
import os
from flask import Blueprint, redirect, url_for, session, jsonify
from src.core.config import settings
from flask import current_app
from src.infrastructure.persistence.sqlite.connection import get_db_connection

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def home():
    """主页路由，重定向到笔记页面或登录页面"""
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    return redirect(url_for('notes.notes_list'))


@main_bp.route('/health')
def health():
    """健康检查端点

    检查数据库、配置文件和存储状态

    Returns:
        JSON 响应，包含各组件健康状态
    """
    status = {'status': 'healthy', 'checks': {}}

    # 检查数据库
    try:
        with get_db_connection() as conn:
            conn.execute("SELECT 1").fetchone()
        status['checks']['database'] = 'ok'
    except Exception as e:
        status['status'] = 'unhealthy'
        status['checks']['database'] = f'error: {str(e)}'

    # 检查配置文件
    status['checks']['config'] = 'ok' if os.path.exists(settings.paths.config_file) else 'missing'
    status['checks']['watch_config'] = 'ok' if os.path.exists(settings.paths.watch_file) else 'missing'

    # 检查存储
    storage_manager = getattr(current_app, 'storage_manager', None)
    status['checks']['storage'] = 'ok' if storage_manager else 'error'

    return jsonify(status), 200 if status['status'] == 'healthy' else 503
