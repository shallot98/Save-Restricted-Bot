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
from config import load_watch_config, MEDIA_DIR
from bot.filters import check_whitelist, check_blacklist, check_whitelist_regex, check_blacklist_regex, extract_content
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
    """消息对象，封装消息元数据"""
    user_id: str
    watch_key: str
    message: pyrogram.types.messages_and_media.message.Message
    watch_data: Dict[str, Any]
    source_chat_id: str
    dest_chat_id: Optional[str]
    message_text: str
    timestamp: float = field(default_factory=time.time)
    retry_count: int = 0
    media_group_key: Optional[str] = None


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
        
    def run(self):
        """主循环：持续处理队列消息"""
        # Create event loop for this thread
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        logger.info("🔧 消息工作线程已启动（带事件循环）")
        
        while self.running:
            try:
                # 获取消息，超时1秒以便定期检查running状态
                try:
                    msg_obj = self.message_queue.get(timeout=1)
                except queue.Empty:
                    # Periodically log statistics
                    if time.time() - self.last_stats_time > WORKER_STATS_INTERVAL:
                        queue_size = self.message_queue.qsize()
                        if queue_size > 0 or self.processed_count > 0:
                            logger.info(f"📊 队列统计: 待处理={queue_size}, 已完成={self.processed_count}, 跳过={self.skipped_count}, 失败={self.failed_count}, 重试={self.retry_count}")
                        self.last_stats_time = time.time()
                    continue
                
                # 记录队列统计信息
                queue_size = self.message_queue.qsize()
                logger.info(f"📥 从队列取出消息 (队列剩余: {queue_size}, 已处理: {self.processed_count}, 跳过: {self.skipped_count}, 失败: {self.failed_count})")
                
                # 处理消息
                result = self.process_message(msg_obj)
                
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
        """Execute operation with FloodWait retry and timeout handling"""
        for flood_attempt in range(max_flood_retries):
            try:
                result = operation_func()
                # Check if result is a coroutine (async operation)
                if asyncio.iscoroutine(result):
                    self._run_async_with_timeout(result, timeout=timeout)
                return True
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
            
            # 再次验证过滤规则（防止配置在入队后被修改）
            # Priority: blacklist > whitelist (blacklist has higher priority)
            
            # Step 1: Check blacklists first (higher priority)
            if check_blacklist(message_text, blacklist):
                return "skip"
            
            if check_blacklist_regex(message_text, blacklist_regex):
                return "skip"
            
            # Step 2: Check whitelists
            if not check_whitelist(message_text, whitelist):
                return "skip"
            
            if not check_whitelist_regex(message_text, whitelist_regex):
                return "skip"
            
            logger.info(f"🎯 消息通过所有过滤规则，准备处理")
            
            # Record mode - save to database
            if record_mode:
                return self._handle_record_mode(message, user_id, source_chat_id, message_text, forward_mode, extract_patterns)
            
            # Forward mode
            else:
                return self._handle_forward_mode(message, dest_chat_id, message_text, forward_mode, extract_patterns, preserve_forward_source, record_mode)
            
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
        
        try:
            media_group = self.acc.get_media_group(message.chat.id, message.id)
            if media_group:
                logger.info(f"   📷 发现媒体组，共 {len(media_group)} 个媒体")
                for idx, msg in enumerate(media_group):
                    if msg.photo:
                        media_type = "photo"
                        file_name = f"{msg.id}_{idx}_{datetime.now(CHINA_TZ).strftime('%Y%m%d_%H%M%S')}.jpg"
                        file_path = os.path.join(MEDIA_DIR, file_name)
                        self.acc.download_media(msg.photo.file_id, file_name=file_path)
                        media_paths.append(file_name)
                        if idx == 0:
                            media_path = file_name
                        if len(media_paths) >= MAX_MEDIA_PER_GROUP:
                            logger.warning(f"   ⚠️ 媒体组超过{MAX_MEDIA_PER_GROUP}张图片，仅保存前{MAX_MEDIA_PER_GROUP}张")
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
        self.acc.download_media(message.photo.file_id, file_name=file_path)
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
                self.acc.download_media(thumb.file_id, file_name=file_path)
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
                self.acc.download_media(thumb.file_id, file_name=file_path)
                media_path = file_name
                media_paths = [file_name]
                logger.info(f"   ✅ GIF缩略图已保存")
            else:
                logger.warning(f"   ⚠️ GIF动图没有缩略图")
        except Exception as e:
            logger.warning(f"   ⚠️ 下载GIF缩略图失败: {e}")
        
        return media_type, media_path, media_paths
    
    def _handle_forward_mode(self, message, dest_chat_id, message_text, forward_mode, extract_patterns, preserve_forward_source, record_mode):
        """Handle forward mode processing"""
        logger.info(f"📤 转发模式：开始处理，目标: {dest_chat_id}")
        
        # Extract mode
        if forward_mode == "extract" and extract_patterns:
            extracted_text = extract_content(message_text, extract_patterns)
            
            if extracted_text:
                logger.info(f"   提取到内容，准备发送")
                dest_id = "me" if dest_chat_id == "me" else int(dest_chat_id)
                self._execute_with_flood_retry(
                    "发送提取内容",
                    lambda: self.acc.send_message(dest_id, extracted_text)
                )
                logger.info(f"   ✅ 提取内容已发送")
                time.sleep(RATE_LIMIT_DELAY)
            else:
                logger.debug(f"   未提取到任何内容，跳过发送")
        
        # Full forward mode
        else:
            dest_id = "me" if dest_chat_id == "me" else int(dest_chat_id)
            
            if preserve_forward_source:
                self._forward_with_source(message, dest_id)
            else:
                self._copy_without_source(message, dest_id)
        
        # Check for multi-hop chains (dest also has configured tasks)
        if not record_mode and dest_chat_id and dest_chat_id != "me":
            self._check_dest_tasks(message, dest_chat_id, message_text)
        
        return "success"
    
    def _forward_with_source(self, message, dest_id):
        """Forward message preserving source"""
        logger.debug(f"   保留转发来源")
        if message.media_group_id:
            try:
                media_group = self.acc.get_media_group(message.chat.id, message.id)
                message_ids = [msg.id for msg in media_group] if media_group else [message.id]
                self._execute_with_flood_retry(
                    "转发媒体组",
                    lambda: self.acc.forward_messages(dest_id, message.chat.id, message_ids)
                )
                logger.info(f"   ✅ 媒体组已转发")
                time.sleep(RATE_LIMIT_DELAY)
            except UnrecoverableError:
                raise
            except Exception as e:
                logger.warning(f"   转发媒体组失败，回退到单条转发: {e}")
                self._execute_with_flood_retry(
                    "转发单条消息",
                    lambda: self.acc.forward_messages(dest_id, message.chat.id, message.id)
                )
                logger.info(f"   ✅ 消息已转发（单条）")
                time.sleep(RATE_LIMIT_DELAY)
        else:
            self._execute_with_flood_retry(
                "转发消息",
                lambda: self.acc.forward_messages(dest_id, message.chat.id, message.id)
            )
            logger.info(f"   ✅ 消息已转发")
            time.sleep(RATE_LIMIT_DELAY)
    
    def _copy_without_source(self, message, dest_id):
        """Copy message hiding source"""
        logger.debug(f"   隐藏转发来源")
        if message.media_group_id:
            try:
                self._execute_with_flood_retry(
                    "复制媒体组",
                    lambda: self.acc.copy_media_group(dest_id, message.chat.id, message.id)
                )
                logger.info(f"   ✅ 媒体组已复制（隐藏引用）")
                time.sleep(RATE_LIMIT_DELAY)
            except UnrecoverableError:
                raise
            except Exception as e:
                logger.warning(f"   复制媒体组失败，回退到复制单条: {e}")
                self._execute_with_flood_retry(
                    "复制单条消息",
                    lambda: self.acc.copy_message(dest_id, message.chat.id, message.id)
                )
                logger.info(f"   ✅ 消息已复制（单条）")
                time.sleep(RATE_LIMIT_DELAY)
        else:
            self._execute_with_flood_retry(
                "复制消息",
                lambda: self.acc.copy_message(dest_id, message.chat.id, message.id)
            )
            logger.info(f"   ✅ 消息已复制")
            time.sleep(RATE_LIMIT_DELAY)
    
    def _check_dest_tasks(self, message, dest_chat_id, message_text):
        """Check if destination has configured tasks (multi-hop chains)"""
        logger.debug(f"🔍 检查目标频道 {dest_chat_id} 是否配置了任务")
        dest_chat_id_str = str(dest_chat_id)
        watch_config = load_watch_config()
        
        for check_user_id, check_watches in watch_config.items():
            for check_watch_key, check_watch_data in check_watches.items():
                if isinstance(check_watch_data, dict):
                    check_source = str(check_watch_data.get("source", ""))
                    check_record_mode = check_watch_data.get("record_mode", False)
                    check_dest = check_watch_data.get("dest")
                    
                    if check_source == dest_chat_id_str and check_record_mode:
                        # Record mode for destination
                        self._handle_dest_record_mode(message, message_text, check_user_id, check_watch_data, dest_chat_id_str)
                    elif check_source == dest_chat_id_str and not check_record_mode and check_dest:
                        # Forward mode for destination
                        self._handle_dest_forward_mode(message, message_text, check_user_id, check_watch_data, check_dest)
    
    def _handle_dest_record_mode(self, message, message_text, check_user_id, check_watch_data, dest_chat_id_str):
        """Handle recording for destination in multi-hop chain"""
        logger.info(f"📝 目标频道记录模式：发现配置，为用户 {check_user_id} 记录")
        
        try:
            # Get destination chat info
            try:
                dest_chat = self.acc.get_chat(int(dest_chat_id_str))
                dest_name = dest_chat.title or dest_chat.username or dest_chat_id_str
            except:
                dest_name = dest_chat_id_str
            
            # Prepare content
            content_to_save = message_text
            check_forward_mode = check_watch_data.get("forward_mode", "full")
            check_extract_patterns = check_watch_data.get("extract_patterns", [])
            
            if check_forward_mode == "extract" and check_extract_patterns:
                content_to_save = extract_content(message_text, check_extract_patterns)
            
            # Handle media (simplified for dest recording)
            record_media_type, record_media_path, record_media_paths = None, None, []
            
            if message.media_group_id:
                record_media_type, record_media_path, record_media_paths, _ = self._handle_media_group(message, content_to_save)
            elif message.photo:
                record_media_type, record_media_path, record_media_paths = self._handle_single_photo(message)
            elif message.video:
                record_media_type, record_media_path, record_media_paths = self._handle_single_video(message)
            
            # Save to database
            note_id = add_note(
                user_id=int(check_user_id),
                source_chat_id=dest_chat_id_str,
                source_name=dest_name,
                message_text=content_to_save if content_to_save else None,
                media_type=record_media_type,
                media_path=record_media_path,
                media_paths=record_media_paths if record_media_paths else None,
                media_group_id=str(message.media_group_id) if message.media_group_id else None
            )
            logger.info(f"   ✅ 目标频道记录模式：笔记已保存 (ID={note_id})")
        except Exception as e:
            logger.error(f"   ❌ 目标频道记录模式：保存失败: {e}", exc_info=True)
    
    def _handle_dest_forward_mode(self, message, message_text, check_user_id, check_watch_data, check_dest):
        """Handle forwarding for destination in multi-hop chain"""
        logger.info(f"📤 目标频道转发模式：为用户 {check_user_id} 转发/提取到 {check_dest}")
        
        try:
            check_forward_mode = check_watch_data.get("forward_mode", "full")
            check_extract_patterns = check_watch_data.get("extract_patterns", [])
            dest_whitelist = check_watch_data.get("whitelist", [])
            dest_blacklist = check_watch_data.get("blacklist", [])
            dest_whitelist_regex = check_watch_data.get("whitelist_regex", [])
            dest_blacklist_regex = check_watch_data.get("blacklist_regex", [])
            
            # Apply filters
            if check_blacklist(message_text, dest_blacklist):
                return
            if check_blacklist_regex(message_text, dest_blacklist_regex):
                return
            if not check_whitelist(message_text, dest_whitelist):
                return
            if not check_whitelist_regex(message_text, dest_whitelist_regex):
                return
            
            # Extract mode
            if check_forward_mode == "extract" and check_extract_patterns:
                extracted_text = extract_content(message_text, check_extract_patterns)
                if extracted_text:
                    check_dest_id = "me" if check_dest == "me" else int(check_dest)
                    self._execute_with_flood_retry(
                        "发送提取内容（目标频道提取）",
                        lambda: self.acc.send_message(check_dest_id, extracted_text)
                    )
                    logger.info(f"   ✅ 提取内容已发送到 {check_dest}")
                    time.sleep(0.5)
            # Full forward mode
            else:
                check_dest_id = "me" if check_dest == "me" else int(check_dest)
                self._execute_with_flood_retry(
                    "复制消息（目标频道转发）",
                    lambda: self.acc.copy_message(check_dest_id, message.chat.id, message.id)
                )
                logger.info(f"   ✅ 消息已复制到 {check_dest}")
                time.sleep(0.5)
        except Exception as e:
            logger.error(f"   ❌ 目标频道转发/提取失败: {e}", exc_info=True)
    
    def stop(self):
        """停止工作线程"""
        self.running = False
        logger.info("🛑 正在停止消息工作线程...")
