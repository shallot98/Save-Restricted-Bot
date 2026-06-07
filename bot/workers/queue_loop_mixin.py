"""Queue loop helpers for MessageWorker."""

import asyncio
import gc
import heapq
import logging
import queue
import time
from typing import Optional

from bot.utils.dedup import cleanup_old_messages
from constants import WORKER_STATS_INTERVAL

logger = logging.getLogger(__name__)


class QueueLoopMixin:
    """Provide queue polling, retry scheduling, and worker loop behavior."""

    def _defer_message(self, msg_obj) -> None:
        """将消息放入内部延迟队列（按 available_at 调度）。"""
        self._delayed_seq += 1
        heapq.heappush(self._delayed, (msg_obj.available_at, self._delayed_seq, msg_obj))

    def run(self):
        """主循环：持续处理队列消息"""
        self._start_worker_loop()
        gc_counter = 0

        while self.running:
            from_queue = False
            task_done_called = False
            try:
                msg_obj, from_queue, gc_counter = self._poll_next_message(gc_counter)
                if msg_obj is None:
                    continue

                self._log_message_received()
                if msg_obj.available_at > time.time():
                    task_done_called = self._defer_unready_message(msg_obj, from_queue)
                    continue

                result = self.process_message(msg_obj)
                self._handle_processing_result(result, msg_obj)
                self._record_message_metric(result)
            except Exception as e:
                self._track_worker_loop_error(e)
            finally:
                self._mark_queue_task_done(from_queue, task_done_called)

        self._close_worker_loop()

    def _start_worker_loop(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        logger.info("🔧 消息工作线程已启动（带事件循环）")

    def _poll_next_message(self, gc_counter: int) -> tuple[Optional[object], bool, int]:
        now = time.time()
        if self._delayed and self._delayed[0][0] <= now:
            _, _, msg_obj = heapq.heappop(self._delayed)
            return msg_obj, False, gc_counter

        timeout = 0.3
        if self._delayed:
            timeout = min(timeout, max(0.0, self._delayed[0][0] - now))

        try:
            return self.message_queue.get(timeout=timeout), True, gc_counter
        except queue.Empty:
            return None, False, self._maybe_log_idle_stats(gc_counter)

    def _maybe_log_idle_stats(self, gc_counter: int) -> int:
        if time.time() - self.last_stats_time <= WORKER_STATS_INTERVAL:
            return gc_counter

        queue_size = self.message_queue.qsize()
        delayed_size = len(self._delayed)
        if queue_size > 0 or delayed_size > 0 or self.processed_count > 0:
            logger.info(
                "📊 队列统计: "
                f"待处理={queue_size}, 延迟={delayed_size}, "
                f"已完成={self.processed_count}, 跳过={self.skipped_count}, "
                f"失败={self.failed_count}, 重试={self.retry_count}"
            )

        cleanup_old_messages()
        gc_counter = self._run_periodic_gc(gc_counter + 1)
        self.last_stats_time = time.time()
        return gc_counter

    @staticmethod
    def _run_periodic_gc(gc_counter: int) -> int:
        if gc_counter < 3:
            return gc_counter

        collected = gc.collect()
        logger.debug(f"🧹 强制垃圾回收: 回收了 {collected} 个对象")
        return 0

    def _log_message_received(self) -> None:
        queue_size = self.message_queue.qsize()
        delayed_size = len(self._delayed)
        logger.info(
            "📥 获取待处理消息 "
            f"(队列={queue_size}, 延迟={delayed_size}, "
            f"已处理={self.processed_count}, 跳过={self.skipped_count}, 失败={self.failed_count})"
        )

    def _defer_unready_message(self, msg_obj, from_queue: bool) -> bool:
        self._defer_message(msg_obj)
        if not from_queue:
            return False
        self.message_queue.task_done()
        return True

    def _handle_processing_result(self, result: str, msg_obj) -> None:
        if result == "success":
            self.processed_count += 1
            logger.info(f"✅ 消息处理成功 (总计: {self.processed_count})")
            msg_obj.message = None
            return

        if result == "skip":
            self.skipped_count += 1
            logger.info(f"⏭️ 消息已跳过 (总计: {self.skipped_count})")
            msg_obj.message = None
            return

        if result == "retry":
            self._handle_retry_result(msg_obj)

    def _handle_retry_result(self, msg_obj) -> None:
        if msg_obj.retry_count >= self.max_retries:
            self.failed_count += 1
            logger.error(f"❌ 消息处理最终失败，已达最大重试次数 (总失败: {self.failed_count})")
            msg_obj.message = None
            return

        msg_obj.retry_count += 1
        self.retry_count += 1
        backoff_time = self._get_backoff_time(msg_obj.retry_count)
        logger.warning(
            f"⚠️ 消息处理失败，将在 {backoff_time} 秒后重试 "
            f"(第 {msg_obj.retry_count}/{self.max_retries} 次)"
        )
        msg_obj.message = None
        msg_obj.available_at = max(msg_obj.available_at, time.time() + backoff_time)
        self._defer_message(msg_obj)
        logger.info("🔄 消息已加入延迟队列")

    @staticmethod
    def _record_message_metric(result: str) -> None:
        try:
            from src.infrastructure.monitoring.performance.business_metrics import get_business_metrics

            get_business_metrics().record_message_processed(
                success=result == "success",
                category="worker_message",
            )
        except Exception as metrics_err:
            logger.debug(f"业务指标上报失败（忽略，不影响主流程）: {metrics_err}")

    @staticmethod
    def _track_worker_loop_error(error: Exception) -> None:
        logger.error(f"⚠️ 工作线程异常: {error}", exc_info=True)
        try:
            from src.infrastructure.monitoring.errors.tracker import get_error_tracker

            get_error_tracker().track_error(
                error=error,
                context={"component": "message_worker", "stage": "outer_loop"},
            )
        except Exception as track_err:
            logger.debug(f"错误追踪上报失败（忽略，不影响主流程）: {track_err}")

    def _mark_queue_task_done(self, from_queue: bool, task_done_called: bool) -> None:
        if not from_queue or task_done_called:
            return
        try:
            self.message_queue.task_done()
        except ValueError:
            pass

    def _close_worker_loop(self) -> None:
        if self.loop:
            self.loop.close()
        logger.info("🛑 消息工作线程已停止")
