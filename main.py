"""
Save-Restricted-Bot - Telegram Bot for Saving Restricted Content
Main entry point - coordinates all modules

Architecture: Uses new layered architecture (src/)
- src/core/         Configuration, constants, exceptions
- src/domain/       Business entities and logic
- src/infrastructure/  Database, storage implementations
- src/application/  Services and use cases
- src/presentation/ Bot handlers and web routes

职责：
- 初始化日志系统
- 初始化客户端
- 初始化消息队列
- 注册所有处理器
- 初始化数据库
- 打印启动配置
- 启动Bot
"""

# 导入新架构的日志配置
from src.infrastructure.logging import setup_logging, get_logger

# 初始化日志系统
setup_logging()
logger = get_logger(__name__)

# 导入核心模块
from bot.core import (
    initialize_clients,
    initialize_message_queue,
    print_startup_config
)

# 导入处理器注册
from bot.handlers import register_all_handlers

# 导入数据库（通过兼容层使用新架构）
from database import init_database

# 导入自动校准调度器
from bot.services.calibration_scheduler import start_scheduler, stop_scheduler

# 导入新架构配置（用于验证）
from src.core.config import settings


def main():
    """主函数：协调所有模块启动Bot"""
    instance_lock = None
    try:
        # 0. 验证新架构配置
        logger.info(f"📁 数据目录: {settings.paths.data_dir}")
        logger.info(f"📁 配置目录: {settings.paths.config_dir}")

        # 0.1 显式单实例约束：同一 DATA_DIR 下只允许运行一个 Bot
        try:
            from src.core.utils.single_instance_lock import acquire_single_instance_lock, SingleInstanceError

            instance_lock = acquire_single_instance_lock(settings.paths.data_dir / "bot.lock")
            logger.info("🔒 已获取单实例锁")
        except SingleInstanceError as e:
            logger.critical(f"❌ 无法获取单实例锁: {e}")
            raise SystemExit(1)

        # 1. 初始化客户端
        logger.info("🚀 正在启动 Save-Restricted-Bot...")
        bot, acc = initialize_clients()

        # 2. 初始化消息队列
        message_queue, message_worker = initialize_message_queue(acc)

        # 3. 注册所有处理器
        register_all_handlers(bot, acc, message_queue)

        # 4. 初始化数据库（致命错误）
        logger.info("🔧 正在初始化数据库系统...")
        try:
            init_database()
            logger.info("✅ 数据库初始化成功")
        except Exception as e:
            logger.critical(f"❌ 数据库初始化失败: {e}", exc_info=True)
            logger.critical("❌ 数据库是核心功能，无法继续启动")
            raise SystemExit(1)

        # 5. 启动自动校准调度器（非致命错误）
        logger.info("🔧 正在启动自动校准调度器...")
        try:
            start_scheduler(interval=60)
            logger.info("✅ 自动校准调度器已启动")
        except Exception as e:
            logger.error(f"⚠️ 启动校准调度器失败: {e}")
            logger.warning("⚠️ 系统将以降级模式运行（自动校准功能不可用）")

        # 6. 打印启动配置
        print_startup_config(acc)

        # 7. 启动Bot
        logger.info("🎬 启动Bot主循环...")
        bot.run()

    except KeyboardInterrupt:
        logger.info("\n⚠️ 收到中断信号，正在关闭...")
    except Exception as e:
        logger.error(f"❌ Bot运行时发生错误: {e}", exc_info=True)
    finally:
        # 清理资源
        logger.info("🧹 正在清理资源...")

        # 停止自动校准调度器
        try:
            stop_scheduler()
            logger.info("✅ 自动校准调度器已停止")
        except Exception as e:
            logger.error(f"⚠️ 停止校准调度器时出错: {e}")

        if acc is not None:
            try:
                acc.stop()
                logger.info("✅ User客户端已停止")
            except Exception as e:
                logger.error(f"⚠️ 停止User客户端时出错: {e}")

        if instance_lock is not None:
            try:
                instance_lock.close()
            except Exception as e:
                logger.debug(f"释放单实例锁失败（忽略）: {e}")

        logger.info("👋 Bot已关闭")


if __name__ == "__main__":
    main()
