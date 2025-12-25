"""
Flask 应用工厂模块

遵循 SOLID 原则：
- SRP: 仅负责应用初始化和蓝图注册
- OCP: 通过蓝图扩展功能，无需修改此文件
- DIP: 依赖抽象的蓝图接口

Architecture: Uses new layered architecture
- src/compat for backward compatibility
"""
import os
import logging
from typing import Optional
from flask import Flask

# New architecture imports
from src.compat.database_compat import init_database, DATA_DIR
from bot.config.constants import AppConstants
from web.security import init_csrf, init_security_headers

logger = logging.getLogger(__name__)


def create_app(config: Optional[dict] = None) -> Flask:
    """Flask 应用工厂

    Args:
        config: 可选的配置字典，用于测试或自定义配置

    Returns:
        Flask: 配置完成的 Flask 应用实例
    """
    app = Flask(
        __name__,
        template_folder='../templates',
        static_folder='../static'
    )

    # 基础配置
    app.secret_key = AppConstants.FLASK_SECRET_KEY
    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", os.environ.get("SESSION_COOKIE_SAMESITE", "Lax"))
    app.config.setdefault(
        "SESSION_COOKIE_SECURE",
        os.environ.get("SESSION_COOKIE_SECURE", "").strip().lower() in {"1", "true", "yes", "on"},
    )

    # 应用自定义配置
    if config:
        app.config.update(config)

    # 安全基线：CSRF 与安全响应头（best-effort，不依赖额外三方库）
    init_csrf(app)
    init_security_headers(app)

    # 初始化数据库
    init_database()

    # 初始化存储管理器
    from web.utils.storage import init_storage_manager
    app.storage_manager = init_storage_manager()

    # 注册 Jinja2 过滤器
    from web.utils.filters import register_filters
    register_filters(app)

    # 注册蓝图
    _register_blueprints(app)

    return app


def _register_blueprints(app: Flask) -> None:
    """注册所有蓝图

    Args:
        app: Flask 应用实例
    """
    from web.routes.main import main_bp
    from web.routes.auth import auth_bp
    from web.routes.notes import notes_bp
    from web.routes.admin import admin_bp
    from web.routes.media import media_bp
    from web.routes.api import api_bp
    from web.routes.monitoring import monitoring_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(notes_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(media_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(monitoring_bp, url_prefix='/monitoring')
