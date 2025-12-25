"""
Flask Web 应用入口

Architecture: Uses new layered architecture (src/)
- src/core/           Configuration and constants
- src/presentation/   Web routes and views
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

# 导入 Web 应用工厂（保持使用现有 web 模块，它已通过兼容层使用新架构）
from web import create_app

# 创建 Flask 应用实例
app = create_app()
PerformanceMiddleware(app)

# 记录启动信息
logger.info(f"📁 数据目录: {settings.paths.data_dir}")
logger.info(f"📁 媒体目录: {settings.paths.media_dir}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"🌐 启动 Web 服务器，端口: {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
