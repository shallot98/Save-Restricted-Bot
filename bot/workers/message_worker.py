"""
Message queue worker thread
Processes messages from the queue and handles forwarding/recording
"""
import time
import asyncio
import os
import logging
import queue
import re
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime
from zoneinfo import ZoneInfo
import pyrogram
from pyrogram.errors import FloodWait

from database import add_note
from config import load_watch_config, load_webdav_config, MEDIA_DIR
from bot.filters import check_whitelist, check_blacklist, check_whitelist_regex, check_blacklist_regex, extract_content
from bot.storage.webdav_client import WebDAVClient, StorageManager
from bot.utils.dedup import cleanup_old_messages
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


@dataclass
class Message:
    """消息对象，封装消息元数据（优化：只保留必要数据，减少内存占用）"""
    user_id: str
    watch_key: str
    message: pyrogram.types.messages_and_media.message.Message  # 保留完整对象用于转发
    watch_data: Dict[str, Any]
    source_chat_id: str
    dest_chat_id: Optional[str]
    message_text: str
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

        # 初始化存储管理器
        self.storage_manager = self._init_storage_manager()

    def _init_storage_manager(self) -> StorageManager:
        """初始化存储管理器"""
        try:
            # 加载 WebDAV 配置
            webdav_config = load_webdav_config()

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
            try:
                # 获取消息，超时1秒以便定期检查running状态
                try:
                    msg_obj = self.message_queue.get(timeout=1)
                except queue.Empty:
                    # Periodically log statistics and cleanup
                    if time.time() - self.last_stats_time > WORKER_STATS_INTERVAL:
                        queue_size = self.message_queue.qsize()
                        if queue_size > 0 or self.processed_count > 0:
                            logger.info(f"📊 队列统计: 待处理={queue_size}, 已完成={self.processed_count}, 跳过={self.skipped_count}, 失败={self.failed_count}, 重试={self.retry_count}")

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
                
                # 记录队列统计信息
                queue_size = self.message_queue.qsize()
                logger.info(f"📥 从队列取出消息 (队列剩余: {queue_size}, 已处理: {self.processed_count}, 跳过: {self.skipped_count}, 失败: {self.failed_count})")
                
                # 处理消息
                result = self.process_message(msg_obj)

                # 优化：处理完成后立即清理消息对象，释放内存
                try:
                    del msg_obj.message  # 删除Pyrogram消息对象
                    msg_obj.message = None
                except:
                    pass

                if result == "success":
                    self.processed_count += 1
                    logger.info(f"✅ 消息处理成功 (总计: {self.processed_count})")
                elif result == "skip":
                    self.skipped_count += 1
                    logger.info(f"⏭️ 消息已跳过 (总计: {self.skipped_count})")
                elif result == "retry":
                    # 失败处理：重试或放弃
                    if msg_obj.retry_count < self.max_retries:
                        msg_obj.retry_count += 1
                        self.retry_count += 1
                        # Calculate exponential backoff time
                        backoff_time = get_backoff_time(msg_obj.retry_count)
                        logger.warning(f"⚠️ 消息处理失败，将在 {backoff_time} 秒后重试 (第 {msg_obj.retry_count}/{self.max_retries} 次)")
                        time.sleep(backoff_time)
                        # 重新入队
                        self.message_queue.put(msg_obj)
                        logger.info(f"🔄 消息已重新入队")
                    else:
                        self.failed_count += 1
                        logger.error(f"❌ 消息处理最终失败，已达最大重试次数 (总失败: {self.failed_count})")
                
                # 标记任务完成
                self.message_queue.task_done()
                
            except Exception as e:
                logger.error(f"⚠️ 工作线程异常: {e}", exc_info=True)
                # 确保task_done被调用
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
                    time.sleep(wait_time + 1)
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
            
            message = msg_obj.message
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
            append_dn = watch_data.get("append_dn_to_magnet", False)
            
            # 再次验证过滤规则（防止配置在入队后被修改）
            # Priority: blacklist > whitelist (blacklist has higher priority)
            
            # Step 1: Check blacklists first (higher priority)
            if check_blacklist(message_text, blacklist):
                logger.info(f"⏭️ 消息被黑名单过滤: {blacklist}")
                return "skip"

            if check_blacklist_regex(message_text, blacklist_regex):
                logger.info(f"⏭️ 消息被正则黑名单过滤: {blacklist_regex}")
                return "skip"

            # Step 2: Check whitelists
            if not check_whitelist(message_text, whitelist):
                logger.info(f"⏭️ 消息未通过白名单: {whitelist}")
                return "skip"

            if not check_whitelist_regex(message_text, whitelist_regex):
                logger.info(f"⏭️ 消息未通过正则白名单: {whitelist_regex}")
                return "skip"
            
            logger.info(f"🎯 消息通过所有过滤规则，准备处理")
            
            # Record mode - save to database
            if record_mode:
                return self._handle_record_mode(message, user_id, source_chat_id, message_text, forward_mode, extract_patterns)
            
            # Forward mode
            else:
                return self._handle_forward_mode(message, dest_chat_id, message_text, forward_mode, extract_patterns, preserve_forward_source, record_mode, append_dn)
            
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
                return "retry"
        except Exception as e:
            logger.error(f"❌ 处理消息时出错: {e}", exc_info=True)
            return "retry"
    
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
            note_id = add_note(
                user_id=int(user_id),
                source_chat_id=source_chat_id,
                source_name=source_name,
                message_text=content_to_save if content_to_save else None,
                media_type=media_type,
                media_path=media_path,
                media_paths=media_paths if media_paths else None,
                media_group_id=str(message.media_group_id) if message.media_group_id else None
            )
            logger.info(f"✅ 记录模式：笔记保存成功！笔记ID: {note_id}")
            return "success"
        except Exception as e:
            logger.error(f"❌ 记录模式：保存笔记失败！", exc_info=True)
            raise
    
    def _handle_media_group(self, message, content_to_save):
        """Handle media group download"""
        media_type = None
        media_path = None
        media_paths = []

        # 获取 WebDAV 配置
        webdav_config = load_webdav_config()
        keep_local = webdav_config.get('keep_local_copy', False)

        try:
            media_group = self.acc.get_media_group(message.chat.id, message.id)
            if media_group:
                logger.info(f"   📷 发现媒体组，共 {len(media_group)} 个媒体")
                for idx, msg in enumerate(media_group):
                    saved = False
                    storage_location = None

                    # 处理图片
                    if msg.photo:
                        media_type = "photo"
                        file_name = f"{msg.id}_{idx}_{datetime.now(CHINA_TZ).strftime('%Y%m%d_%H%M%S')}.jpg"
                        file_path = os.path.join(MEDIA_DIR, file_name)
                        try:
                            # 下载到本地临时文件
                            self.acc.download_media(msg.photo.file_id, file_name=file_path)

                            # 使用存储管理器保存
                            success, storage_location = self.storage_manager.save_file(file_path, file_name, keep_local=keep_local)

                            if success:
                                media_paths.append(storage_location)
                                if idx == 0:
                                    media_path = storage_location
                                saved = True
                                logger.debug(f"      ✅ 保存图片: {file_name}")
                            else:
                                logger.error(f"      ❌ 存储图片失败: {file_name}")
                        except Exception as e:
                            logger.error(f"      ❌ 下载图片失败: {e}")

                    # 处理视频缩略图
                    elif msg.video:
                        if not media_type:
                            media_type = "video"
                        if msg.video.thumbs and len(msg.video.thumbs) > 0:
                            thumb = msg.video.thumbs[-1]
                            file_name = f"{msg.id}_{idx}_thumb_{datetime.now(CHINA_TZ).strftime('%Y%m%d_%H%M%S')}.jpg"
                            file_path = os.path.join(MEDIA_DIR, file_name)
                            try:
                                # 下载到本地临时文件
                                self.acc.download_media(thumb.file_id, file_name=file_path)

                                # 使用存储管理器保存
                                success, storage_location = self.storage_manager.save_file(file_path, file_name, keep_local=keep_local)

                                if success:
                                    media_paths.append(storage_location)
                                    if idx == 0:
                                        media_path = storage_location
                                    saved = True
                                    logger.debug(f"      ✅ 保存视频缩略图: {file_name}")
                                else:
                                    logger.error(f"      ❌ 存储视频缩略图失败: {file_name}")
                            except Exception as e:
                                logger.error(f"      ❌ 下载视频缩略图失败: {e}")

                    # 处理GIF动图缩略图
                    elif msg.animation:
                        if not media_type:
                            media_type = "animation"
                        if msg.animation.thumbs and len(msg.animation.thumbs) > 0:
                            thumb = msg.animation.thumbs[-1]
                            file_name = f"{msg.id}_{idx}_gif_thumb_{datetime.now(CHINA_TZ).strftime('%Y%m%d_%H%M%S')}.jpg"
                            file_path = os.path.join(MEDIA_DIR, file_name)
                            try:
                                # 下载到本地临时文件
                                self.acc.download_media(thumb.file_id, file_name=file_path)

                                # 使用存储管理器保存
                                success, storage_location = self.storage_manager.save_file(file_path, file_name, keep_local=keep_local)

                                if success:
                                    media_paths.append(storage_location)
                                    if idx == 0:
                                        media_path = storage_location
                                    saved = True
                                    logger.debug(f"      ✅ 保存GIF缩略图: {file_name}")
                                else:
                                    logger.error(f"      ❌ 存储GIF缩略图失败: {file_name}")
                            except Exception as e:
                                logger.error(f"      ❌ 下载GIF缩略图失败: {e}")

                    if not saved:
                        logger.warning(f"      ⚠️ 媒体 {idx+1} 类型不支持或无缩略图")

                    if len(media_paths) >= MAX_MEDIA_PER_GROUP:
                        logger.warning(f"   ⚠️ 媒体组超过{MAX_MEDIA_PER_GROUP}个，仅保存前{MAX_MEDIA_PER_GROUP}个")
                        break

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
        webdav_config = load_webdav_config()
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
                webdav_config = load_webdav_config()
                keep_local = webdav_config.get('keep_local_copy', False)
                success, storage_location = self.storage_manager.save_file(file_path, file_name, keep_local=keep_local)

                if success:
                    media_path = storage_location
                    media_paths = [storage_location]
                else:
                    media_path = file_name
                    media_paths = [file_name]

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
                webdav_config = load_webdav_config()
                keep_local = webdav_config.get('keep_local_copy', False)
                success, storage_location = self.storage_manager.save_file(file_path, file_name, keep_local=keep_local)

                if success:
                    media_path = storage_location
                    media_paths = [storage_location]
                else:
                    media_path = file_name
                    media_paths = [file_name]

                logger.info(f"   ✅ GIF缩略图已保存")
            else:
                logger.warning(f"   ⚠️ GIF动图没有缩略图")
        except Exception as e:
            logger.warning(f"   ⚠️ 下载GIF缩略图失败: {e}")

        return media_type, media_path, media_paths
    
    def _handle_forward_mode(self, message, dest_chat_id, message_text, forward_mode, extract_patterns, preserve_forward_source, record_mode, append_dn=False):
        """Handle forward mode processing"""
        logger.info(f"📤 转发模式：开始处理，目标: {dest_chat_id}")

        # 用于存储转发后的新消息ID(用于链式转发)
        forwarded_message_id = None

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

            # 检查是否需要DN补全
            need_dn_completion = append_dn and message_text
            processed_text = message_text  # 默认使用原始文本

            if need_dn_completion:
                temp_processed = self._append_dn_to_magnets(message_text)
                if temp_processed != message_text:
                    processed_text = temp_processed  # 使用补全DN后的文本
                    need_dn_completion = True
                else:
                    need_dn_completion = False

            # 如果需要DN补全，使用修改后的文本转发
            if need_dn_completion:
                logger.info(f"   🧲 检测到磁力链接，将在同一条消息内补全DN")
                forwarded_message_id = self._forward_with_modified_text(message, dest_id, processed_text, preserve_forward_source)
            else:
                # 正常转发
                if preserve_forward_source:
                    forwarded_message_id = self._forward_with_source(message, dest_id)
                else:
                    forwarded_message_id = self._copy_without_source(message, dest_id)

        # 检查目标频道是否也是监控源，如果是则手动触发其配置
        # 注意：这里传递的是processed_text（可能已补全DN），而不是原始的message_text
        if not record_mode and dest_chat_id and dest_chat_id != "me" and forwarded_message_id:
            # 如果启用了DN补全，传递补全后的文本；否则传递原始文本
            text_for_chain = processed_text if (append_dn and message_text) else message_text
            self._trigger_dest_monitoring(dest_chat_id, forwarded_message_id, text_for_chain)

        return "success"

    def _append_dn_to_magnets(self, message_text):
        """为磁力链接补全DN参数

        Args:
            message_text: 消息文本

        Returns:
            处理后的文本
        """
        import re

        # 查找所有磁力链接
        magnet_pattern = r'magnet:\?xt=urn:btih:[a-zA-Z0-9]+(?:[&?][^\s\n\r|]*)?'
        magnets = re.findall(magnet_pattern, message_text)

        if not magnets:
            return message_text

        # 提取基础DN文本（从消息开头到第一个#号）
        hash_pos = message_text.find('#')
        base_dn_text = message_text[:hash_pos].rstrip() if hash_pos != -1 else message_text.rstrip()

        # 如果基础DN文本为空或就是磁力链接本身，跳过
        if not base_dn_text or base_dn_text in magnets:
            return message_text

        processed_text = message_text
        magnet_count = 0

        for magnet_link in magnets:
            # 检查是否已有dn参数
            if '&dn=' not in magnet_link and '?dn=' not in magnet_link:
                magnet_count += 1

                # 如果有多条磁力链接，在DN结尾添加序号区分
                if len(magnets) > 1:
                    dn_text = f"{base_dn_text}-{magnet_count}"
                else:
                    dn_text = base_dn_text

                # 直接使用原始文字，不进行URL编码
                new_magnet = f"{magnet_link}&dn={dn_text}"
                processed_text = processed_text.replace(magnet_link, new_magnet)
                logger.debug(f"   补全DN [{magnet_count}]: {dn_text[:30]}...")

        if magnet_count > 0:
            logger.info(f"   🧲 共补全 {magnet_count} 条磁力链接的DN参数")

        return processed_text
    
    def _forward_with_modified_text(self, message, dest_id, modified_text, preserve_source=False):
        """转发消息并修改文本内容（用于DN补全）

        Args:
            message: 原始消息对象
            dest_id: 目标ID
            modified_text: 修改后的文本（补全DN的磁力链接）
            preserve_source: 是否保留转发来源

        Returns:
            转发后的第一条消息ID（用于链式转发）
        """
        logger.debug(f"   转发消息并修改文本内容")

        forwarded_msg_id = None

        # 如果消息有媒体（图片、视频等），需要复制媒体并修改caption
        if message.photo or message.video or message.animation or message.document:
            # 对于媒体消息，使用copy_message并修改caption
            if message.media_group_id:
                # 媒体组：使用copy_media_group并修改第一条消息的caption
                try:
                    # 注意：copy_media_group会复制整个媒体组，但只能设置第一条消息的caption
                    # 这正是我们需要的：第一条消息使用补全DN的文本，其他消息保持原样
                    result = self._execute_with_flood_retry(
                        "复制媒体组并修改caption",
                        lambda: self.acc.copy_media_group(
                            dest_id,
                            message.chat.id,
                            message.id,
                            captions=[modified_text]  # 只修改第一条消息的caption
                        )
                    )
                    # copy_media_group返回消息ID列表，取第一个
                    if result and len(result) > 0:
                        forwarded_msg_id = result[0].id if hasattr(result[0], 'id') else result[0]
                    logger.info(f"   ✅ 媒体组已复制（第一条消息的caption已修改）")
                except Exception as e:
                    logger.warning(f"   copy_media_group失败，尝试逐个复制: {e}")
                    # 回退方案：逐个复制
                    try:
                        media_group = self.acc.get_media_group(message.chat.id, message.id)
                        if media_group:
                            logger.debug(f"   逐个处理媒体组，共 {len(media_group)} 个媒体")
                            for idx, msg in enumerate(media_group):
                                # 第一条消息使用修改后的文本，其他消息保持原样
                                caption_to_use = modified_text if idx == 0 else (msg.caption or "")

                                result = self._execute_with_flood_retry(
                                    f"复制媒体 {idx+1}/{len(media_group)}",
                                    lambda m=msg, c=caption_to_use: self.acc.copy_message(
                                        dest_id, m.chat.id, m.id, caption=c
                                    )
                                )
                                # 保存第一条消息的ID
                                if idx == 0 and result:
                                    forwarded_msg_id = result.id if hasattr(result, 'id') else result
                                time.sleep(0.3)
                            logger.info(f"   ✅ 媒体组已逐个复制完成")
                        else:
                            raise Exception("无法获取媒体组")
                    except Exception as e2:
                        logger.error(f"   逐个复制也失败: {e2}")
                        # 最后的回退：复制单条消息
                        result = self._execute_with_flood_retry(
                            "复制单条媒体消息",
                            lambda: self.acc.copy_message(dest_id, message.chat.id, message.id, caption=modified_text)
                        )
                        if result:
                            forwarded_msg_id = result.id if hasattr(result, 'id') else result
                        logger.info(f"   ✅ 已复制单条媒体消息")
            else:
                # 单个媒体：直接复制并修改caption
                result = self._execute_with_flood_retry(
                    "复制媒体消息",
                    lambda: self.acc.copy_message(dest_id, message.chat.id, message.id, caption=modified_text)
                )
                if result:
                    forwarded_msg_id = result.id if hasattr(result, 'id') else result
                logger.info(f"   ✅ 媒体消息已复制（caption已修改）")
        else:
            # 纯文本消息：直接发送修改后的文本
            result = self._execute_with_flood_retry(
                "发送修改后的文本",
                lambda: self.acc.send_message(dest_id, modified_text)
            )
            if result:
                forwarded_msg_id = result.id if hasattr(result, 'id') else result
            logger.info(f"   ✅ 文本消息已发送（文本已修改）")

        time.sleep(RATE_LIMIT_DELAY)
        return forwarded_msg_id

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

    def _trigger_dest_monitoring(self, dest_chat_id, forwarded_message_id, message_text):
        """手动触发目标频道的监控配置处理

        当目标频道也是监控源时，转发到该频道的消息不会自动触发监控
        （因为copy_message不触发outgoing事件），所以需要手动触发

        Args:
            dest_chat_id: 目标频道ID
            forwarded_message_id: 转发后的消息ID（在目标频道中）
            message_text: 消息文本内容
        """
        from config import load_watch_config, get_monitored_sources

        dest_chat_id_str = str(dest_chat_id)
        monitored_sources = get_monitored_sources()

        # 检查目标是否是监控源
        if dest_chat_id_str not in monitored_sources:
            return

        logger.info(f"🔄 目标频道 {dest_chat_id} 也是监控源，手动触发其配置处理...")
        logger.debug(f"   转发后的消息ID: {forwarded_message_id}")

        # 获取转发后的消息对象（关键修改：从目标频道获取消息）
        try:
            dest_id = int(dest_chat_id)
            forwarded_message = self.acc.get_messages(dest_id, forwarded_message_id)
            if not forwarded_message:
                logger.warning(f"   ⚠️ 无法获取转发后的消息对象，跳过链式转发")
                return
            logger.debug(f"   成功获取转发后的消息对象: chat_id={forwarded_message.chat.id}, message_id={forwarded_message.id}")
        except Exception as e:
            logger.error(f"   ❌ 获取转发后的消息对象失败: {e}")
            return

        watch_config = load_watch_config()
        matched_configs = 0

        for check_user_id, check_watches in watch_config.items():
            for check_watch_key, check_watch_data in check_watches.items():
                if isinstance(check_watch_data, dict):
                    check_source = str(check_watch_data.get("source", ""))

                    # 匹配目标频道的配置
                    if check_source != dest_chat_id_str:
                        continue

                    matched_configs += 1

                    # 提取配置
                    check_record_mode = check_watch_data.get("record_mode", False)
                    check_dest = check_watch_data.get("dest")

                    # 跳过"转发到自己"的配置，避免无限循环
                    if not check_record_mode and check_dest == dest_chat_id_str:
                        logger.debug(f"   ⏭️ 跳过转发到自己的配置，避免循环")
                        continue

                    logger.info(f"   ✅ 找到目标频道的配置 #{matched_configs}: user={check_user_id}, mode={'记录' if check_record_mode else '转发到 ' + str(check_dest)}")
                    dest_whitelist = check_watch_data.get("whitelist", [])
                    dest_blacklist = check_watch_data.get("blacklist", [])
                    dest_whitelist_regex = check_watch_data.get("whitelist_regex", [])
                    dest_blacklist_regex = check_watch_data.get("blacklist_regex", [])
                    check_forward_mode = check_watch_data.get("forward_mode", "full")
                    check_extract_patterns = check_watch_data.get("extract_patterns", [])

                    # 应用过滤规则
                    if check_blacklist(message_text, dest_blacklist):
                        logger.debug(f"   ⏭️ 目标频道配置：黑名单过滤")
                        continue
                    if check_blacklist_regex(message_text, dest_blacklist_regex):
                        logger.debug(f"   ⏭️ 目标频道配置：正则黑名单过滤")
                        continue
                    if not check_whitelist(message_text, dest_whitelist):
                        logger.debug(f"   ⏭️ 目标频道配置：白名单过滤")
                        continue
                    if not check_whitelist_regex(message_text, dest_whitelist_regex):
                        logger.debug(f"   ⏭️ 目标频道配置：正则白名单过滤")
                        continue

                    logger.info(f"   🎯 目标频道配置：通过过滤规则")

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

                    # 转发模式（注意：不使用elif，因为一个频道可能同时有记录和转发配置）
                    if check_dest and check_dest != "me":
                        logger.info(f"   📤 目标频道配置：转发到 {check_dest}")
                        logger.debug(f"      转发模式: {check_forward_mode}")
                        if check_extract_patterns:
                            logger.debug(f"      提取规则: {check_extract_patterns}")

                        # 缓存下一级目标的Peer（仅在未缓存时）
                        from bot.services.peer_cache import cache_peer_if_needed
                        from bot.utils.peer import is_dest_cached
                        check_dest_id = int(check_dest)
                        check_dest_str = str(check_dest)

                        # 只有未缓存时才尝试缓存
                        if not is_dest_cached(check_dest_str):
                            logger.debug(f"      尝试缓存下一级目标Peer: {check_dest}")
                            if not cache_peer_if_needed(self.acc, check_dest_id, "下一级目标"):
                                logger.warning(f"   ⚠️ 下一级目标Peer缓存失败: {check_dest}")
                                logger.warning(f"      💡 提示：如果目标是私聊用户，请确保该用户已与账号建立过对话")
                                logger.warning(f"      💡 可以让该用户向账号发送一条消息，然后重启Bot")
                                continue
                        else:
                            logger.debug(f"      下一级目标Peer已缓存: {check_dest}")

                        try:
                            check_preserve_source = check_watch_data.get("preserve_forward_source", False)
                            check_append_dn = check_watch_data.get("append_dn_to_magnet", False)
                            self._handle_forward_mode(
                                forwarded_message, check_dest, message_text,
                                check_forward_mode, check_extract_patterns,
                                check_preserve_source, False, check_append_dn
                            )
                        except Exception as e:
                            logger.error(f"   ❌ 目标频道转发失败: {e}", exc_info=True)

        if matched_configs == 0:
            logger.debug(f"   ℹ️ 目标频道 {dest_chat_id} 没有匹配的配置")
        else:
            logger.info(f"   📊 链式转发完成: 共处理 {matched_configs} 个配置")

    def stop(self):
        """停止工作线程"""
        self.running = False
        logger.info("🛑 正在停止消息工作线程...")
