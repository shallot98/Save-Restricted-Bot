"""
Message queue worker thread
Processes messages from the queue and handles forwarding/recording

Architecture: Uses new layered architecture
- 服务由构造函数注入（main.py → bot.core.initialize_message_queue → MessageWorker）
- src/application/services for business logic
"""
import time
import os
import logging
import queue
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, Dict, Any
import pyrogram

# New architecture imports
from src.core.config import settings
from bot.workers.chain_forward_mixin import ChainForwardMixin
from bot.workers.errors import RetryLater, UnrecoverableError
from bot.workers.forwarding_mixin import ForwardingMixin
from bot.workers.message_loading_mixin import MessageLoadingMixin
from bot.workers.media_handling_mixin import MediaHandlingMixin
from bot.workers.processing_models import ForwardModeContext, RecordModeContext
from bot.workers.queue_loop_mixin import QueueLoopMixin
from bot.workers.record_mode_mixin import RecordModeMixin
from bot.workers.telegram_execution_mixin import TelegramExecutionMixin

if TYPE_CHECKING:
    from src.application.services import MessageWorkerService, WatchService

try:
    from src.infrastructure.monitoring.performance.decorators import monitor_performance
except Exception:
    def monitor_performance(*args, **kwargs):
        def _decorator(fn):
            return fn
        return _decorator

from constants import (
    MAX_RETRIES,
    get_backoff_time,
)

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """消息对象，封装消息元数据（优化：只保留必要数据，减少内存占用）"""
    user_id: str
    watch_key: str
    source_chat_id: str
    message_id: int
    watch_data: Dict[str, Any]
    dest_chat_id: Optional[str]
    message_text: str
    message: Optional[pyrogram.types.messages_and_media.message.Message] = None  # 重试时可按需重新获取
    available_at: float = field(default_factory=time.time)
    timestamp: float = field(default_factory=time.time)
    retry_count: int = 0
    media_group_key: Optional[str] = None

    def __post_init__(self):
        """优化：清理message对象中不必要的大型属性以减少内存"""
        # 注意：不能删除message对象本身，因为转发需要它
        # 但可以在处理完成后由worker清理
        pass


class MessageWorker(
    QueueLoopMixin,
    TelegramExecutionMixin,
    MessageLoadingMixin,
    ChainForwardMixin,
    ForwardingMixin,
    RecordModeMixin,
    MediaHandlingMixin,
):
    """消息工作线程，处理队列中的消息"""

    def __init__(
        self,
        message_queue: queue.Queue,
        acc_client,
        max_retries: int = MAX_RETRIES,
        *,
        message_service: Optional["MessageWorkerService"] = None,
        watch_service: Optional["WatchService"] = None,
    ):
        """构造 worker。

        ``message_service`` / ``watch_service`` 由组合根经 ``main.py`` →
        ``initialize_message_queue`` 注入。两者允许为 None 只是为了让不触碰服务的
        单测（重试退避、消息装载）能免装配构造；真正取用走下面的属性，未注入会
        立刻抛 RuntimeError，不静默回落到全局容器（§5.3 规则 5）。
        """
        self.__message_service = message_service
        self.__watch_service = watch_service
        self.message_queue = message_queue
        self.acc = acc_client
        self.max_retries = max_retries
        self.processed_count = 0
        self.failed_count = 0
        self.skipped_count = 0
        self.retry_count = 0
        self.running = True
        self.last_stats_time = time.time()
        self.loop = None
        self.thread: Optional[threading.Thread] = None
        self._delayed: list[tuple[float, int, Message]] = []
        self._delayed_seq: int = 0
        self._chain_max_hops = self._load_chain_max_hops()

        # 初始化存储管理器
        self.storage_manager = self._init_storage_manager()

    @staticmethod
    def _missing(name: str) -> RuntimeError:
        return RuntimeError(
            f"MessageWorker 未注入 {name}；"
            "请检查 main.py → initialize_message_queue 的装配路径"
        )

    @property
    def _message_service(self) -> "MessageWorkerService":
        """笔记落库与指标上报的编排服务（构造期注入）。"""
        if self.__message_service is None:
            raise self._missing("MessageWorkerService")
        return self.__message_service

    @property
    def _watch_service(self) -> "WatchService":
        """链式转发查询目标频道监控配置用（构造期注入）。"""
        if self.__watch_service is None:
            raise self._missing("WatchService")
        return self.__watch_service

    @staticmethod
    def _load_chain_max_hops() -> int:
        """读取链式转发最大跳数，防止多跳配置产生循环风暴。"""
        default_hops = 6
        raw = os.environ.get("CHAIN_FORWARD_MAX_HOPS")
        try:
            hops = int(raw) if raw is not None else default_hops
        except ValueError:
            hops = default_hops
        return max(1, min(hops, 20))

    @staticmethod
    def _get_backoff_time(retry_count: int) -> int:
        return get_backoff_time(retry_count)

    def _track_processing_error(self, error: Exception, msg_obj: Message) -> None:
        """Report processing errors without breaking the main retry flow."""
        self._message_service.track_processing_error(
            error,
            user_id=msg_obj.user_id,
            source_chat_id=msg_obj.source_chat_id,
            watch_key=msg_obj.watch_key,
        )

    @monitor_performance("worker.process_message")
    def process_message(self, msg_obj: Message) -> str:
        """处理单条消息

        Returns:
            "success": Message processed successfully
            "skip": Message skipped (filters or unrecoverable errors)
            "retry": Message failed but can be retried
        """
        try:
            return self._process_message_core(msg_obj)
        except RetryLater as e:
            return self._handle_retry_later(e, msg_obj)
        except UnrecoverableError as e:
            logger.warning(f"⚠️ 消息处理失败（不可恢复），跳过: {e}")
            return "skip"
        except (ValueError, KeyError) as e:
            return self._handle_lookup_processing_error(e, msg_obj)
        except Exception as e:
            return self._handle_unexpected_processing_error(e, msg_obj)

    def _process_message_core(self, msg_obj: Message) -> str:
        logger.info(f"⚙️ 开始处理消息: user={msg_obj.user_id}, source={msg_obj.source_chat_id}")
        logger.debug(
            f"   重试次数: {msg_obj.retry_count}, "
            f"消息文本: {msg_obj.message_text[:100] if msg_obj.message_text else 'None'}..."
        )

        message = self._ensure_message_loaded(msg_obj)
        task = self._message_service.build_watch_task(
            source_chat_id=msg_obj.source_chat_id,
            dest_chat_id=msg_obj.dest_chat_id,
            watch_data=msg_obj.watch_data,
        )

        if not self._message_service.should_process(task, msg_obj.message_text):
            logger.info("⏭️ 消息未通过过滤规则，已跳过")
            return "skip"

        logger.info("🎯 消息通过所有过滤规则，准备处理")
        if task.record_mode:
            return self._process_record_task(msg_obj, message, task)

        return self._process_forward_task(msg_obj, message, task)

    def _process_record_task(self, msg_obj: Message, message, task) -> str:
        return self._handle_record_mode(
            RecordModeContext(
                message=message,
                user_id=msg_obj.user_id,
                source_chat_id=msg_obj.source_chat_id,
                message_text=msg_obj.message_text,
                forward_mode=task.forward_mode,
                extract_patterns=task.extract_patterns,
            )
        )

    def _process_forward_task(self, msg_obj: Message, message, task) -> str:
        return self._handle_forward_mode(
            ForwardModeContext(
                message=message,
                dest_chat_id=task.dest,
                message_text=msg_obj.message_text,
                forward_mode=task.forward_mode,
                extract_patterns=task.extract_patterns,
                preserve_forward_source=task.preserve_forward_source,
                record_mode=task.record_mode,
            )
        )

    @staticmethod
    def _handle_retry_later(error: RetryLater, msg_obj: Message) -> str:
        msg_obj.available_at = max(msg_obj.available_at, time.time() + error.delay_seconds)
        logger.warning(f"⏳ 消息需延迟重试（{error.delay_seconds}秒）: {error.reason or str(error)}")
        return "retry"

    def _handle_lookup_processing_error(self, error: ValueError | KeyError, msg_obj: Message) -> str:
        error_msg = str(error)
        if "Peer id invalid" in error_msg or "ID not found" in error_msg:
            logger.warning(f"⚠️ 跳过无效的 Peer ID 错误: {error_msg}")
            return "skip"

        return self._handle_unexpected_processing_error(error, msg_obj)

    def _handle_unexpected_processing_error(self, error: Exception, msg_obj: Message) -> str:
        logger.error(f"❌ 处理消息时出错: {error}", exc_info=True)
        self._track_processing_error(error, msg_obj)
        return "retry"

    @property
    def delayed_count(self) -> int:
        """当前内部延迟（重试）队列长度。"""
        return len(self._delayed)

    def stop(self):
        """请求停止工作线程（不阻塞；主循环最多 0.3 秒内感知）"""
        self.running = False
        logger.info("🛑 正在停止消息工作线程...")

    def join_thread(self, timeout: float) -> bool:
        """等待工作线程退出。

        Returns:
            True 表示线程已退出（或从未启动），False 表示超时仍在运行。
        """
        thread = self.thread
        if thread is None or not thread.is_alive():
            return True

        thread.join(timeout=max(0.0, timeout))
        if thread.is_alive():
            logger.warning(f"⚠️ 工作线程 {thread.name} 未在 {timeout:.1f}s 内退出")
            return False
        return True

    def stop_and_join(self, timeout: float) -> bool:
        """停止工作线程并等待其退出。"""
        self.stop()
        return self.join_thread(timeout)
