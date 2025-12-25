"""
多 Worker 消息队列系统
提升消息处理并发能力
"""
import queue
import threading
import logging
from typing import List
from bot.workers.message_worker import MessageWorker, Message

logger = logging.getLogger(__name__)


class MultiWorkerQueue:
    """多 Worker 消息队列管理器"""
    
    def __init__(self, acc_client, worker_count: int = 4, max_retries: int = 3):
        """
        初始化多 Worker 队列
        
        Args:
            acc_client: User 客户端实例
            worker_count: Worker 线程数量
            max_retries: 最大重试次数
        """
        self.message_queue = queue.Queue()
        self.acc = acc_client
        self.worker_count = worker_count
        self.max_retries = max_retries
        self.workers: List[MessageWorker] = []
        self.worker_threads: List[threading.Thread] = []
        self.running = False
        
        logger.info(f"🚀 初始化多 Worker 队列系统 (Worker 数量: {worker_count})")
    
    def start(self):
        """启动所有 Worker 线程"""
        if self.running:
            logger.warning("⚠️ Worker 队列已在运行")
            return
        
        self.running = True
        
        # 创建并启动 Worker 线程
        for i in range(self.worker_count):
            worker = MessageWorker(
                message_queue=self.message_queue,
                acc_client=self.acc,
                max_retries=self.max_retries
            )
            self.workers.append(worker)
            
            thread = threading.Thread(
                target=worker.run,
                name=f"MessageWorker-{i+1}",
                daemon=True
            )
            thread.start()
            self.worker_threads.append(thread)
            
            logger.info(f"✅ Worker-{i+1} 已启动")
        
        logger.info(f"🎉 所有 {self.worker_count} 个 Worker 已启动")
    
    def stop(self):
        """停止所有 Worker 线程"""
        if not self.running:
            return
        
        logger.info("🛑 正在停止所有 Worker...")
        
        # 停止所有 Worker
        for worker in self.workers:
            worker.running = False
        
        # 等待所有线程结束
        for thread in self.worker_threads:
            thread.join(timeout=5)
        
        self.running = False
        logger.info("✅ 所有 Worker 已停止")
    
    def put(self, message: Message):
        """
        将消息放入队列
        
        Args:
            message: 消息对象
        """
        self.message_queue.put(message)
    
    def get_stats(self) -> dict:
        """
        获取队列统计信息
        
        Returns:
            dict: 统计信息字典
        """
        total_processed = sum(w.processed_count for w in self.workers)
        total_failed = sum(w.failed_count for w in self.workers)
        total_skipped = sum(w.skipped_count for w in self.workers)
        total_retry = sum(w.retry_count for w in self.workers)
        
        return {
            'worker_count': self.worker_count,
            'queue_size': self.message_queue.qsize(),
            'total_processed': total_processed,
            'total_failed': total_failed,
            'total_skipped': total_skipped,
            'total_retry': total_retry,
            'workers': [
                {
                    'id': i + 1,
                    'processed': w.processed_count,
                    'failed': w.failed_count,
                    'skipped': w.skipped_count,
                    'retry': w.retry_count
                }
                for i, w in enumerate(self.workers)
            ]
        }
    
    def print_stats(self):
        """打印队列统计信息"""
        stats = self.get_stats()
        
        logger.info("=" * 60)
        logger.info("📊 多 Worker 队列统计")
        logger.info("=" * 60)
        logger.info(f"Worker 数量: {stats['worker_count']}")
        logger.info(f"队列大小: {stats['queue_size']}")
        logger.info(f"总处理数: {stats['total_processed']}")
        logger.info(f"总失败数: {stats['total_failed']}")
        logger.info(f"总跳过数: {stats['total_skipped']}")
        logger.info(f"总重试数: {stats['total_retry']}")
        logger.info("\n各 Worker 统计:")
        for worker_stat in stats['workers']:
            logger.info(
                f"  Worker-{worker_stat['id']}: "
                f"处理={worker_stat['processed']}, "
                f"失败={worker_stat['failed']}, "
                f"跳过={worker_stat['skipped']}, "
                f"重试={worker_stat['retry']}"
            )
        logger.info("=" * 60)


# 使用示例
def create_multi_worker_queue(acc_client, worker_count: int = 4):
    """
    创建多 Worker 队列实例
    
    Args:
        acc_client: User 客户端实例
        worker_count: Worker 数量（默认 4）
        
    Returns:
        MultiWorkerQueue: 多 Worker 队列实例
    """
    return MultiWorkerQueue(acc_client, worker_count=worker_count)
