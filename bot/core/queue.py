"""
消息队列管理模块
职责：初始化消息队列和工作线程

环境变量:
    - MESSAGE_QUEUE_MAXSIZE: 队列最大容量，默认 1000
    - MESSAGE_WORKER_COUNT: Worker 线程数量，默认 3（提高记录模式处理速率）
"""
import queue
import os
import threading
import time
from typing import TYPE_CHECKING, Optional

from bot.utils.logger import get_logger
from bot.workers import MessageWorker
from constants import MAX_RETRIES

if TYPE_CHECKING:
    from src.application.services import MessageWorkerService, WatchService

logger = get_logger(__name__)

DEFAULT_QUEUE_MAXSIZE = 1000
DEFAULT_WORKER_COUNT = 3
MAX_WORKER_COUNT = 10
DEFAULT_SHUTDOWN_TIMEOUT = 10.0


def initialize_message_queue(
    acc,
    *,
    message_service: Optional["MessageWorkerService"] = None,
    watch_service: Optional["WatchService"] = None,
):
    """
    初始化消息队列和工作线程

    Args:
        acc: User客户端实例（如果为None，则不初始化队列）
        message_service: 组合根装配的笔记落库/指标编排服务，透传给每个 worker
        watch_service: 组合根装配的监控配置服务，透传给每个 worker（链式转发用）

    两个服务参数由 ``main.py`` 从 ``BotServices`` 取出后传入。默认 None 只服务于
    不触碰服务的关闭/重试单测；worker 内部取用时未注入会立刻抛错。

    Returns:
        tuple: (message_queue, message_workers)
            - message_queue: 消息队列实例
            - message_workers: 消息工作线程实例列表
            如果acc为None，返回 (None, None)
    """
    if acc is None:
        logger.warning("⚠️ User客户端未初始化，跳过消息队列初始化")
        return None, None

    logger.info("📬 正在初始化消息队列系统...")
    message_queue = queue.Queue(maxsize=_queue_maxsize())
    message_workers, worker_threads = _create_message_workers(
        message_queue, acc, message_service=message_service, watch_service=watch_service
    )
    _start_worker_threads(worker_threads)
    _log_queue_initialization(message_queue, worker_threads)
    return message_queue, _legacy_worker_return(message_workers)


def _queue_maxsize() -> int:
    return _env_int("MESSAGE_QUEUE_MAXSIZE", DEFAULT_QUEUE_MAXSIZE)


def _worker_count() -> int:
    return max(1, min(_env_int("MESSAGE_WORKER_COUNT", DEFAULT_WORKER_COUNT), MAX_WORKER_COUNT))


def _env_int(name: str, default: int) -> int:
    raw_value = os.environ.get(name)
    try:
        return int(raw_value) if raw_value is not None else default
    except ValueError:
        return default


def _create_message_workers(message_queue, acc, *, message_service=None, watch_service=None):
    message_workers = []
    worker_threads = []
    for i in range(_worker_count()):
        worker = MessageWorker(
            message_queue,
            acc,
            max_retries=MAX_RETRIES,
            message_service=message_service,
            watch_service=watch_service,
        )
        thread = threading.Thread(
            target=worker.run,
            daemon=True,
            name=f"MessageWorker-{i + 1}",
        )
        worker.thread = thread
        message_workers.append(worker)
        worker_threads.append(thread)
    return message_workers, worker_threads


def _start_worker_threads(worker_threads: list[threading.Thread]) -> None:
    for thread in worker_threads:
        thread.start()


def _log_queue_initialization(message_queue, worker_threads: list[threading.Thread]) -> None:
    logger.info("✅ 消息队列系统初始化完成")
    logger.info(f"   - 最大重试次数: {MAX_RETRIES}")
    logger.info(f"   - 队列上限: {message_queue.maxsize}")
    logger.info(f"   - Worker 线程数: {len(worker_threads)}")
    for thread in worker_threads:
        logger.info(f"   - 工作线程: {thread.name}")


def _legacy_worker_return(message_workers: list):
    return message_workers[0] if len(message_workers) == 1 else message_workers


def normalize_message_workers(message_workers) -> list[MessageWorker]:
    """Accept the single/list polymorphic return of initialize_message_queue."""
    if message_workers is None:
        return []
    if isinstance(message_workers, (list, tuple)):
        return [worker for worker in message_workers if worker is not None]
    return [message_workers]


def shutdown_message_workers(message_workers, *, timeout: float = DEFAULT_SHUTDOWN_TIMEOUT) -> bool:
    """Stop all message workers and wait for their threads within a shared deadline.

    Returns:
        True 表示全部线程已退出；False 表示有线程超时（未处理消息数量会记录到日志）。
    """
    workers = normalize_message_workers(message_workers)
    if not workers:
        return True

    for worker in workers:
        worker.stop()

    deadline = time.monotonic() + max(0.0, timeout)
    all_stopped = True
    for worker in workers:
        if not worker.join_thread(max(0.0, deadline - time.monotonic())):
            all_stopped = False

    _log_worker_shutdown(workers, all_stopped)
    return all_stopped


def _log_worker_shutdown(workers: list[MessageWorker], all_stopped: bool) -> None:
    pending = workers[0].message_queue.qsize() if workers[0].message_queue is not None else 0
    delayed = sum(worker.delayed_count for worker in workers)
    if not all_stopped:
        logger.warning(f"⚠️ 部分消息工作线程未在超时内退出（队列剩余={pending}, 延迟队列={delayed}）")
        return
    if pending or delayed:
        logger.warning(f"⚠️ 消息工作线程已停止，仍有未处理消息（队列剩余={pending}, 延迟队列={delayed}）")
        return
    logger.info("✅ 消息工作线程已全部停止，队列已清空")
