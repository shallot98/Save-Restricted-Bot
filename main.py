"""
Save-Restricted-Bot - Telegram Bot for Saving Restricted Content
Main entry point - coordinates all modules

Architecture: Uses new layered architecture (src/)
- src/core/         Configuration, constants, exceptions
- src/domain/       Business entities and logic
- src/infrastructure/  Database, storage implementations
- src/application/  Services and use cases
- bot/              Telegram 表现层（唯一，src/presentation 空壳已删除）

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

# 组合根：把 bot 侧具体实现装配进 DI 容器（必须早于任何服务被取用），
# 并构造交给表现层的服务集合——bot/ 自身不再认识组合根（报告 §5.3 规则 3）。
from composition.bot_runtime import build_bot_services
from composition.wiring import configure_runtime_implementations

# 导入核心模块
from bot.core import (
    initialize_clients,
    initialize_message_queue,
    print_startup_config
)
from bot.core.queue import shutdown_message_workers

# 导入处理器注册
from bot.handlers import register_all_handlers

# 导入数据库（通过兼容层使用新架构）
from database import init_database

# 导入自动校准调度器
from bot.services.calibration_scheduler import start_scheduler, stop_scheduler
from bot.services.history_copy_task_manager import get_history_copy_task_manager
from bot.services.pt_pay_manager import get_pt_pay_monitor_manager
from bot.services.signin_manager import get_scheduled_signin_manager
from bot.services.watch_catchup_scheduler import (
    start_watch_catchup_scheduler,
    stop_watch_catchup_scheduler,
)

# 导入新架构配置（用于验证）
from src.core.config import settings


def main():
    """主函数：协调所有模块启动Bot"""
    instance_lock = None
    acc = None
    message_workers = None
    try:
        _log_runtime_paths()
        configure_runtime_implementations()
        services = build_bot_services()
        instance_lock = _acquire_instance_lock()
        bot, acc, message_queue, message_workers = _initialize_bot_runtime(services)
        _initialize_database_or_exit()
        _start_calibration_scheduler(services)
        # Peer cache happens inside print_startup_config; start catch-up after that.
        print_startup_config(acc)
        _start_watch_catchup_scheduler(acc, message_queue, services)
        _run_bot(bot)
    except KeyboardInterrupt:
        logger.info("\n⚠️ 收到中断信号，正在关闭...")
    except Exception as e:
        logger.error(f"❌ Bot运行时发生错误: {e}", exc_info=True)
    finally:
        _cleanup_resources(acc, instance_lock, message_workers)


def _log_runtime_paths() -> None:
    logger.info(f"📁 数据目录: {settings.paths.data_dir}")
    logger.info(f"📁 配置目录: {settings.paths.config_dir}")


def _acquire_instance_lock():
    from src.core.utils.single_instance_lock import SingleInstanceError, acquire_single_instance_lock

    try:
        instance_lock = acquire_single_instance_lock(settings.paths.data_dir / "bot.lock")
        logger.info("🔒 已获取单实例锁")
        return instance_lock
    except SingleInstanceError as e:
        logger.critical(f"❌ 无法获取单实例锁: {e}")
        raise SystemExit(1)


def _initialize_bot_runtime(services):
    logger.info("🚀 正在启动 Save-Restricted-Bot...")
    bot, acc = initialize_clients()
    message_queue, message_worker = initialize_message_queue(
        acc,
        message_service=services.message_worker_service,
        watch_service=services.watch_service,
    )
    register_all_handlers(bot, acc, message_queue, services=services)
    return bot, acc, message_queue, message_worker


def _initialize_database_or_exit() -> None:
    logger.info("🔧 正在初始化数据库系统...")
    try:
        init_database()
        logger.info("✅ 数据库初始化成功")
    except Exception as e:
        logger.critical(f"❌ 数据库初始化失败: {e}", exc_info=True)
        logger.critical("❌ 数据库是核心功能，无法继续启动")
        raise SystemExit(1)


def _start_calibration_scheduler(services) -> None:
    logger.info("🔧 正在启动自动校准调度器...")
    try:
        start_scheduler(interval=60, manager=services.calibration_manager)
        logger.info("✅ 自动校准调度器已启动")
    except Exception as e:
        logger.error(f"⚠️ 启动校准调度器失败: {e}")
        logger.warning("⚠️ 系统将以降级模式运行（自动校准功能不可用）")


def _start_watch_catchup_scheduler(acc, message_queue, services) -> None:
    logger.info("🔧 正在启动监控源 catch-up 调度器...")
    try:
        start_watch_catchup_scheduler(
            acc, message_queue, watch_service=services.watch_service
        )
        logger.info("✅ 监控源 catch-up 调度器已启动")
    except Exception as e:
        logger.error(f"⚠️ 启动 catch-up 调度器失败: {e}")
        logger.warning("⚠️ 系统将以降级模式运行（漏消息自动补扫不可用）")


def _run_bot(bot) -> None:
    logger.info("🎬 启动Bot主循环...")
    bot.run()


def _cleanup_resources(acc, instance_lock, message_workers=None) -> None:
    logger.info("🧹 正在清理资源...")
    _stop_watch_catchup_scheduler()
    _stop_message_workers(message_workers)
    _stop_calibration_scheduler()
    _shutdown_history_copy_task_manager()
    _shutdown_pt_pay_monitor_manager()
    _shutdown_scheduled_signin_manager()
    _stop_user_client(acc)
    _release_instance_lock(instance_lock)
    logger.info("👋 Bot已关闭")


def _stop_message_workers(message_workers) -> None:
    if message_workers is None:
        return
    try:
        if shutdown_message_workers(message_workers):
            logger.info("✅ 消息工作线程已停止")
        else:
            logger.warning("⚠️ 消息工作线程未能全部在超时内退出")
    except Exception as e:
        logger.error(f"⚠️ 停止消息工作线程时出错: {e}", exc_info=True)


def _stop_calibration_scheduler() -> None:
    try:
        stop_scheduler()
        logger.info("✅ 自动校准调度器已停止")
    except Exception as e:
        logger.error(f"⚠️ 停止校准调度器时出错: {e}")


def _stop_watch_catchup_scheduler() -> None:
    try:
        stop_watch_catchup_scheduler()
        logger.info("✅ 监控源 catch-up 调度器已停止")
    except Exception as e:
        logger.error(f"⚠️ 停止 catch-up 调度器时出错: {e}")


def _shutdown_history_copy_task_manager() -> None:
    try:
        get_history_copy_task_manager().shutdown()
        logger.info("✅ 历史复制任务管理器已停止")
    except Exception as e:
        logger.error(f"⚠️ 停止历史复制任务管理器时出错: {e}")


def _shutdown_pt_pay_monitor_manager() -> None:
    try:
        get_pt_pay_monitor_manager().shutdown()
        logger.info("✅ PT 联动脚本管理器已停止")
    except Exception as e:
        logger.error(f"⚠️ 停止 PT 联动脚本管理器时出错: {e}")


def _shutdown_scheduled_signin_manager() -> None:
    try:
        get_scheduled_signin_manager().shutdown()
        logger.info("✅ 定时签到脚本管理器已停止")
    except Exception as e:
        logger.error(f"⚠️ 停止定时签到脚本管理器时出错: {e}")


def _stop_user_client(acc) -> None:
    if acc is None:
        return
    try:
        acc.stop()
        logger.info("✅ User客户端已停止")
    except Exception as e:
        logger.error(f"⚠️ 停止User客户端时出错: {e}")


def _release_instance_lock(instance_lock) -> None:
    if instance_lock is None:
        return
    try:
        instance_lock.close()
    except Exception as e:
        logger.debug(f"释放单实例锁失败（忽略）: {e}")


if __name__ == "__main__":
    main()
