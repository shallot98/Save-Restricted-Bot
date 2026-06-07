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
from bot.utils.logger import get_logger
from bot.workers import MessageWorker
from constants import MAX_RETRIES

logger = get_logger(__name__)

DEFAULT_QUEUE_MAXSIZE = 1000
DEFAULT_WORKER_COUNT = 3
MAX_WORKER_COUNT = 10


def initialize_message_queue(acc):
    """
    初始化消息队列和工作线程

    Args:
        acc: User客户端实例（如果为None，则不初始化队列）

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
    message_workers, worker_threads = _create_message_workers(message_queue, acc)
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


def _create_message_workers(message_queue, acc):
    message_workers = []
    worker_threads = []
    for i in range(_worker_count()):
        worker = MessageWorker(message_queue, acc, max_retries=MAX_RETRIES)
        thread = threading.Thread(
            target=worker.run,
            daemon=True,
            name=f"MessageWorker-{i + 1}",
        )
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
