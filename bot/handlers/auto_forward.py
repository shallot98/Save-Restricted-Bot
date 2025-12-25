"""
自动转发处理器模块
职责：处理频道/群组消息的自动转发

Architecture: Uses new layered architecture
- src/core/container for service access
- src/infrastructure/cache for message deduplication
"""
import queue
import pyrogram
from pyrogram import filters
from bot.utils.logger import get_logger
from bot.utils import is_message_processed, mark_message_processed, cleanup_old_messages
from bot.utils.dedup import is_media_group_processed, register_processed_media_group, processed_messages
from bot.workers import Message

# New architecture imports
from src.core.container import get_watch_service
from src.infrastructure.cache import get_cache

# Legacy imports (for backward compatibility during migration)
from constants import MESSAGE_CACHE_CLEANUP_THRESHOLD

logger = get_logger(__name__)

# Use new cache for monitored sources
_monitored_sources_cache = get_cache()


def create_auto_forward_handler(acc, message_queue):
    """
    创建自动转发处理器

    Args:
        acc: User客户端实例
        message_queue: 消息队列实例

    Returns:
        function: 自动转发处理器函数
    """

    @acc.on_message((filters.channel | filters.group | filters.private) & (filters.incoming | filters.outgoing))
    def auto_forward(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
        """处理频道/群组/私聊消息，包括转发的消息"""
        try:
            try:
                from src.infrastructure.monitoring.performance.business_metrics import get_business_metrics

                metrics = get_business_metrics()
            except Exception:
                metrics = None

            # 添加调试日志：记录所有接收到的消息
            logger.info(f"🔔 收到消息: chat_id={message.chat.id if message and message.chat else 'Unknown'}, message_id={message.id if message else 'Unknown'}")

            # 验证消息对象和属性
            if not message or not hasattr(message, 'chat') or not message.chat:
                logger.debug("跳过：消息对象无效或缺少 chat 属性")
                return

            # 验证chat ID
            if not hasattr(message.chat, 'id') or message.chat.id is None:
                logger.debug("跳过：消息缺少有效的 chat ID")
                return

            # 检查重复消息
            if not hasattr(message, 'id') or message.id is None:
                logger.debug("跳过：消息缺少有效的 message ID")
                return

            if is_message_processed(message.id, message.chat.id):
                logger.debug(f"⏭️ 跳过已处理的消息: chat_id={message.chat.id}, message_id={message.id}")
                return

            # 立即标记为已处理，防止重复处理
            mark_message_processed(message.id, message.chat.id)

            # 定期清理旧消息记录
            if len(processed_messages) > MESSAGE_CACHE_CLEANUP_THRESHOLD:
                cleanup_old_messages()

            # 记录消息类型
            if message.outgoing:
                logger.debug(f"📤 outgoing消息（由Bot转发）: chat_id={message.chat.id}, message_id={message.id}")
            else:
                logger.debug(f"📥 incoming消息（外部来源）: chat_id={message.chat.id}, message_id={message.id}")

            # 获取源chat ID
            source_chat_id = str(message.chat.id)

            # 早期过滤：检查此源是否被监控（使用 WatchService）
            watch_service = get_watch_service()
            monitored_sources = watch_service.get_monitored_sources()
            if source_chat_id not in monitored_sources:
                # 记录被过滤的消息（调试用）
                logger.debug(f"⏭️ 消息来自非监控源，已跳过: chat_id={source_chat_id}, message_id={message.id}")
                logger.debug(f"   当前监控源列表: {monitored_sources if monitored_sources else '空'}")
                return

            logger.info(f"🔔 监控源消息: chat_id={source_chat_id}, message_id={message.id}")

            # 获取消息文本
            message_text = message.text or message.caption or ""

            # 查找所有匹配的监控配置（使用 WatchService）
            from contextlib import nullcontext

            try:
                from src.infrastructure.monitoring.performance.decorators import performance_context
            except Exception:
                performance_context = None

            monitor_ctx = performance_context("bot.auto_forward.enqueue", tags={"component": "auto_forward"}) if performance_context else nullcontext()
            with monitor_ctx:
                tasks_for_source = watch_service.get_tasks_for_source(source_chat_id)
                enqueued_count = 0
                enqueued_forward_count = 0

                for entry in tasks_for_source:
                    if len(entry) == 3:
                        user_id, watch_key, task = entry
                    else:
                        user_id, task = entry
                        watch_key = source_chat_id

                    if hasattr(task, "to_dict"):
                        watch_data = task.to_dict()
                    elif isinstance(task, dict):
                        watch_data = task
                    else:
                        continue

                    dest = watch_data.get("dest")
                    record_mode = bool(watch_data.get("record_mode", False))
                    preserve_forward_source = bool(watch_data.get("preserve_forward_source", False))

                    logger.info(f"✅ 匹配到监控任务: user={user_id}, source={source_chat_id}")

                    # 转发模式：由 worker 在处理阶段负责确保 Peer 缓存就绪
                    dest_chat_id = dest if not record_mode else None

                    # 媒体组去重
                    if message.media_group_id:
                        mode_suffix = "record" if record_mode else "forward"
                        media_group_key = f"{user_id}_{watch_key}_{dest_chat_id}_{mode_suffix}_{message.media_group_id}"

                        if is_media_group_processed(media_group_key):
                            logger.debug(f"⏭️ 跳过已处理的媒体组: {media_group_key}")
                            continue

                        # 注册为已处理
                        register_processed_media_group(media_group_key)
                        logger.info(f"📸 首次处理媒体组: {media_group_key}")

                    # 创建消息对象
                    msg_obj = Message(
                        user_id=user_id,
                        watch_key=watch_key,
                        source_chat_id=source_chat_id,
                        message_id=message.id,
                        watch_data=watch_data,
                        dest_chat_id=dest_chat_id,
                        message_text=message_text,
                        message=None,
                        media_group_key=f"{user_id}_{watch_key}_{message.media_group_id}" if message.media_group_id else None
                    )

                    # 入队消息进行处理
                    try:
                        message_queue.put_nowait(msg_obj)
                    except queue.Full:
                        logger.warning(
                            f"🚨 队列已满，丢弃消息: user={user_id}, source={source_chat_id}, message_id={message.id}"
                        )
                        if metrics is not None:
                            metrics.record_message_processed(
                                success=False,
                                category="auto_forward",
                                error_type="queue_full",
                            )
                        continue

                    enqueued_count += 1
                    logger.info(f"📬 消息已入队: user={user_id}, source={source_chat_id}, 队列大小={message_queue.qsize()}")
                    if not record_mode:
                        enqueued_forward_count += 1
                        if metrics is not None:
                            metrics.record_forward(success=True, preserve_source=preserve_forward_source)

                if enqueued_count > 0:
                    logger.info(f"✅ 本次共入队 {enqueued_count} 条消息")
                    if metrics is not None:
                        metrics.record_message_processed(success=True, category="auto_forward", error_type=None)

        except (ValueError, KeyError) as e:
            error_msg = str(e)
            if "Peer id invalid" not in error_msg and "ID not found" not in error_msg:
                logger.error(f"⚠️ auto_forward 错误: {type(e).__name__}: {e}", exc_info=True)
                try:
                    from src.infrastructure.monitoring.performance.business_metrics import get_business_metrics

                    get_business_metrics().record_message_processed(
                        success=False,
                        category="auto_forward",
                        error_type=type(e).__name__,
                    )
                except Exception as metrics_err:
                    logger.debug(f"业务指标上报失败（忽略，不影响主流程）: {metrics_err}")
                try:
                    from src.infrastructure.monitoring.performance.business_metrics import get_business_metrics

                    get_business_metrics().record_forward(
                        success=False,
                        preserve_source=False,
                        error_type=type(e).__name__,
                    )
                except Exception as metrics_err:
                    logger.debug(f"业务指标上报失败（忽略，不影响主流程）: {metrics_err}")
                try:
                    from src.infrastructure.monitoring.errors.tracker import get_error_tracker

                    get_error_tracker().track_error(
                        error=e,
                        context={"component": "auto_forward", "error_kind": type(e).__name__},
                    )
                except Exception as track_err:
                    logger.debug(f"错误追踪上报失败（忽略，不影响主流程）: {track_err}")
        except Exception as e:
            logger.error(f"⚠️ auto_forward 意外错误: {type(e).__name__}: {e}", exc_info=True)
            try:
                from src.infrastructure.monitoring.performance.business_metrics import get_business_metrics

                get_business_metrics().record_message_processed(
                    success=False,
                    category="auto_forward",
                    error_type=type(e).__name__,
                )
            except Exception as metrics_err:
                logger.debug(f"业务指标上报失败（忽略，不影响主流程）: {metrics_err}")
            try:
                from src.infrastructure.monitoring.performance.business_metrics import get_business_metrics

                get_business_metrics().record_forward(
                    success=False,
                    preserve_source=False,
                    error_type=type(e).__name__,
                )
            except Exception as metrics_err:
                logger.debug(f"业务指标上报失败（忽略，不影响主流程）: {metrics_err}")
            try:
                from src.infrastructure.monitoring.errors.tracker import get_error_tracker

                get_error_tracker().track_error(
                    error=e,
                    context={"component": "auto_forward", "error_kind": type(e).__name__},
                )
            except Exception as track_err:
                logger.debug(f"错误追踪上报失败（忽略，不影响主流程）: {track_err}")

    return auto_forward
