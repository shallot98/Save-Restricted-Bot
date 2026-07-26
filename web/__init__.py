"""
Flask 应用工厂模块

遵循 SOLID 原则：
- SRP: 仅负责应用初始化和蓝图注册
- OCP: 通过蓝图扩展功能，无需修改此文件
- DIP: 依赖抽象的蓝图接口

Architecture: Uses new layered architecture
- 数据库初始化直连 src.infrastructure.persistence（Phase 2 已拆掉经由
  src/compat + 根 database.py 的双向桥）
- 服务实例由调用方（app.py，经 composition.web_runtime）构造后注入，本模块
  与整个 web/ 包都不认识组合根（报告 §5.3 规则 3）
"""
import os
import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional
from flask import Flask

# New architecture imports
from src.infrastructure.persistence import init_database
from bot.config.constants import AppConstants
from web.security import init_csrf, init_security_headers
from web.services import WebServices, bind_services

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WebInfrastructure:
    """构造期基础设施副作用的注入点（建库 + 存储管理器）。

    为什么需要它
    ------------
    工厂在构造期真的建库、真的按 WebDAV 配置连远端。这两个副作用把
    `web/routes/` 的写路径挡在了测试之外——报告 §3 P1-6 里 api/admin/notes/main
    合计 551 语句 0% 覆盖，唯一有覆盖的 media 路由靠的是**绕开工厂**自建
    `Flask(__name__)`，因而测不到工厂注册的 CSRF、安全头与服务绑定。

    与 `services` 的必填语义不冲突：这里注入的是本模块已经 import 的具体函数，
    不是跨层的服务定位；缺省即生产行为，`app.py` 无需改动。
    """

    init_database: Callable[[], None]
    init_storage_manager: Callable[[], Any]


def _default_infrastructure() -> WebInfrastructure:
    """生产默认：真建库 + 真按 WebDAV 配置装配存储管理器。

    `init_storage_manager` 延迟到调用时才 import，沿用改造前的行为——
    `web.utils.storage` 会拉起根 `database` / `config` 模块，提到模块顶层会让
    `import web` 的代价（与副作用面）无谓变大。
    """
    from web.utils.storage import init_storage_manager

    return WebInfrastructure(
        init_database=init_database,
        init_storage_manager=init_storage_manager,
    )


def create_app(
    config: Optional[dict] = None,
    *,
    services: WebServices,
    infrastructure: Optional[WebInfrastructure] = None,
) -> Flask:
    """Flask 应用工厂

    Args:
        config: 可选的配置字典，用于测试或自定义配置
        services: 组合根装配的服务集合。必填——给它一个「自己去容器里取」的默认值
            就等于把服务定位藏进工厂，路由层的解耦也就白做了。
        infrastructure: 构造期副作用的实现。缺省为生产实现（见
            `_default_infrastructure`）；测试传入内存/临时目录版本即可在不碰真实
            `data/notes.db` 的前提下走完整个工厂。

    Returns:
        Flask: 配置完成的 Flask 应用实例
    """
    infra = infrastructure or _default_infrastructure()
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

    # 绑定组合根装配好的服务（路由经 web.services.get_services() 取用）
    bind_services(app, services)

    # 初始化数据库
    infra.init_database()

    # 初始化存储管理器
    app.storage_manager = infra.init_storage_manager()

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
