"""
Message queue worker thread
Processes messages from the queue and handles forwarding/recording

Architecture: Uses new layered architecture
- src/core/container for service access
- src/application/services for business logic
"""
import time
import asyncio
import os
import heapq
import logging
import queue
import re
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime
from zoneinfo import ZoneInfo
import pyrogram
from pyrogram.errors import FloodWait

# New architecture imports
from src.core.container import get_note_service, get_watch_service
from src.core.config import settings
from src.core.exceptions import ValidationError
from src.compat.config_compat import MEDIA_DIR
from src.domain.entities.watch import WatchTask
from src.domain.services.filter_service import FilterService
from src.domain.entities.note import NoteCreate

try:
    from src.infrastructure.monitoring.performance.decorators import monitor_performance
except Exception:
    def monitor_performance(*args, **kwargs):
        def _decorator(fn):
            return fn
        return _decorator

# Legacy imports
from bot.filters import extract_content
from bot.storage.webdav_client import WebDAVClient, StorageManager
from bot.utils.dedup import cleanup_old_messages
from bot.utils.magnet_utils import MagnetLinkParser
from constants import (
    MAX_RETRIES, MAX_FLOOD_RETRIES, OPERATION_TIMEOUT,
    WORKER_STATS_INTERVAL, RATE_LIMIT_DELAY, get_backoff_time, MAX_MEDIA_PER_GROUP
)

logger = logging.getLogger(__name__)

# China timezone
CHINA_TZ = ZoneInfo("Asia/Shanghai")


class UnrecoverableError(Exception):
    """Exception for unrecoverable errors that should not be retried"""
    pass


class RetryLater(Exception):
    """Exception indicating the message should be retried after a delay."""

    def __init__(self, delay_seconds: float, reason: str = "") -> None:
        super().__init__(reason or f"retry later: {delay_seconds}s")
        self.delay_seconds = delay_seconds
        self.reason = reason


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


class MessageWorker:
    """消息工作线程，处理队列中的消息"""

    def __init__(self, message_queue: queue.Queue, acc_client, max_retries: int = MAX_RETRIES):
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
        self._delayed: list[tuple[float, int, Message]] = []
        self._delayed_seq: int = 0

        # 初始化存储管理器
        self.storage_manager = self._init_storage_manager()

    def _defer_message(self, msg_obj: Message) -> None:
        """将消息放入内部延迟队列（按 available_at 调度）。"""
        self._delayed_seq += 1
        heapq.heappush(self._delayed, (msg_obj.available_at, self._delayed_seq, msg_obj))

    def _init_storage_manager(self) -> StorageManager:
        """初始化存储管理器"""
        try:
            # 加载 WebDAV 配置
            webdav_config = settings.webdav_config

            # 如果启用了 WebDAV
            if webdav_config.get('enabled', False):
                url = webdav_config.get('url', '').strip()
                username = webdav_config.get('username', '').strip()
                password = webdav_config.get('password', '').strip()
                base_path = webdav_config.get('base_path', '/telegram_media')

                if url and username and password:
                    try:
                        webdav_client = WebDAVClient(url, username, password, base_path)

                        # 测试连接
                        if webdav_client.test_connection():
                            logger.info("✅ WebDAV 存储已启用")
                            return StorageManager(MEDIA_DIR, webdav_client)
                        else:
                            logger.warning("⚠️ WebDAV 连接测试失败，降级到本地存储")
                    except Exception as e:
                        logger.error(f"❌ WebDAV 初始化失败: {e}，降级到本地存储")
                else:
                    logger.warning("⚠️ WebDAV 配置不完整，使用本地存储")

            # 使用本地存储
            logger.info("📁 使用本地存储模式")
            return StorageManager(MEDIA_DIR)

        except Exception as e:
            logger.error(f"❌ 存储管理器初始化失败: {e}，使用本地存储")
            return StorageManager(MEDIA_DIR)

    def run(self):
        """主循环：持续处理队列消息"""
        import gc

        # Create event loop for this thread
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        logger.info("🔧 消息工作线程已启动（带事件循环）")

        # 优化：记录垃圾回收计数器
        gc_counter = 0

        while self.running:
            msg_obj: Optional[Message] = None
            from_queue = False
            task_done_called = False

            try:
                now = time.time()

                # 优先处理到期的延迟消息；否则阻塞等待队列或下一个延迟消息到期
                if self._delayed and self._delayed[0][0] <= now:
                    _, _, msg_obj = heapq.heappop(self._delayed)
                else:
                    timeout = 1.0
                    if self._delayed:
                        timeout = min(timeout, max(0.0, self._delayed[0][0] - now))

                    try:
                        msg_obj = self.message_queue.get(timeout=timeout)
                        from_queue = True
                    except queue.Empty:
                        # Periodically log statistics and cleanup
                        if time.time() - self.last_stats_time > WORKER_STATS_INTERVAL:
                            queue_size = self.message_queue.qsize()
                            delayed_size = len(self._delayed)
                            if queue_size > 0 or delayed_size > 0 or self.processed_count > 0:
                                logger.info(
                                    "📊 队列统计: "
                                    f"待处理={queue_size}, 延迟={delayed_size}, "
                                    f"已完成={self.processed_count}, 跳过={self.skipped_count}, "
                                    f"失败={self.failed_count}, 重试={self.retry_count}"
                                )

                            # 清理过期的消息缓存，防止内存泄漏
                            cleanup_old_messages()

                            # 优化：定期强制垃圾回收（每3个清理周期）
                            gc_counter += 1
                            if gc_counter >= 3:
                                collected = gc.collect()
                                logger.debug(f"🧹 强制垃圾回收: 回收了 {collected} 个对象")
                                gc_counter = 0

                            self.last_stats_time = time.time()
                        continue

                if msg_obj is None:
                    continue

                # 记录队列统计信息
                queue_size = self.message_queue.qsize()
                delayed_size = len(self._delayed)
                logger.info(
                    "📥 获取待处理消息 "
                    f"(队列={queue_size}, 延迟={delayed_size}, "
                    f"已处理={self.processed_count}, 跳过={self.skipped_count}, 失败={self.failed_count})"
                )

                # 未到执行时间：放入延迟队列，避免在有 maxsize 队列下 requeue 阻塞
                now = time.time()
                if msg_obj.available_at > now:
                    self._defer_message(msg_obj)
                    if from_queue:
                        self.message_queue.task_done()
                        task_done_called = True
                    continue

                # 处理消息
                result = self.process_message(msg_obj)

                if result == "success":
                    self.processed_count += 1
                    logger.info(f"✅ 消息处理成功 (总计: {self.processed_count})")
                    msg_obj.message = None
                elif result == "skip":
                    self.skipped_count += 1
                    logger.info(f"⏭️ 消息已跳过 (总计: {self.skipped_count})")
                    msg_obj.message = None
                elif result == "retry":
                    # 失败处理：延迟重试或放弃
                    if msg_obj.retry_count < self.max_retries:
                        msg_obj.retry_count += 1
                        self.retry_count += 1
                        backoff_time = get_backoff_time(msg_obj.retry_count)
                        logger.warning(
                            f"⚠️ 消息处理失败，将在 {backoff_time} 秒后重试 "
                            f"(第 {msg_obj.retry_count}/{self.max_retries} 次)"
                        )
                        msg_obj.message = None
                        desired_available_at = time.time() + backoff_time
                        if msg_obj.available_at < desired_available_at:
                            msg_obj.available_at = desired_available_at
                        self._defer_message(msg_obj)
                        logger.info("🔄 消息已加入延迟队列")
                    else:
                        self.failed_count += 1
                        logger.error(
                            f"❌ 消息处理最终失败，已达最大重试次数 (总失败: {self.failed_count})"
                        )
                        msg_obj.message = None

                try:
                    from src.infrastructure.monitoring.performance.business_metrics import get_business_metrics

                    get_business_metrics().record_message_processed(
                        success=result == "success",
                        category="worker_message",
                    )
                except Exception as metrics_err:
                    logger.debug(f"业务指标上报失败（忽略，不影响主流程）: {metrics_err}")

            except Exception as e:
                logger.error(f"⚠️ 工作线程异常: {e}", exc_info=True)
                try:
                    from src.infrastructure.monitoring.errors.tracker import get_error_tracker

                    get_error_tracker().track_error(
                        error=e,
                        context={"component": "message_worker", "stage": "outer_loop"},
                    )
                except Exception as track_err:
                    logger.debug(f"错误追踪上报失败（忽略，不影响主流程）: {track_err}")
            finally:
                if from_queue and not task_done_called:
                    try:
                        self.message_queue.task_done()
                    except ValueError:
                        pass
        
        # Clean up event loop
        if self.loop:
            self.loop.close()
        logger.info("🛑 消息工作线程已停止")
    
    def _run_async_with_timeout(self, coro, timeout: float = OPERATION_TIMEOUT):
        """Execute async operation with timeout in the worker thread"""
        # Validate that we have a proper coroutine or awaitable
        if not asyncio.iscoroutine(coro) and not hasattr(coro, '__await__'):
            error_msg = f"Expected coroutine or awaitable, got {type(coro).__name__}"
            logger.error(f"❌ {error_msg}")
            raise TypeError(error_msg)
        
        # Ensure event loop exists and is valid
        if not self.loop or self.loop.is_closed():
            error_msg = "Event loop not available or closed"
            logger.error(f"❌ {error_msg}")
            raise RuntimeError(error_msg)
        
        try:
            return self.loop.run_until_complete(
                asyncio.wait_for(coro, timeout=timeout)
            )
        except asyncio.TimeoutError:
            logger.error(f"❌ 操作超时（{timeout}秒）")
            raise

    @staticmethod
    def _coerce_chat_id(chat_id: str):
        """将 chat_id 规范为 Pyrogram 可接受的类型（int 或字符串）。"""
        if chat_id == "me":
            return "me"
        try:
            return int(chat_id)
        except Exception:
            return chat_id

    def _ensure_message_loaded(self, msg_obj: Message):
        """确保 msg_obj.message 可用于处理（重试时按需重新获取）。"""
        if msg_obj.message is not None:
            if not msg_obj.message_text:
                msg_obj.message_text = msg_obj.message.text or msg_obj.message.caption or ""
                if (
                    self.acc
                    and not msg_obj.message_text
                    and getattr(msg_obj.message, "media_group_id", None)
                ):
                    chat_id = self._coerce_chat_id(msg_obj.source_chat_id)
                    try:
                        media_group = self._execute_with_flood_retry(
                            "获取媒体组文本",
                            lambda: self.acc.get_media_group(chat_id, msg_obj.message_id),
                        )
                        if media_group:
                            first = media_group[0]
                            msg_obj.message_text = first.text or first.caption or ""
                    except RetryLater:
                        raise
                    except Exception as e:
                        logger.debug(f"📸 获取媒体组文本失败: {e}")
            return msg_obj.message

        if not self.acc:
            raise UnrecoverableError("User client 未初始化，无法重新获取消息")

        chat_id = self._coerce_chat_id(msg_obj.source_chat_id)
        try:
            from bot.services.peer_cache import cache_peer_if_needed

            if chat_id != "me":
                cache_peer_if_needed(self.acc, chat_id, "源频道")
        except Exception as e:
            logger.debug(f"源频道 Peer 缓存预热失败（忽略，不影响主流程）: {e}")
        fetched = self._execute_with_flood_retry(
            "重新获取消息",
            lambda: self.acc.get_messages(chat_id, msg_obj.message_id),
        )

        if isinstance(fetched, list):
            fetched = fetched[0] if fetched else None

        if not fetched:
            raise UnrecoverableError(f"无法重新获取消息: {msg_obj.source_chat_id}/{msg_obj.message_id}")

        msg_obj.message = fetched

        if not msg_obj.message_text:
            msg_obj.message_text = fetched.text or fetched.caption or ""
            if not msg_obj.message_text and getattr(fetched, "media_group_id", None):
                media_group = self._execute_with_flood_retry(
                    "获取媒体组文本",
                    lambda: self.acc.get_media_group(chat_id, msg_obj.message_id),
                )
                if media_group:
                    first = media_group[0]
                    msg_obj.message_text = first.text or first.caption or ""

        return fetched
    
    def _execute_with_flood_retry(self, operation_name: str, operation_func, max_flood_retries: int = MAX_FLOOD_RETRIES, timeout: float = OPERATION_TIMEOUT):
        """Execute operation with FloodWait retry and timeout handling

        Returns:
            操作的返回结果（消息对象或消息ID列表）
        """
        for flood_attempt in range(max_flood_retries):
            try:
                result = operation_func()
                # Check if result is a coroutine (async operation)
                if asyncio.iscoroutine(result):
                    result = self._run_async_with_timeout(result, timeout=timeout)
                return result
            except FloodWait as e:
                wait_time = e.value
                if flood_attempt < max_flood_retries - 1:
                    logger.warning(f"⏳ {operation_name}: 遇到限流 FLOOD_WAIT, 需等待 {wait_time} 秒")
                    logger.info(f"   将在 {wait_time + 1} 秒后重试 (FloodWait 重试 {flood_attempt + 1}/{max_flood_retries})")
                    raise RetryLater(wait_time + 1, reason=f"{operation_name}: FLOOD_WAIT")
                else:
                    logger.error(f"❌ {operation_name}: FloodWait 重试次数已达上限，放弃操作")
                    raise UnrecoverableError(f"FloodWait retry limit exceeded for {operation_name}")
            except asyncio.TimeoutError:
                logger.error(f"❌ {operation_name}: 操作超时（{timeout}秒），跳过此消息")
                raise UnrecoverableError(f"Timeout ({timeout}s) for {operation_name}")
            except TypeError as e:
                error_msg = str(e)
                if "coroutine" in error_msg.lower() or "awaitable" in error_msg.lower():
                    logger.error(f"❌ {operation_name}: 异步执行错误: {error_msg}")
                    raise UnrecoverableError(f"Async execution error for {operation_name}: {error_msg}")
                else:
                    logger.error(f"❌ {operation_name} 执行失败: {type(e).__name__}: {e}")
                    raise
            except (ValueError, KeyError) as e:
                error_msg = str(e)
                if "Peer id invalid" in error_msg or "ID not found" in error_msg:
                    logger.warning(f"⚠️ {operation_name}: Peer ID 无效，跳过: {error_msg}")
                    raise UnrecoverableError(f"Invalid Peer ID: {error_msg}")
                else:
                    logger.error(f"❌ {operation_name} 执行失败: {type(e).__name__}: {e}")
                    raise
            except Exception as e:
                logger.error(f"❌ {operation_name} 执行失败: {type(e).__name__}: {e}")
                raise
        raise UnrecoverableError(f"Operation {operation_name} failed after {max_flood_retries} FloodWait retries")
    
    @monitor_performance("worker.process_message")
    def process_message(self, msg_obj: Message) -> str:
        """处理单条消息
        
        Returns:
            "success": Message processed successfully
            "skip": Message skipped (filters or unrecoverable errors)
            "retry": Message failed but can be retried
        """
        try:
            logger.info(f"⚙️ 开始处理消息: user={msg_obj.user_id}, source={msg_obj.source_chat_id}")
            logger.debug(f"   重试次数: {msg_obj.retry_count}, 消息文本: {msg_obj.message_text[:100] if msg_obj.message_text else 'None'}...")
            
            message = self._ensure_message_loaded(msg_obj)
            watch_data = msg_obj.watch_data
            user_id = msg_obj.user_id
            source_chat_id = msg_obj.source_chat_id
            dest_chat_id = msg_obj.dest_chat_id
            message_text = msg_obj.message_text
            
            # 提取配置
            whitelist = watch_data.get("whitelist", [])
            blacklist = watch_data.get("blacklist", [])
            whitelist_regex = watch_data.get("whitelist_regex", [])
            blacklist_regex = watch_data.get("blacklist_regex", [])
            preserve_forward_source = watch_data.get("preserve_forward_source", False)
            forward_mode = watch_data.get("forward_mode", "full")
            extract_patterns = watch_data.get("extract_patterns", [])
            record_mode = watch_data.get("record_mode", False)
            # 已删除 append_dn 配置（不再使用DN补全功能）
            
            # 再次验证过滤规则（防止配置在入队后被修改）
            task = WatchTask(
                source=str(source_chat_id),
                dest=dest_chat_id,
                whitelist=whitelist,
                blacklist=blacklist,
                whitelist_regex=whitelist_regex,
                blacklist_regex=blacklist_regex,
                preserve_forward_source=preserve_forward_source,
                forward_mode=forward_mode,
                extract_patterns=extract_patterns,
                record_mode=record_mode,
            )

            if not FilterService.should_forward(task, message_text):
                logger.info("⏭️ 消息未通过过滤规则，已跳过")
                return "skip"
            
            logger.info(f"🎯 消息通过所有过滤规则，准备处理")
            
            # Record mode - save to database
            if record_mode:
                return self._handle_record_mode(message, user_id, source_chat_id, message_text, forward_mode, extract_patterns)
            
            # Forward mode
            else:
                return self._handle_forward_mode(message, dest_chat_id, message_text, forward_mode, extract_patterns, preserve_forward_source, record_mode)
            
        except RetryLater as e:
            msg_obj.available_at = max(msg_obj.available_at, time.time() + e.delay_seconds)
            logger.warning(f"⏳ 消息需延迟重试（{e.delay_seconds}秒）: {e.reason or str(e)}")
            return "retry"
        except UnrecoverableError as e:
            logger.warning(f"⚠️ 消息处理失败（不可恢复），跳过: {e}")
            return "skip"
        except (ValueError, KeyError) as e:
            error_msg = str(e)
            if "Peer id invalid" in error_msg or "ID not found" in error_msg:
                logger.warning(f"⚠️ 跳过无效的 Peer ID 错误: {error_msg}")
                return "skip"
            else:
                logger.error(f"❌ 处理消息时出错: {type(e).__name__}: {e}", exc_info=True)
                try:
                    from src.infrastructure.monitoring.errors.tracker import get_error_tracker

                    get_error_tracker().track_error(
                        error=e,
                        context={
                            "component": "message_worker",
                            "stage": "process_message",
                            "user_id": msg_obj.user_id,
                            "source_chat_id": msg_obj.source_chat_id,
                            "watch_key": msg_obj.watch_key,
                        },
                    )
                except Exception as track_err:
                    logger.debug(f"错误追踪上报失败（忽略，不影响主流程）: {track_err}")
                return "retry"
        except Exception as e:
            logger.error(f"❌ 处理消息时出错: {e}", exc_info=True)
            try:
                from src.infrastructure.monitoring.errors.tracker import get_error_tracker

                get_error_tracker().track_error(
                    error=e,
                    context={
                        "component": "message_worker",
                        "stage": "process_message",
                        "user_id": msg_obj.user_id,
                        "source_chat_id": msg_obj.source_chat_id,
                        "watch_key": msg_obj.watch_key,
                    },
                )
            except Exception as track_err:
                logger.debug(f"错误追踪上报失败（忽略，不影响主流程）: {track_err}")
            return "retry"
    
    @monitor_performance("worker.handle_record_mode")
    def _handle_record_mode(self, message, user_id, source_chat_id, message_text, forward_mode, extract_patterns):
        """Handle record mode processing"""
        logger.info(f"📝 记录模式：开始处理消息")
        logger.info(f"   来源: {source_chat_id} ({getattr(message.chat, 'title', None) or getattr(message.chat, 'username', None)})")
        source_name = message.chat.title or message.chat.username or source_chat_id
        
        # Handle text content with extraction
        content_to_save = message_text
        logger.debug(f"   原始内容长度: {len(message_text)}")
        
        if forward_mode == "extract" and extract_patterns:
            content_to_save = extract_content(message_text, extract_patterns)
        
        # Handle media
        media_type = None
        media_path = None
        media_paths = []
        
        logger.debug(f"   开始处理媒体")
        
        # Check if this is a media group (multiple images)
        if message.media_group_id:
            media_type, media_path, media_paths, content_to_save = self._handle_media_group(message, content_to_save)
        
        # Single photo
        elif message.photo:
            media_type, media_path, media_paths = self._handle_single_photo(message)
        
        # Single video
        elif message.video:
            media_type, media_path, media_paths = self._handle_single_video(message)
        
        # Single animation (GIF)
        elif message.animation:
            media_type, media_path, media_paths = self._handle_single_animation(message)
        
        # Save to database
        logger.info(f"💾 记录模式：准备保存笔记到数据库")
        logger.info(f"   - 用户ID: {user_id}")
        logger.info(f"   - 来源: {source_name} ({source_chat_id})")
        logger.info(f"   - 文本: {bool(content_to_save)} ({len(content_to_save) if content_to_save else 0} 字符)")
        logger.info(f"   - 媒体类型: {media_type}")
        logger.info(f"   - 媒体数量: {len(media_paths)} 个")
        logger.info(f"   - 媒体组ID: {message.media_group_id if message.media_group_id else 'None'}")
        
        try:
            note_service = get_note_service()

            note_dto = note_service.create_note(
                NoteCreate(
                    user_id=int(user_id),
                    source_chat_id=source_chat_id,
                    source_name=source_name,
                    message_text=content_to_save if content_to_save else None,
                    media_type=media_type,
                    media_path=media_path,
                    media_paths=media_paths if media_paths else None,
                    media_group_id=str(message.media_group_id) if message.media_group_id else None,
                )
            )

            note_id = note_dto.id

            magnet_link = (
                MagnetLinkParser.extract_magnet_from_text(content_to_save)
                if content_to_save
                else None
            )
            if magnet_link:
                note_service.update_magnet(note_id, magnet_link, filename=None)

            logger.info(f"✅ 记录模式：笔记保存成功！笔记ID: {note_id}")
            try:
                from src.infrastructure.monitoring.performance.business_metrics import get_business_metrics

                get_business_metrics().record_note_saved(
                    success=True,
                    has_media=bool(media_type),
                )
            except Exception as metrics_err:
                logger.debug(f"业务指标上报失败（忽略，不影响主流程）: {metrics_err}")
            return "success"
        except ValidationError as e:
            if "Duplicate" in str(e):
                logger.info("⏭️ 记录模式：检测到重复笔记，已跳过写入")
                return "success"
            raise
        except Exception as e:
            logger.error(f"❌ 记录模式：保存笔记失败！", exc_info=True)
            try:
                from src.infrastructure.monitoring.performance.business_metrics import get_business_metrics

                get_business_metrics().record_note_saved(
                    success=False,
                    has_media=bool(media_type),
                    error_type=type(e).__name__,
                )
            except Exception as metrics_err:
                logger.debug(f"业务指标上报失败（忽略，不影响主流程）: {metrics_err}")
            raise
    
    def _download_and_save_media(self, file_id: str, file_name: str, keep_local: bool) -> tuple[bool, Optional[str]]:
        """下载并保存单个媒体文件

        Args:
            file_id: Telegram 文件 ID
            file_name: 保存的文件名
            keep_local: 是否保留本地副本

        Returns:
            (success, storage_location): 是否成功和存储位置
        """
        file_path = os.path.join(MEDIA_DIR, file_name)
        try:
            self.acc.download_media(file_id, file_name=file_path)
            return self.storage_manager.save_file(file_path, file_name, keep_local=keep_local)
        except Exception as e:
            logger.error(f"      ❌ 下载媒体失败: {e}")
            return False, None

    def _process_single_media_in_group(self, msg, idx: int, keep_local: bool,
                                       media_type: Optional[str]) -> tuple[Optional[str], bool, Optional[str]]:
        """处理媒体组中的单个媒体

        Args:
            msg: 媒体消息对象
            idx: 媒体索引
            keep_local: 是否保留本地副本
            media_type: 当前媒体类型

        Returns:
            (media_type, saved, storage_location): 媒体类型、是否保存成功、存储位置
        """
        timestamp = datetime.now(CHINA_TZ).strftime('%Y%m%d_%H%M%S')

        # 处理图片
        if msg.photo:
            file_name = f"{msg.id}_{idx}_{timestamp}.jpg"
            success, location = self._download_and_save_media(msg.photo.file_id, file_name, keep_local)
            if success:
                logger.debug(f"      ✅ 保存图片: {file_name}")
            return "photo", success, location

        # 处理视频缩略图
        if msg.video:
            new_type = media_type or "video"
            if msg.video.thumbs and len(msg.video.thumbs) > 0:
                thumb = msg.video.thumbs[-1]
                file_name = f"{msg.id}_{idx}_thumb_{timestamp}.jpg"
                success, location = self._download_and_save_media(thumb.file_id, file_name, keep_local)
                if success:
                    logger.debug(f"      ✅ 保存视频缩略图: {file_name}")
                return new_type, success, location
            return new_type, False, None

        # 处理 GIF 动图缩略图
        if msg.animation:
            new_type = media_type or "animation"
            if msg.animation.thumbs and len(msg.animation.thumbs) > 0:
                thumb = msg.animation.thumbs[-1]
                file_name = f"{msg.id}_{idx}_gif_thumb_{timestamp}.jpg"
                success, location = self._download_and_save_media(thumb.file_id, file_name, keep_local)
                if success:
                    logger.debug(f"      ✅ 保存GIF缩略图: {file_name}")
                return new_type, success, location
            return new_type, False, None

        return media_type, False, None

    def _handle_media_group(self, message, content_to_save):
        """Handle media group download"""
        media_type = None
        media_path = None
        media_paths = []

        webdav_config = settings.webdav_config
        keep_local = webdav_config.get('keep_local_copy', False)

        try:
            media_group = self.acc.get_media_group(message.chat.id, message.id)
            if not media_group:
                raise Exception("无法获取媒体组")

            logger.info(f"   📷 发现媒体组，共 {len(media_group)} 个媒体")

            for idx, msg in enumerate(media_group):
                # 处理单个媒体
                media_type, saved, storage_location = self._process_single_media_in_group(
                    msg, idx, keep_local, media_type
                )

                if saved and storage_location:
                    media_paths.append(storage_location)
                    if idx == 0:
                        media_path = storage_location
                else:
                    logger.warning(f"      ⚠️ 媒体 {idx+1} 类型不支持或无缩略图")

                # 检查媒体数量限制
                if len(media_paths) >= MAX_MEDIA_PER_GROUP:
                    logger.warning(f"   ⚠️ 媒体组超过{MAX_MEDIA_PER_GROUP}个，仅保存前{MAX_MEDIA_PER_GROUP}个")
                    break

                # 提取 caption
                if msg.caption and not content_to_save:
                    content_to_save = msg.caption

            logger.info(f"   ✅ 媒体组处理完成，共保存 {len(media_paths)} 个文件")

        except Exception as e:
            logger.error(f"   ❌ 获取媒体组失败: {e}", exc_info=True)
            if message.photo:
                media_type, media_path, media_paths = self._handle_single_photo(message)

        return media_type, media_path, media_paths, content_to_save
    
    def _handle_single_photo(self, message):
        """Handle single photo download"""
        logger.info(f"   📷 处理单张图片")
        media_type = "photo"
        file_name = f"{message.id}_{datetime.now(CHINA_TZ).strftime('%Y%m%d_%H%M%S')}.jpg"
        file_path = os.path.join(MEDIA_DIR, file_name)

        # 下载到本地临时文件
        self.acc.download_media(message.photo.file_id, file_name=file_path)

        # 使用存储管理器保存
        webdav_config = settings.webdav_config
        keep_local = webdav_config.get('keep_local_copy', False)
        success, storage_location = self.storage_manager.save_file(file_path, file_name, keep_local=keep_local)

        if success:
            return media_type, storage_location, [storage_location]
        else:
            logger.warning(f"⚠️ 存储失败，使用本地路径: {file_name}")
            return media_type, file_name, [file_name]
    
    def _handle_single_video(self, message):
        """Handle single video thumbnail download"""
        logger.info(f"   📹 处理视频消息")
        media_type = "video"
        media_path = None
        media_paths = []

        try:
            if message.video.thumbs and len(message.video.thumbs) > 0:
                thumb = message.video.thumbs[-1]
                file_name = f"{message.id}_{datetime.now(CHINA_TZ).strftime('%Y%m%d_%H%M%S')}_thumb.jpg"
                file_path = os.path.join(MEDIA_DIR, file_name)

                # 下载到本地临时文件
                self.acc.download_media(thumb.file_id, file_name=file_path)

                # 使用存储管理器保存
                webdav_config = settings.webdav_config
                keep_local = webdav_config.get('keep_local_copy', False)
                success, storage_location = self.storage_manager.save_file(file_path, file_name, keep_local=keep_local)

                if success:
                    media_path = storage_location
                    media_paths = [storage_location]
                else:
                    media_path = f"local:{file_name}"
                    media_paths = [media_path]

                logger.info(f"   ✅ 视频缩略图已保存")
            else:
                logger.warning(f"   ⚠️ 视频没有缩略图")
        except Exception as e:
            logger.warning(f"   ⚠️ 下载视频缩略图失败: {e}")

        return media_type, media_path, media_paths
    
    def _handle_single_animation(self, message):
        """Handle single GIF animation thumbnail download"""
        logger.info(f"   🎞️ 处理GIF动图消息")
        media_type = "animation"
        media_path = None
        media_paths = []

        try:
            if message.animation.thumbs and len(message.animation.thumbs) > 0:
                thumb = message.animation.thumbs[-1]
                file_name = f"{message.id}_{datetime.now(CHINA_TZ).strftime('%Y%m%d_%H%M%S')}_gif_thumb.jpg"
                file_path = os.path.join(MEDIA_DIR, file_name)

                # 下载到本地临时文件
                self.acc.download_media(thumb.file_id, file_name=file_path)

                # 使用存储管理器保存
                webdav_config = settings.webdav_config
                keep_local = webdav_config.get('keep_local_copy', False)
                success, storage_location = self.storage_manager.save_file(file_path, file_name, keep_local=keep_local)

                if success:
                    media_path = storage_location
                    media_paths = [storage_location]
                else:
                    media_path = f"local:{file_name}"
                    media_paths = [media_path]

                logger.info(f"   ✅ GIF缩略图已保存")
            else:
                logger.warning(f"   ⚠️ GIF动图没有缩略图")
        except Exception as e:
            logger.warning(f"   ⚠️ 下载GIF缩略图失败: {e}")

        return media_type, media_path, media_paths
    
    @monitor_performance("worker.handle_forward_mode")
    def _handle_forward_mode(self, message, dest_chat_id, message_text, forward_mode, extract_patterns, preserve_forward_source, record_mode):
        """Handle forward mode processing"""
        logger.info(f"📤 转发模式：开始处理，目标: {dest_chat_id}")

        if not dest_chat_id:
            raise UnrecoverableError("目标频道为空，无法转发")

        # 目标 Peer 缓存由 worker 负责，避免在回调线程进行重操作
        if dest_chat_id != "me":
            if not self._ensure_peer_cached(str(dest_chat_id)):
                raise UnrecoverableError(f"目标 Peer 缓存失败: {dest_chat_id}")

        # 用于存储转发后的新消息ID(用于链式转发)
        forwarded_message_id = None

        try:
            # Extract mode
            if forward_mode == "extract" and extract_patterns:
                extracted_text = extract_content(message_text, extract_patterns)

                if extracted_text:
                    logger.info(f"   提取到内容，准备发送")
                    dest_id = "me" if dest_chat_id == "me" else int(dest_chat_id)
                    sent_msg = self._execute_with_flood_retry(
                        "发送提取内容",
                        lambda: self.acc.send_message(dest_id, extracted_text)
                    )
                    if sent_msg:
                        forwarded_message_id = sent_msg.id if hasattr(sent_msg, 'id') else None
                    logger.info(f"   ✅ 提取内容已发送")
                    time.sleep(RATE_LIMIT_DELAY)
                else:
                    logger.debug(f"   未提取到任何内容，跳过发送")

            # Full forward mode
            else:
                dest_id = "me" if dest_chat_id == "me" else int(dest_chat_id)

                # 正常转发（已删除DN补全功能）
                if preserve_forward_source:
                    forwarded_message_id = self._forward_with_source(message, dest_id)
                else:
                    forwarded_message_id = self._copy_without_source(message, dest_id)

            try:
                from src.infrastructure.monitoring.performance.business_metrics import get_business_metrics

                get_business_metrics().record_forward(
                    success=True,
                    preserve_source=bool(preserve_forward_source),
                )
            except Exception as metrics_err:
                logger.debug(f"业务指标上报失败（忽略，不影响主流程）: {metrics_err}")

        except Exception as e:
            try:
                from src.infrastructure.monitoring.performance.business_metrics import get_business_metrics

                get_business_metrics().record_forward(
                    success=False,
                    preserve_source=bool(preserve_forward_source),
                    error_type=type(e).__name__,
                )
            except Exception as metrics_err:
                logger.debug(f"业务指标上报失败（忽略，不影响主流程）: {metrics_err}")
            raise

        # 检查目标频道是否也是监控源，如果是则手动触发其配置
        if not record_mode and dest_chat_id and dest_chat_id != "me" and forwarded_message_id:
            text_for_chain = message_text
            self._trigger_dest_monitoring(dest_chat_id, forwarded_message_id, text_for_chain)

        return "success"

    def _forward_with_source(self, message, dest_id):
        """Forward message preserving source

        Returns:
            转发后的第一条消息ID（用于链式转发）
        """
        logger.debug(f"   保留转发来源")
        forwarded_msg_id = None

        if message.media_group_id:
            try:
                media_group = self.acc.get_media_group(message.chat.id, message.id)
                message_ids = [msg.id for msg in media_group] if media_group else [message.id]
                result = self._execute_with_flood_retry(
                    "转发媒体组",
                    lambda: self.acc.forward_messages(dest_id, message.chat.id, message_ids)
                )
                # forward_messages 返回消息列表，取第一个
                if result:
                    if isinstance(result, list) and len(result) > 0:
                        forwarded_msg_id = result[0].id if hasattr(result[0], 'id') else result[0]
                    else:
                        forwarded_msg_id = result.id if hasattr(result, 'id') else result
                logger.info(f"   ✅ 媒体组已转发")
                time.sleep(RATE_LIMIT_DELAY)
            except UnrecoverableError:
                raise
            except Exception as e:
                logger.warning(f"   转发媒体组失败，回退到单条转发: {e}")
                result = self._execute_with_flood_retry(
                    "转发单条消息",
                    lambda: self.acc.forward_messages(dest_id, message.chat.id, message.id)
                )
                if result:
                    if isinstance(result, list) and len(result) > 0:
                        forwarded_msg_id = result[0].id if hasattr(result[0], 'id') else result[0]
                    else:
                        forwarded_msg_id = result.id if hasattr(result, 'id') else result
                logger.info(f"   ✅ 消息已转发（单条）")
                time.sleep(RATE_LIMIT_DELAY)
        else:
            result = self._execute_with_flood_retry(
                "转发消息",
                lambda: self.acc.forward_messages(dest_id, message.chat.id, message.id)
            )
            if result:
                if isinstance(result, list) and len(result) > 0:
                    forwarded_msg_id = result[0].id if hasattr(result[0], 'id') else result[0]
                else:
                    forwarded_msg_id = result.id if hasattr(result, 'id') else result
            logger.info(f"   ✅ 消息已转发")
            time.sleep(RATE_LIMIT_DELAY)

        return forwarded_msg_id
    
    def _copy_without_source(self, message, dest_id):
        """Copy message hiding source

        Returns:
            复制后的第一条消息ID（用于链式转发）
        """
        logger.debug(f"   隐藏转发来源")
        forwarded_msg_id = None

        if message.media_group_id:
            try:
                result = self._execute_with_flood_retry(
                    "复制媒体组",
                    lambda: self.acc.copy_media_group(dest_id, message.chat.id, message.id)
                )
                # copy_media_group 返回消息列表，取第一个
                if result:
                    if isinstance(result, list) and len(result) > 0:
                        forwarded_msg_id = result[0].id if hasattr(result[0], 'id') else result[0]
                    else:
                        forwarded_msg_id = result.id if hasattr(result, 'id') else result
                logger.info(f"   ✅ 媒体组已复制（隐藏引用）")
                time.sleep(RATE_LIMIT_DELAY)
            except UnrecoverableError:
                raise
            except Exception as e:
                logger.warning(f"   复制媒体组失败，回退到复制单条: {e}")
                result = self._execute_with_flood_retry(
                    "复制单条消息",
                    lambda: self.acc.copy_message(dest_id, message.chat.id, message.id)
                )
                if result:
                    forwarded_msg_id = result.id if hasattr(result, 'id') else result
                logger.info(f"   ✅ 消息已复制（单条）")
                time.sleep(RATE_LIMIT_DELAY)
        else:
            result = self._execute_with_flood_retry(
                "复制消息",
                lambda: self.acc.copy_message(dest_id, message.chat.id, message.id)
            )
            if result:
                forwarded_msg_id = result.id if hasattr(result, 'id') else result
            logger.info(f"   ✅ 消息已复制")
            time.sleep(RATE_LIMIT_DELAY)

        return forwarded_msg_id

    def _get_forwarded_message(self, dest_chat_id: str, forwarded_message_id: int):
        """获取转发后的消息对象

        Args:
            dest_chat_id: 目标频道 ID
            forwarded_message_id: 转发后的消息 ID

        Returns:
            消息对象，失败返回 None
        """
        try:
            dest_id = int(dest_chat_id)
            # 使用 _execute_with_flood_retry 包装，添加 FloodWait 重试机制
            forwarded_message = self._execute_with_flood_retry(
                "获取转发后的消息",
                lambda: self.acc.get_messages(dest_id, forwarded_message_id)
            )
            if forwarded_message:
                logger.debug(f"   成功获取转发后的消息对象: chat_id={forwarded_message.chat.id}, message_id={forwarded_message.id}")
            return forwarded_message
        except UnrecoverableError as e:
            logger.warning(f"   ⚠️ 获取转发后的消息对象失败（不可恢复）: {e}")
            return None
        except Exception as e:
            logger.error(f"   ❌ 获取转发后的消息对象失败: {e}")
            return None

    def _apply_chain_filters(self, message_text: str, watch_data: dict) -> bool:
        """应用链式转发的过滤规则

        Args:
            message_text: 消息文本
            watch_data: 监控配置

        Returns:
            bool: 是否通过过滤
        """
        task = WatchTask(
            source=str(watch_data.get("source") or ""),
            dest=watch_data.get("dest"),
            whitelist=watch_data.get("whitelist", []),
            blacklist=watch_data.get("blacklist", []),
            whitelist_regex=watch_data.get("whitelist_regex", []),
            blacklist_regex=watch_data.get("blacklist_regex", []),
            preserve_forward_source=bool(watch_data.get("preserve_forward_source", False)),
            forward_mode=watch_data.get("forward_mode", "full"),
            extract_patterns=watch_data.get("extract_patterns", []),
            record_mode=bool(watch_data.get("record_mode", False)),
        )

        if not FilterService.should_forward(task, message_text):
            logger.debug("   ⏭️ 目标频道配置：未通过过滤")
            return False

        return True

    def _ensure_peer_cached(self, dest: str) -> bool:
        """确保目标 Peer 已缓存

        Args:
            dest: 目标 ID

        Returns:
            bool: 是否缓存成功
        """
        from bot.services.peer_cache import cache_peer_if_needed
        from bot.utils.peer import is_dest_cached

        if is_dest_cached(dest):
            logger.debug(f"      下一级目标Peer已缓存: {dest}")
            return True

        logger.debug(f"      尝试缓存下一级目标Peer: {dest}")
        if cache_peer_if_needed(self.acc, int(dest), "下一级目标"):
            return True

        logger.warning(f"   ⚠️ 下一级目标Peer缓存失败: {dest}")
        logger.warning(f"      💡 提示：如果目标是私聊用户，请确保该用户已与账号建立过对话")
        logger.warning(f"      💡 可以让该用户向账号发送一条消息，然后重启Bot")
        return False

    def _process_chain_config(self, forwarded_message, check_user_id: str, dest_chat_id_str: str,
                              message_text: str, watch_data: dict) -> None:
        """处理单个链式转发配置

        Args:
            forwarded_message: 转发后的消息对象
            check_user_id: 用户 ID
            dest_chat_id_str: 目标频道 ID
            message_text: 消息文本
            watch_data: 监控配置
        """
        check_record_mode = watch_data.get("record_mode", False)
        check_dest = watch_data.get("dest")
        check_forward_mode = watch_data.get("forward_mode", "full")
        check_extract_patterns = watch_data.get("extract_patterns", [])

        # 记录模式
        if check_record_mode:
            logger.info(f"   📝 目标频道配置：记录模式")
            try:
                self._handle_record_mode(
                    forwarded_message, check_user_id, dest_chat_id_str,
                    message_text, check_forward_mode, check_extract_patterns
                )
            except Exception as e:
                logger.error(f"   ❌ 目标频道记录失败: {e}", exc_info=True)

        # 转发模式
        if check_dest and check_dest != "me":
            logger.info(f"   📤 目标频道配置：转发到 {check_dest}")
            logger.debug(f"      转发模式: {check_forward_mode}")

            if not self._ensure_peer_cached(str(check_dest)):
                return

            try:
                check_preserve_source = watch_data.get("preserve_forward_source", False)
                self._handle_forward_mode(
                    forwarded_message, check_dest, message_text,
                    check_forward_mode, check_extract_patterns,
                    check_preserve_source, False
                )
            except Exception as e:
                logger.error(f"   ❌ 目标频道转发失败: {e}", exc_info=True)

    def _trigger_dest_monitoring(self, dest_chat_id, forwarded_message_id, message_text):
        """手动触发目标频道的监控配置处理

        当目标频道也是监控源时，转发到该频道的消息不会自动触发监控
        （因为 copy_message 不触发 outgoing 事件），所以需要手动触发

        Args:
            dest_chat_id: 目标频道 ID
            forwarded_message_id: 转发后的消息 ID
            message_text: 消息文本内容
        """
        # 使用 WatchService 获取配置
        watch_service = get_watch_service()

        dest_chat_id_str = str(dest_chat_id)
        monitored_sources = watch_service.get_monitored_sources()

        # 检查目标是否是监控源
        if dest_chat_id_str not in monitored_sources:
            return

        logger.info(f"🔄 目标频道 {dest_chat_id} 也是监控源，手动触发其配置处理...")
        logger.debug(f"   转发后的消息ID: {forwarded_message_id}")

        # 获取转发后的消息对象
        forwarded_message = self._get_forwarded_message(dest_chat_id_str, forwarded_message_id)
        if not forwarded_message:
            logger.warning(f"   ⚠️ 无法获取转发后的消息对象，跳过链式转发")
            return

        matched_configs = 0
        tasks_for_source = watch_service.get_tasks_for_source(dest_chat_id_str)

        for entry in tasks_for_source:
            if not isinstance(entry, (tuple, list)):
                continue

            if len(entry) == 3:
                check_user_id, check_watch_key, check_task = entry
            elif len(entry) == 2:
                check_user_id, check_task = entry
                check_watch_key = ""
            else:
                continue

            if hasattr(check_task, "to_dict"):
                check_watch_data = check_task.to_dict()
            elif isinstance(check_task, dict):
                check_watch_data = check_task
            else:
                continue

            matched_configs += 1
            check_dest = check_watch_data.get("dest")
            check_record_mode = check_watch_data.get("record_mode", False)

            # 跳过"转发到自己"的配置，避免无限循环
            if (
                not check_record_mode
                and check_dest is not None
                and str(check_dest) == dest_chat_id_str
            ):
                logger.debug(f"   ⏭️ 跳过转发到自己的配置，避免循环")
                continue

            logger.info(
                f"   ✅ 找到目标频道的配置 #{matched_configs}: user={check_user_id}, key={check_watch_key}, "
                f"mode={'记录' if check_record_mode else '转发到 ' + str(check_dest)}"
            )

            # 应用过滤规则
            if not self._apply_chain_filters(message_text, check_watch_data):
                continue

            logger.info(f"   🎯 目标频道配置：通过过滤规则")

            # 处理配置
            self._process_chain_config(
                forwarded_message,
                str(check_user_id),
                dest_chat_id_str,
                message_text,
                check_watch_data,
            )

        if matched_configs == 0:
            logger.debug(f"   ℹ️ 目标频道 {dest_chat_id} 没有匹配的配置")
        else:
            logger.info(f"   📊 链式转发完成: 共处理 {matched_configs} 个配置")

    def stop(self):
        """停止工作线程"""
        self.running = False
        logger.info("🛑 正在停止消息工作线程...")
