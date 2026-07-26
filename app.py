"""
Flask Web 应用入口

Architecture: Uses new layered architecture (src/)
- src/core/           Configuration and constants
- web/                Flask 表现层（唯一，src/presentation 空壳已删除）
- src/application/    Services for business logic
- src/infrastructure/ Database and storage

重构后的简洁入口点，遵循 SOLID 原则：
- SRP: 仅负责应用启动
- OCP: 通过 web 模块扩展功能
- DIP: 依赖应用工厂创建实例
"""

import os

# 导入新架构配置
from src.core.config import settings
from src.infrastructure.logging import setup_logging, get_logger
from src.infrastructure.monitoring.performance.middleware import PerformanceMiddleware

# 初始化日志
setup_logging()
logger = get_logger(__name__)

# 组合根：装配 bot 侧具体实现（必须早于任何服务被取用），并构造交给 Flask 的
# 服务集合——web/ 自身不再认识组合根（报告 §5.3 规则 3）。
from composition.web_runtime import build_web_services
from composition.wiring import configure_runtime_implementations

# 导入 Web 应用工厂
from web import create_app

# 创建 Flask 应用实例
configure_runtime_implementations()
app = create_app(services=build_web_services())
PerformanceMiddleware(app)

# 记录启动信息
logger.info(f"📁 数据目录: {settings.paths.data_dir}")
logger.info(f"📁 媒体目录: {settings.paths.media_dir}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"🌐 启动 Web 服务器，端口: {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
