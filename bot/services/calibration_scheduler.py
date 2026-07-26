"""
后台定时任务调度器
负责定期执行校准任务

``CalibrationManager`` 由构造函数注入（沿 ``composition/calibration.py`` 已确立的
先例）：调度器不再 ``from composition.calibration import get_calibration_manager``
自取单例，装配责任回到 ``main.py`` 这个进程入口。
"""
import threading
import time
import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from bot.services.calibration_manager import CalibrationManager

logger = logging.getLogger(__name__)


class CalibrationScheduler:
    """校准任务调度器"""

    def __init__(self, interval: int = 60, *, manager: "CalibrationManager"):
        """
        初始化调度器

        Args:
            interval: 检查间隔（秒），默认60秒
            manager: 组合根构造的校准管理器（进程内单例）
        """
        self.interval = interval
        self.running = False
        self.thread = None
        self.manager = manager

    def start(self):
        """启动调度器"""
        if self.running:
            logger.warning("调度器已经在运行")
            return

        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info(f"🚀 自动校准调度器已启动（间隔: {self.interval}秒）")

    def stop(self):
        """停止调度器"""
        if not self.running:
            return

        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("⏹️ 自动校准调度器已停止")

    def _run(self):
        """调度器主循环"""
        logger.info("📋 调度器主循环已启动")

        while self.running:
            try:
                # 重新加载配置
                self.manager.reload_config()

                # 检查是否启用
                if self.manager.is_enabled():
                    # 处理待执行的任务
                    concurrent_limit = self.manager.config.get('concurrent_limit', 5)
                    self.manager.process_pending_tasks(max_concurrent=concurrent_limit)

                    # 定期清理已完成的任务（每次执行时检查）
                    from database import clear_completed_calibration_tasks
                    clear_completed_calibration_tasks(days=7)

            except Exception as e:
                logger.error(f"调度器执行任务时出错: {e}", exc_info=True)

            # 等待下一个周期
            time.sleep(self.interval)

        logger.info("📋 调度器主循环已退出")


# 全局调度器实例
_scheduler = None


def get_scheduler(interval: int = 60, *, manager: "CalibrationManager") -> CalibrationScheduler:
    """获取全局调度器实例

    Args:
        interval: 检查间隔（秒）
        manager: 组合根构造的校准管理器（仅首次创建时使用）
    """
    global _scheduler
    if _scheduler is None:
        _scheduler = CalibrationScheduler(interval, manager=manager)
    return _scheduler


def start_scheduler(interval: int = 60, *, manager: "CalibrationManager"):
    """启动全局调度器

    Args:
        interval: 检查间隔（秒）
        manager: 组合根构造的校准管理器
    """
    scheduler = get_scheduler(interval, manager=manager)
    scheduler.start()


def stop_scheduler():
    """停止全局调度器"""
    global _scheduler
    if _scheduler:
        _scheduler.stop()
