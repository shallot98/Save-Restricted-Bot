"""
主页和健康检查路由

遵循 SRP 原则：仅负责主页重定向和健康检查端点
"""
import logging
import os
from typing import Dict

from flask import Blueprint, redirect, url_for, session, jsonify
from src.core.config import settings
from flask import current_app
from src.infrastructure.persistence.sqlite.connection import get_db_connection

logger = logging.getLogger(__name__)

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

    检查数据库、配置文件和存储状态。

    该端点**不需要登录**（`docker-compose.yml` 的 healthcheck 直接 GET 它），
    因此响应体里只放固定枚举值，异常细节一律只进日志——此前数据库分支回显
    `str(e)`，会把 `/app/data/notes.db` 这类内部路径暴露给任意匿名客户端。

    状态语义：

    - ``healthy``   → 200，全部探针正常
    - ``degraded``  → 200，存储不可用但数据库仍可服务
    - ``unhealthy`` → 503，数据库不可用

    存储故障刻意不返回 503：`restart: unless-stopped` + healthcheck 的组合下，
    WebDAV 抖动会让编排层把一个仍能读写笔记的 Web 进程判成坏进程。宁可让
    `degraded` 在响应体里显式可见、由人或监控去看，也不因外部依赖抖动打断服务。

    Returns:
        JSON 响应，包含各组件健康状态
    """
    # checks 单独声明：内联进 dict 字面量会让 mypy 把整个 status 推成
    # dict[str, Collection[str]]，后续每一次嵌套赋值都报 index 错。
    checks: Dict[str, str] = {}
    overall = 'healthy'

    # 检查数据库
    try:
        with get_db_connection() as conn:
            conn.execute("SELECT 1").fetchone()
        checks['database'] = 'ok'
    except Exception as e:
        logger.exception(f"健康检查：数据库探针失败: {e}")
        overall = 'unhealthy'
        checks['database'] = 'error'

    # 检查配置文件
    checks['config'] = 'ok' if os.path.exists(settings.paths.config_file) else 'missing'
    checks['watch_config'] = 'ok' if os.path.exists(settings.paths.watch_file) else 'missing'

    # 检查存储
    storage_manager = getattr(current_app, 'storage_manager', None)
    if storage_manager:
        checks['storage'] = 'ok'
    else:
        checks['storage'] = 'error'
        # 不覆盖 unhealthy：数据库故障是更严重的判定，降级不能把它盖回去
        if overall == 'healthy':
            overall = 'degraded'

    return jsonify({'status': overall, 'checks': checks}), 503 if overall == 'unhealthy' else 200
