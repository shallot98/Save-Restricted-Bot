import pyrogram
from pyrogram import Client, filters
from pyrogram.errors import UserAlreadyParticipant, InviteHashExpired, UsernameNotOccupied, ChannelPrivate, UsernameInvalid, FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

import time
import asyncio
import os
import threading
import json
import re
import logging
import queue
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from database import add_note, init_database

# 数据目录 - 独立存储，防止更新时丢失
DEFAULT_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'data'))
DATA_DIR = os.environ.get('DATA_DIR', DEFAULT_DATA_DIR)
CONFIG_DIR = os.path.join(DATA_DIR, 'config')
MEDIA_DIR = os.path.join(DATA_DIR, 'media')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')
WATCH_FILE = os.path.join(CONFIG_DIR, 'watch_config.json')

# 确保配置和媒体目录存在
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(MEDIA_DIR, exist_ok=True)

# 配置日志系统
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


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
    
    def __init__(self, message_queue: queue.Queue, max_retries: int = 3):
        self.message_queue = message_queue
        self.max_retries = max_retries
        self.processed_count = 0
        self.failed_count = 0
        self.skipped_count = 0  # Count of messages skipped due to unrecoverable errors
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
                    # Periodically log statistics (every 60 seconds)
                    if time.time() - self.last_stats_time > 60:
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
                        # 计算退避时间：1秒、2秒、4秒
                        backoff_time = 2 ** (msg_obj.retry_count - 1)
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
    
    def _run_async_with_timeout(self, coro, timeout: float = 30.0):
        """Execute async operation with timeout in the worker thread
        
        Args:
            coro: Coroutine to execute
            timeout: Timeout in seconds (default: 30)
            
        Returns:
            Result of the coroutine
            
        Raises:
            asyncio.TimeoutError: If operation times out
            TypeError: If coro is not a coroutine or awaitable
            RuntimeError: If event loop is not available
            Exception: Any exception from the coroutine
        """
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
            # Create timeout wrapper and execute
            return self.loop.run_until_complete(
                asyncio.wait_for(coro, timeout=timeout)
            )
        except asyncio.TimeoutError:
            logger.error(f"❌ 操作超时（{timeout}秒）")
            raise
    
    def _execute_with_flood_retry(self, operation_name: str, operation_func, max_flood_retries: int = 3, timeout: float = 30.0):
        """Execute operation with FloodWait retry and timeout handling
        
        Args:
            operation_name: Name of the operation for logging
            operation_func: Function to execute (can return a coroutine or be a regular callable)
            max_flood_retries: Maximum number of retries for FloodWait errors
            timeout: Timeout in seconds for each attempt (default: 30)
            
        Returns:
            True if operation succeeded
            
        Raises:
            UnrecoverableError: For errors that should not be retried (Peer ID invalid, etc.)
            Exception: For other errors that may be retried
        """
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
            # Check keyword whitelist
            if whitelist:
                if not any(keyword.lower() in message_text.lower() for keyword in whitelist):
                    logger.debug(f"   ⏭ 过滤：未匹配关键词白名单 {whitelist}")
                    return "skip"  # Filtered out by whitelist
            
            # Check keyword blacklist
            if blacklist:
                if any(keyword.lower() in message_text.lower() for keyword in blacklist):
                    logger.debug(f"   ⏭ 过滤：匹配到关键词黑名单 {blacklist}")
                    return "skip"  # Filtered out by blacklist
            
            # Check regex whitelist
            if whitelist_regex:
                match_found = False
                for pattern in whitelist_regex:
                    try:
                        if re.search(pattern, message_text):
                            match_found = True
                            break
                    except re.error:
                        pass
                if not match_found:
                    logger.debug(f"   ⏭ 过滤：未匹配正则白名单 {whitelist_regex}")
                    return "skip"  # Filtered out by regex whitelist
            
            # Check regex blacklist
            if blacklist_regex:
                skip_message = False
                for pattern in blacklist_regex:
                    try:
                        if re.search(pattern, message_text):
                            skip_message = True
                            break
                    except re.error:
                        pass
                if skip_message:
                    logger.debug(f"   ⏭ 过滤：匹配到正则黑名单 {blacklist_regex}")
                    return "skip"  # Filtered out by regex blacklist
            
            logger.info(f"🎯 消息通过所有过滤规则，准备处理")
            
            # Record mode - save to database
            if record_mode:
                logger.info(f"📝 记录模式：开始处理消息")
                logger.info(f"   来源: {source_chat_id} ({getattr(message.chat, 'title', None) or getattr(message.chat, 'username', None)})")
                source_name = message.chat.title or message.chat.username or source_chat_id
                
                # Handle text content with extraction
                content_to_save = message_text
                logger.debug(f"   原始内容长度: {len(message_text)}")
                
                if forward_mode == "extract" and extract_patterns:
                    logger.debug(f"   应用提取模式: {extract_patterns}")
                    extracted_content = []
                    for pattern in extract_patterns:
                        try:
                            matches = re.findall(pattern, message_text)
                            if matches:
                                if isinstance(matches[0], tuple):
                                    for match_group in matches:
                                        extracted_content.extend(match_group)
                                else:
                                    extracted_content.extend(matches)
                                logger.debug(f"   提取到内容: {len(matches)} 个匹配")
                        except re.error as e:
                            logger.warning(f"   正则表达式错误: {pattern} - {e}")
                    
                    if extracted_content:
                        content_to_save = "\n".join(set(extracted_content))
                        logger.debug(f"   提取后内容长度: {len(content_to_save)}")
                    else:
                        content_to_save = ""
                        logger.debug(f"   未提取到任何内容")
                
                # Handle media
                media_type = None
                media_path = None
                media_paths = []
                
                logger.debug(f"   开始处理媒体")
                logger.debug(f"   - 是否有媒体组: {bool(message.media_group_id)}")
                logger.debug(f"   - 是否有图片: {bool(message.photo)}")
                logger.debug(f"   - 是否有视频: {bool(message.video)}")
                
                # Check if this is a media group (multiple images)
                if message.media_group_id:
                    try:
                        # Call get_media_group directly - Pyrogram handles async/sync bridging
                        media_group = acc.get_media_group(message.chat.id, message.id)
                        if media_group:
                            logger.info(f"   📷 发现媒体组，共 {len(media_group)} 个媒体")
                            for idx, msg in enumerate(media_group):
                                if msg.photo:
                                    media_type = "photo"
                                    file_name = f"{msg.id}_{idx}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                                    file_path = os.path.join(MEDIA_DIR, file_name)
                                    logger.debug(f"   下载图片 {idx+1}: {file_name}")
                                    # Call download_media directly - Pyrogram handles async/sync bridging
                                    acc.download_media(msg.photo.file_id, file_name=file_path)
                                    media_paths.append(file_name)
                                    if idx == 0:
                                        media_path = file_name
                                    # Limit to 9 images
                                    if len(media_paths) >= 9:
                                        logger.warning(f"   ⚠️ 媒体组超过9张图片，仅保存前9张")
                                        break
                                # Capture caption if available and not already set (common on last item)
                                if msg.caption and not content_to_save:
                                    content_to_save = msg.caption
                                    logger.debug(f"   从媒体组捕获标题")
                            logger.info(f"   ✅ 媒体组处理完成，共保存 {len(media_paths)} 个文件")
                    except Exception as e:
                        logger.error(f"   ❌ 获取媒体组失败: {e}", exc_info=True)
                        # Fallback to single image
                        if message.photo:
                            logger.info(f"   回退到单张图片处理")
                            media_type = "photo"
                            file_name = f"{message.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                            file_path = os.path.join(MEDIA_DIR, file_name)
                            # Call download_media directly - Pyrogram handles async/sync bridging
                            acc.download_media(message.photo.file_id, file_name=file_path)
                            media_path = file_name
                            media_paths = [file_name]
                            logger.debug(f"   保存单张图片: {file_name}")
                
                # Single photo
                elif message.photo:
                    logger.info(f"   📷 处理单张图片")
                    media_type = "photo"
                    photo = message.photo
                    file_name = f"{message.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                    file_path = os.path.join(MEDIA_DIR, file_name)
                    # Call download_media directly - Pyrogram handles async/sync bridging
                    acc.download_media(photo.file_id, file_name=file_path)
                    media_path = file_name
                    media_paths = [file_name]
                    logger.debug(f"   保存图片: {file_name}")
                
                # Single video
                elif message.video:
                    logger.info(f"   📹 处理视频消息")
                    media_type = "video"
                    logger.info(f"   - 视频时长: {message.video.duration}秒")
                    logger.info(f"   - 视频尺寸: {message.video.width}x{message.video.height}")
                    logger.info(f"   - 是否有缩略图: {bool(message.video.thumbs)}")
                    
                    try:
                        # Try to download video thumbnail
                        if message.video.thumbs and len(message.video.thumbs) > 0:
                            # Get the largest thumbnail
                            thumb = message.video.thumbs[-1]
                            file_name = f"{message.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_thumb.jpg"
                            file_path = os.path.join(MEDIA_DIR, file_name)
                            logger.info(f"   尝试下载视频缩略图: {file_name}")
                            # Call download_media directly - Pyrogram handles async/sync bridging
                            acc.download_media(thumb.file_id, file_name=file_path)
                            media_path = file_name
                            media_paths = [file_name]
                            logger.info(f"   ✅ 视频缩略图已保存: {file_name}")
                        else:
                            logger.warning(f"   ⚠️ 视频没有缩略图，将只记录视频类型")
                    except Exception as e:
                        logger.warning(f"   ⚠️ 下载视频缩略图失败: {e}")
                        logger.info(f"   视频类型信息将被保留，但无缩略图")
                
                # Save to database
                logger.info(f"💾 记录模式：准备保存笔记到数据库")
                logger.info(f"   - 用户ID: {user_id}")
                logger.info(f"   - 来源: {source_name} ({source_chat_id})")
                logger.info(f"   - 文本: {bool(content_to_save)} ({len(content_to_save) if content_to_save else 0} 字符)")
                logger.info(f"   - 媒体类型: {media_type}")
                logger.info(f"   - 媒体数量: {len(media_paths)} 个")
                logger.debug(f"   - 媒体路径: {media_paths}")
                
                try:
                    note_id = add_note(
                        user_id=int(user_id),
                        source_chat_id=source_chat_id,
                        source_name=source_name,
                        message_text=content_to_save if content_to_save else None,
                        media_type=media_type,
                        media_path=media_path,
                        media_paths=media_paths if media_paths else None
                    )
                    logger.info(f"✅ 记录模式：笔记保存成功！")
                    logger.info(f"   笔记ID: {note_id}")
                except Exception as e:
                    logger.error(f"❌ 记录模式：保存笔记失败！", exc_info=True)
                    logger.error(f"   错误类型: {type(e).__name__}")
                    logger.error(f"   错误信息: {str(e)}")
                    raise  # Re-raise to trigger retry
            
            # Forward mode
            else:
                logger.info(f"📤 转发模式：开始处理")
                logger.info(f"   目标: {dest_chat_id}")
                
                # Extract mode
                if forward_mode == "extract" and extract_patterns:
                    logger.debug(f"   使用提取模式")
                    extracted_content = []
                    for pattern in extract_patterns:
                        try:
                            matches = re.findall(pattern, message_text)
                            if matches:
                                if isinstance(matches[0], tuple):
                                    for match_group in matches:
                                        extracted_content.extend(match_group)
                                else:
                                    extracted_content.extend(matches)
                        except re.error:
                            pass
                    
                    if extracted_content:
                        extracted_text = "\n".join(set(extracted_content))
                        logger.info(f"   提取到内容，准备发送")
                        
                        dest_id = "me" if dest_chat_id == "me" else int(dest_chat_id)
                        
                        self._execute_with_flood_retry(
                            "发送提取内容",
                            lambda: acc.send_message(dest_id, extracted_text)
                        )
                        logger.info(f"   ✅ 提取内容已发送")
                        time.sleep(0.5)
                    else:
                        logger.debug(f"   未提取到任何内容，跳过发送")
                
                # Full forward mode
                else:
                    logger.debug(f"   使用完整转发模式")
                    dest_id = "me" if dest_chat_id == "me" else int(dest_chat_id)
                    
                    if preserve_forward_source:
                        logger.debug(f"   保留转发来源")
                        # Keep forward source - forward full media group when available
                        if message.media_group_id:
                            try:
                                # Call get_media_group directly - Pyrogram handles async/sync bridging
                                media_group = acc.get_media_group(message.chat.id, message.id)
                                if media_group:
                                    message_ids = [msg.id for msg in media_group]
                                else:
                                    message_ids = [message.id]
                                
                                self._execute_with_flood_retry(
                                    "转发媒体组",
                                    lambda: acc.forward_messages(dest_id, message.chat.id, message_ids)
                                )
                                logger.info(f"   ✅ 媒体组已转发")
                                time.sleep(0.5)
                            except UnrecoverableError:
                                raise
                            except Exception as e:
                                logger.warning(f"   转发媒体组失败，回退到单条转发: {e}")
                                self._execute_with_flood_retry(
                                    "转发单条消息",
                                    lambda: acc.forward_messages(dest_id, message.chat.id, message.id)
                                )
                                logger.info(f"   ✅ 消息已转发（单条）")
                                time.sleep(0.5)
                        else:
                            self._execute_with_flood_retry(
                                "转发消息",
                                lambda: acc.forward_messages(dest_id, message.chat.id, message.id)
                            )
                            logger.info(f"   ✅ 消息已转发")
                            time.sleep(0.5)
                    else:
                        logger.debug(f"   隐藏转发来源")
                        # Hide forward source - use copy for single messages or copy_media_group for albums
                        if message.media_group_id:
                            try:
                                self._execute_with_flood_retry(
                                    "复制媒体组",
                                    lambda: acc.copy_media_group(dest_id, message.chat.id, message.id)
                                )
                                logger.info(f"   ✅ 媒体组已复制到 {dest_id}（隐藏引用）")
                                time.sleep(0.5)
                            except UnrecoverableError:
                                raise
                            except Exception as e:
                                logger.warning(f"   复制媒体组失败，回退到复制单条: {e}")
                                self._execute_with_flood_retry(
                                    "复制单条消息",
                                    lambda: acc.copy_message(dest_id, message.chat.id, message.id)
                                )
                                logger.info(f"   ✅ 消息已复制（单条）")
                                time.sleep(0.5)
                        else:
                            # Single message - use copy_message
                            self._execute_with_flood_retry(
                                "复制消息",
                                lambda: acc.copy_message(dest_id, message.chat.id, message.id)
                            )
                            logger.info(f"   ✅ 消息已复制")
                            time.sleep(0.5)
                
                # After forwarding, check if destination also has record mode configured
                if not record_mode and dest_chat_id and dest_chat_id != "me":
                    logger.debug(f"🔍 检查目标频道 {dest_chat_id} 是否配置了记录模式")
                    dest_chat_id_str = str(dest_chat_id)
                    
                    # Reload watch config to get latest settings
                    watch_config = load_watch_config()
                    
                    # Check all watch configs to see if dest has record mode
                    for check_user_id, check_watches in watch_config.items():
                        for check_watch_key, check_watch_data in check_watches.items():
                            if isinstance(check_watch_data, dict):
                                check_source = str(check_watch_data.get("source", ""))
                                check_record_mode = check_watch_data.get("record_mode", False)
                                
                                # If dest has record mode, save this forwarded message
                                if check_source == dest_chat_id_str and check_record_mode:
                                    logger.info(f"📝 目标频道记录模式：发现 {dest_chat_id} 配置了记录模式")
                                    logger.info(f"   为用户 {check_user_id} 记录此转发的消息")
                                    
                                    try:
                                        # Get destination chat info for source_name
                                        try:
                                            # Call get_chat directly - Pyrogram handles async/sync bridging
                                            dest_chat = acc.get_chat(int(dest_chat_id))
                                            dest_name = dest_chat.title or dest_chat.username or dest_chat_id_str
                                        except:
                                            dest_name = dest_chat_id_str
                                        
                                        # Prepare content for recording
                                        content_to_save = message_text
                                        check_forward_mode = check_watch_data.get("forward_mode", "full")
                                        check_extract_patterns = check_watch_data.get("extract_patterns", [])
                                        
                                        # Apply extraction if configured
                                        if check_forward_mode == "extract" and check_extract_patterns:
                                            logger.debug(f"   目标频道配置了提取模式")
                                            extracted_content = []
                                            for pattern in check_extract_patterns:
                                                try:
                                                    matches = re.findall(pattern, message_text)
                                                    if matches:
                                                        if isinstance(matches[0], tuple):
                                                            for match_group in matches:
                                                                extracted_content.extend(match_group)
                                                        else:
                                                            extracted_content.extend(matches)
                                                except re.error:
                                                    pass
                                            if extracted_content:
                                                content_to_save = "\n".join(set(extracted_content))
                                            else:
                                                content_to_save = ""
                                        
                                        # Handle media
                                        record_media_type = None
                                        record_media_path = None
                                        record_media_paths = []
                                        
                                        # Check if message has media group
                                        if message.media_group_id:
                                            try:
                                                # Call get_media_group directly - Pyrogram handles async/sync bridging
                                                media_group = acc.get_media_group(message.chat.id, message.id)
                                                if media_group:
                                                    logger.info(f"   📷 记录媒体组，共 {len(media_group)} 个媒体")
                                                    for idx, msg in enumerate(media_group):
                                                        if msg.photo:
                                                            record_media_type = "photo"
                                                            file_name = f"{msg.id}_{idx}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                                                            file_path = os.path.join(MEDIA_DIR, file_name)
                                                            # Call download_media directly - Pyrogram handles async/sync bridging
                                                            acc.download_media(msg.photo.file_id, file_name=file_path)
                                                            record_media_paths.append(file_name)
                                                            if idx == 0:
                                                                record_media_path = file_name
                                                            if len(record_media_paths) >= 9:
                                                                break
                                                        if msg.caption and not content_to_save:
                                                            content_to_save = msg.caption
                                            except Exception as e:
                                                logger.warning(f"   获取媒体组失败: {e}")
                                        
                                        # Single photo
                                        elif message.photo:
                                            logger.info(f"   📷 记录单张图片")
                                            record_media_type = "photo"
                                            photo = message.photo
                                            file_name = f"{message.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                                            file_path = os.path.join(MEDIA_DIR, file_name)
                                            # Call download_media directly - Pyrogram handles async/sync bridging
                                            acc.download_media(photo.file_id, file_name=file_path)
                                            record_media_path = file_name
                                            record_media_paths = [file_name]
                                        
                                        # Single video
                                        elif message.video:
                                            logger.info(f"   📹 记录视频")
                                            record_media_type = "video"
                                            try:
                                                if message.video.thumbs and len(message.video.thumbs) > 0:
                                                    thumb = message.video.thumbs[-1]
                                                    file_name = f"{message.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_thumb.jpg"
                                                    file_path = os.path.join(MEDIA_DIR, file_name)
                                                    # Call download_media directly - Pyrogram handles async/sync bridging
                                                    acc.download_media(thumb.file_id, file_name=file_path)
                                                    record_media_path = file_name
                                                    record_media_paths = [file_name]
                                                    logger.info(f"   ✅ 视频缩略图已保存")
                                                else:
                                                    logger.warning(f"   ⚠️ 视频没有缩略图")
                                            except Exception as e:
                                                logger.warning(f"   ⚠️ 视频缩略图下载失败: {e}")
                                        
                                        # Save to database
                                        note_id = add_note(
                                            user_id=int(check_user_id),
                                            source_chat_id=dest_chat_id_str,
                                            source_name=dest_name,
                                            message_text=content_to_save if content_to_save else None,
                                            media_type=record_media_type,
                                            media_path=record_media_path,
                                            media_paths=record_media_paths if record_media_paths else None
                                        )
                                        logger.info(f"   ✅ 目标频道记录模式：笔记已保存 (ID={note_id})")
                                        
                                    except Exception as e:
                                        logger.error(f"   ❌ 目标频道记录模式：保存失败: {e}", exc_info=True)
            
            # 处理成功
            return "success"
            
        except UnrecoverableError as e:
            # Unrecoverable errors should not be retried
            logger.warning(f"⚠️ 消息处理失败（不可恢复），跳过: {e}")
            return "skip"  # Skip, don't retry
        except (ValueError, KeyError) as e:
            error_msg = str(e)
            if "Peer id invalid" in error_msg or "ID not found" in error_msg:
                # Silently skip invalid peer errors - don't retry
                logger.warning(f"⚠️ 跳过无效的 Peer ID 错误: {error_msg}")
                return "skip"  # Skip, don't retry
            else:
                logger.error(f"❌ 处理消息时出错: {type(e).__name__}: {e}", exc_info=True)
                return "retry"  # Trigger retry
        except Exception as e:
            logger.error(f"❌ 处理消息时出错: {e}", exc_info=True)
            return "retry"  # Trigger retry
    
    def stop(self):
        """停止工作线程"""
        self.running = False
        logger.info("🛑 正在停止消息工作线程...")


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    config_data = {}
    for key in ["TOKEN", "HASH", "ID", "STRING", "OWNER_ID"]:
        value = os.environ.get(key)
        if value:
            config_data[key] = value
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=4, ensure_ascii=False)
    return config_data

DATA = load_config()

def getenv(var):
    return os.environ.get(var) or DATA.get(var)

# User state management for multi-step interactions
user_states = {}

def load_watch_config():
    if os.path.exists(WATCH_FILE):
        try:
            with open(WATCH_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    with open(WATCH_FILE, 'w', encoding='utf-8') as f:
        json.dump({}, f, indent=4, ensure_ascii=False)
    return {}

def save_watch_config(config):
    with open(WATCH_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

bot_token = getenv("TOKEN") 
api_hash = getenv("HASH") 
api_id = getenv("ID")
bot = Client("mybot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

ss = getenv("STRING")
if ss is not None:
    acc = Client("myacc" ,api_id=api_id, api_hash=api_hash, session_string=ss)
    acc.start()
else: acc = None

# Initialize message queue and worker thread
message_queue = queue.Queue()
message_worker = None
worker_thread = None

if acc is not None:
    message_worker = MessageWorker(message_queue, max_retries=3)
    worker_thread = threading.Thread(target=message_worker.run, daemon=True, name="MessageWorker")
    worker_thread.start()
    logger.info("✅ 消息队列和工作线程已初始化")

# download status
def downstatus(statusfile,message):
    while True:
        if os.path.exists(statusfile):
            break

    time.sleep(3)      
    while os.path.exists(statusfile):
        with open(statusfile,"r") as downread:
            txt = downread.read()
        try:
            bot.edit_message_text(message.chat.id, message.id, f"__⬇️ 已下载__ : **{txt}**")
            time.sleep(10)
        except:
            time.sleep(5)


# upload status
def upstatus(statusfile,message):
    while True:
        if os.path.exists(statusfile):
            break

    time.sleep(3)      
    while os.path.exists(statusfile):
        with open(statusfile,"r") as upread:
            txt = upread.read()
        try:
            bot.edit_message_text(message.chat.id, message.id, f"__⬆️ 已上传__ : **{txt}**")
            time.sleep(10)
        except:
            time.sleep(5)


# progress writter
def progress(current, total, message, type):
    with open(f'{message.id}{type}status.txt',"w") as fileup:
        fileup.write(f"{current * 100 / total:.1f}%")


# start command
@bot.on_message(filters.command(["start"]))
def send_start(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 监控管理", callback_data="menu_watch")],
        [InlineKeyboardButton("❓ 帮助说明", callback_data="menu_help")],
        [InlineKeyboardButton("🌐 源代码", url="https://github.com/bipinkrish/Save-Restricted-Bot")]
    ])
    
    welcome_text = f"👋 你好 **{message.from_user.mention}**！\n\n"
    welcome_text += "我是受限内容保存机器人，可以帮你：\n\n"
    welcome_text += "📥 **转发消息** - 直接发送 Telegram 链接\n"
    welcome_text += "👁 **监控频道/群组** - 自动转发新消息\n"
    welcome_text += "🔍 **智能过滤** - 关键词、正则表达式过滤\n"
    welcome_text += "🎯 **提取模式** - 提取特定内容转发\n\n"
    welcome_text += "点击下方按钮开始使用 👇"
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=keyboard, reply_to_message_id=message.id)

# help command
@bot.on_message(filters.command(["help"]))
def send_help(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 监控管理", callback_data="menu_watch")],
        [InlineKeyboardButton("🏠 返回主菜单", callback_data="menu_main")]
    ])
    
    help_text = """**📖 使用帮助**

**📥 转发消息**
直接发送 Telegram 消息链接即可转发内容

**📋 监控功能**
• 点击"监控管理"按钮设置自动转发
• 支持监控频道和群组
• 支持关键词过滤（白名单/黑名单）
• 支持正则表达式过滤
• 支持提取模式（正则提取特定内容）
• 可选择是否保留转发来源
• 可随时编辑监控设置

**🔗 链接格式**

公开频道/群组：
`https://t.me/username/123`

私有频道/群组（需要先加入）：
`https://t.me/c/123456789/123`

批量下载（范围）：
`https://t.me/username/100-120`

机器人消息：
`https://t.me/b/botusername/123`

**💡 提示**
• 私有频道需要配置 String Session
• 可以使用"me"作为目标保存到收藏夹
• 关键词过滤不区分大小写
• 正则表达式支持完整的 Python re 语法
• 提取模式会将匹配的内容单独发送
• 所有操作都可通过按钮完成，无需记忆复杂命令
"""
    bot.send_message(message.chat.id, help_text, reply_markup=keyboard, reply_to_message_id=message.id)

# watch command - now with inline keyboard
@bot.on_message(filters.command(["watch"]))
def watch_command(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    if acc is None:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 返回主菜单", callback_data="menu_main")]])
        bot.send_message(message.chat.id, "**❌ 需要配置 String Session 才能使用监控功能**", reply_markup=keyboard, reply_to_message_id=message.id)
        return
    
    show_watch_menu(message.chat.id, message.id)

def show_watch_menu(chat_id, reply_to_message_id=None):
    watch_config = load_watch_config()
    user_id = str(chat_id)
    
    watch_count = len(watch_config.get(user_id, {}))
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ 添加监控", callback_data="watch_add_start")],
        [InlineKeyboardButton(f"📋 查看列表 ({watch_count})", callback_data="watch_list")],
        [InlineKeyboardButton("🗑 删除监控", callback_data="watch_remove_start")],
        [InlineKeyboardButton("🏠 返回主菜单", callback_data="menu_main")]
    ])
    
    text = "**📋 监控管理**\n\n"
    text += "选择操作：\n\n"
    text += "➕ **添加监控** - 设置新的自动转发任务\n"
    text += "📋 **查看列表** - 查看所有监控任务\n"
    text += "🗑 **删除监控** - 移除现有监控任务\n\n"
    text += f"当前监控任务数：**{watch_count}** 个"
    
    bot.send_message(chat_id, text, reply_markup=keyboard, reply_to_message_id=reply_to_message_id)

# Callback query handler
@bot.on_callback_query()
def callback_handler(client: pyrogram.client.Client, callback_query: CallbackQuery):
    data = callback_query.data
    chat_id = callback_query.message.chat.id
    message_id = callback_query.message.id
    user_id = str(callback_query.from_user.id)
    
    try:
        if data == "menu_main":
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 监控管理", callback_data="menu_watch")],
                [InlineKeyboardButton("❓ 帮助说明", callback_data="menu_help")],
                [InlineKeyboardButton("🌐 源代码", url="https://github.com/bipinkrish/Save-Restricted-Bot")]
            ])
            
            welcome_text = f"👋 你好 **{callback_query.from_user.mention}**！\n\n"
            welcome_text += "我是受限内容保存机器人，可以帮你：\n\n"
            welcome_text += "📥 **转发消息** - 直接发送 Telegram 链接\n"
            welcome_text += "👁 **监控频道/群组** - 自动转发新消息\n"
            welcome_text += "🔍 **智能过滤** - 关键词、正则表达式过滤\n"
            welcome_text += "🎯 **提取模式** - 提取特定内容转发\n\n"
            welcome_text += "点击下方按钮开始使用 👇"
            
            bot.edit_message_text(chat_id, message_id, welcome_text, reply_markup=keyboard)
            callback_query.answer()
        
        elif data == "menu_help":
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 监控管理", callback_data="menu_watch")],
                [InlineKeyboardButton("🏠 返回主菜单", callback_data="menu_main")]
            ])
            
            help_text = """**📖 使用帮助**

**📥 转发消息**
直接发送 Telegram 消息链接即可转发内容

**📋 监控功能**
• 点击"监控管理"按钮设置自动转发或记录
• 支持监控频道、群组和收藏夹
• 输入 `me` 可监控自己的收藏夹
• 支持关键词过滤（白名单/黑名单）
• 支持正则表达式过滤
• 支持提取模式（正则提取特定内容）
• 可选择是否保留转发来源
• 📝 支持记录模式（保存到网页笔记）
• 可随时编辑监控设置

**📝 记录模式**
• 将监控内容保存到网页而非转发
• 记录文字、图片和视频封面
• 包含时间戳信息
• 过滤规则和提取模式仍然生效
• 通过 Web 界面查看记录（端口 5000）
• 默认登录账号：admin/admin
• 搜索功能支持高亮显示

**🔗 链接格式**

公开频道/群组：
`https://t.me/username/123`

私有频道/群组（需要先加入）：
`https://t.me/c/123456789/123`

批量下载（范围）：
`https://t.me/username/100-120`

机器人消息：
`https://t.me/b/botusername/123`

**💡 提示**
• 私有频道需要配置 String Session
• 可以使用 `me` 监控收藏夹或作为目标
• 关键词过滤不区分大小写
• 正则表达式支持完整的 Python re 语法
• 提取模式会将匹配的内容单独发送
• 所有操作都可通过按钮完成，无需记忆复杂命令
• 机器人重启后会自动加载所有配置
"""
            bot.edit_message_text(chat_id, message_id, help_text, reply_markup=keyboard)
            callback_query.answer()
        
        elif data == "menu_watch":
            if acc is None:
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 返回主菜单", callback_data="menu_main")]])
                bot.edit_message_text(chat_id, message_id, "**❌ 需要配置 String Session 才能使用监控功能**", reply_markup=keyboard)
                callback_query.answer("❌ 需要配置 String Session", show_alert=True)
                return
            
            watch_config = load_watch_config()
            watch_count = len(watch_config.get(user_id, {}))
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ 添加监控", callback_data="watch_add_start")],
                [InlineKeyboardButton(f"📋 查看列表 ({watch_count})", callback_data="watch_list")],
                [InlineKeyboardButton("🗑 删除监控", callback_data="watch_remove_start")],
                [InlineKeyboardButton("🏠 返回主菜单", callback_data="menu_main")]
            ])
            
            text = "**📋 监控管理**\n\n"
            text += "选择操作：\n\n"
            text += "➕ **添加监控** - 设置新的自动转发任务\n"
            text += "📋 **查看列表** - 查看所有监控任务\n"
            text += "🗑 **删除监控** - 移除现有监控任务\n\n"
            text += f"当前监控任务数：**{watch_count}** 个"
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer()
        
        elif data == "watch_add_start":
            user_states[user_id] = {"action": "add_source"}
            
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]])
            
            text = "**➕ 添加监控任务**\n\n"
            text += "**步骤 1/2：** 请发送来源频道/群组\n\n"
            text += "可以发送：\n"
            text += "• 输入 `me` 监控自己的收藏夹\n"
            text += "• 频道/群组用户名（如 `@channel_name`）\n"
            text += "• 频道/群组ID（如 `-1001234567890`）\n"
            text += "• 转发一条来自该频道/群组的消息\n\n"
            text += "💡 机器人需要能够访问该频道/群组"
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer()
        
        elif data == "watch_list":
            watch_config = load_watch_config()
            
            if user_id not in watch_config or not watch_config[user_id]:
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="menu_watch")]])
                bot.edit_message_text(chat_id, message_id, "**📋 监控列表**\n\n暂无监控任务\n\n点击\"添加监控\"开始设置", reply_markup=keyboard)
                callback_query.answer("暂无监控任务")
                return
            
            buttons = []
            for idx, (watch_key, watch_data) in enumerate(watch_config[user_id].items(), 1):
                if isinstance(watch_data, dict):
                    # New format with source|dest key
                    source = watch_data.get("source", watch_key.split("|")[0] if "|" in watch_key else watch_key)
                    dest = watch_data.get("dest", watch_key.split("|")[1] if "|" in watch_key else "unknown")
                else:
                    # Old format compatibility
                    source = watch_key
                    dest = watch_data
                
                # Handle None values
                if source is None:
                    source = "未知来源"
                if dest is None:
                    dest = "未知目标"
                
                # Truncate source and dest for button display
                source_display = source if len(source) <= 15 else source[:12] + "..."
                dest_display = dest if len(dest) <= 15 else dest[:12] + "..."
                
                buttons.append([InlineKeyboardButton(f"{idx}. {source_display} ➡️ {dest_display}", callback_data=f"watch_view_{idx}")])
            
            buttons.append([InlineKeyboardButton("🔙 返回", callback_data="menu_watch")])
            keyboard = InlineKeyboardMarkup(buttons)
            
            text = "**📋 监控任务列表**\n\n"
            text += f"共 **{len(watch_config[user_id])}** 个监控任务\n\n"
            text += "点击任务查看详情和编辑 👇"
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer()
        
        elif data == "watch_remove_start":
            watch_config = load_watch_config()
            
            if user_id not in watch_config or not watch_config[user_id]:
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="menu_watch")]])
                bot.edit_message_text(chat_id, message_id, "**🗑 删除监控**\n\n暂无监控任务可删除", reply_markup=keyboard)
                callback_query.answer("暂无监控任务")
                return
            
            buttons = []
            for idx, (watch_key, watch_data) in enumerate(watch_config[user_id].items(), 1):
                if isinstance(watch_data, dict):
                    # New format with source|dest key
                    source = watch_data.get("source", watch_key.split("|")[0] if "|" in watch_key else watch_key)
                    dest = watch_data.get("dest", watch_key.split("|")[1] if "|" in watch_key else "unknown")
                else:
                    # Old format compatibility
                    source = watch_key
                    dest = watch_data
                
                # Handle None values
                if source is None:
                    source = "未知来源"
                if dest is None:
                    dest = "未知目标"
                
                buttons.append([InlineKeyboardButton(f"🗑 {idx}. {source} ➡️ {dest}", callback_data=f"watch_remove_{idx}")])
            
            buttons.append([InlineKeyboardButton("❌ 取消", callback_data="menu_watch")])
            keyboard = InlineKeyboardMarkup(buttons)
            
            text = "**🗑 删除监控**\n\n"
            text += "选择要删除的监控任务："
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer()
        
        elif data.startswith("watch_view_"):
            task_id = int(data.split("_")[2])
            watch_config = load_watch_config()
            
            if user_id not in watch_config or not watch_config[user_id]:
                callback_query.answer("❌ 监控任务不存在", show_alert=True)
                return
            
            if task_id < 1 or task_id > len(watch_config[user_id]):
                callback_query.answer("❌ 任务编号无效", show_alert=True)
                return
            
            watch_key = list(watch_config[user_id].keys())[task_id - 1]
            watch_data = watch_config[user_id][watch_key]
            
            if isinstance(watch_data, dict):
                # New format with source|dest key
                source_id = watch_data.get("source", watch_key.split("|")[0] if "|" in watch_key else watch_key)
                dest = watch_data.get("dest", watch_key.split("|")[1] if "|" in watch_key else "unknown")
                whitelist = watch_data.get("whitelist", [])
                blacklist = watch_data.get("blacklist", [])
                whitelist_regex = watch_data.get("whitelist_regex", [])
                blacklist_regex = watch_data.get("blacklist_regex", [])
                preserve_source = watch_data.get("preserve_forward_source", False)
                forward_mode = watch_data.get("forward_mode", "full")
                extract_patterns = watch_data.get("extract_patterns", [])
                record_mode = watch_data.get("record_mode", False)
            else:
                # Old format compatibility
                source_id = watch_key
                dest = watch_data
                whitelist = []
                blacklist = []
                whitelist_regex = []
                blacklist_regex = []
                preserve_source = False
                forward_mode = "full"
                extract_patterns = []
                record_mode = False
            
            # Handle None values
            if source_id is None:
                source_id = "未知来源"
            if dest is None:
                dest = "未知目标"
            
            text = f"**📋 监控任务详情**\n\n"
            text += f"**来源：** `{source_id}`\n"
            
            if record_mode:
                text += f"**模式：** 📝 记录模式（保存到网页）\n\n"
            else:
                text += f"**目标：** `{dest}`\n\n"
                text += f"**转发模式：** {'🎯 提取模式' if forward_mode == 'extract' else '📦 完整转发'}\n"
                if preserve_source:
                    text += f"**保留来源：** ✅ 是\n"
                else:
                    text += f"**保留来源：** ❌ 否\n"
            
            text += "\n**过滤规则：**\n"
            if whitelist:
                text += f"🟢 关键词白名单: `{', '.join(whitelist)}`\n"
            if blacklist:
                text += f"🔴 关键词黑名单: `{', '.join(blacklist)}`\n"
            if whitelist_regex:
                text += f"🟢 正则白名单: `{', '.join(whitelist_regex)}`\n"
            if blacklist_regex:
                text += f"🔴 正则黑名单: `{', '.join(blacklist_regex)}`\n"
            if not (whitelist or blacklist or whitelist_regex or blacklist_regex):
                text += "⏭ 无过滤（转发所有消息）\n"
            
            if forward_mode == "extract" and extract_patterns:
                text += f"\n**提取规则：**\n"
                for pattern in extract_patterns:
                    text += f"• `{pattern}`\n"
            
            buttons = [[InlineKeyboardButton("✏️ 编辑过滤规则", callback_data=f"edit_filter_{task_id}")]]
            
            if not record_mode:
                buttons.append([InlineKeyboardButton("🔄 切换转发模式", callback_data=f"edit_mode_{task_id}")])
                buttons.append([InlineKeyboardButton("📤 切换保留来源", callback_data=f"edit_preserve_{task_id}")])
            
            buttons.append([InlineKeyboardButton("🗑 删除此监控", callback_data=f"watch_remove_{task_id}")])
            buttons.append([InlineKeyboardButton("🔙 返回列表", callback_data="watch_list")])
            
            keyboard = InlineKeyboardMarkup(buttons)
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer()
        
        elif data.startswith("watch_remove_"):
            task_id = int(data.split("_")[2])
            watch_config = load_watch_config()
            
            if user_id not in watch_config or not watch_config[user_id]:
                callback_query.answer("❌ 监控任务不存在", show_alert=True)
                return
            
            if task_id < 1 or task_id > len(watch_config[user_id]):
                callback_query.answer("❌ 任务编号无效", show_alert=True)
                return
            
            watch_key = list(watch_config[user_id].keys())[task_id - 1]
            watch_data = watch_config[user_id][watch_key]
            
            if isinstance(watch_data, dict):
                # New format with source|dest key
                source_id = watch_data.get("source", watch_key.split("|")[0] if "|" in watch_key else watch_key)
                dest_id = watch_data.get("dest", watch_key.split("|")[1] if "|" in watch_key else "unknown")
            else:
                # Old format compatibility
                source_id = watch_key
                dest_id = watch_data
            
            # Handle None values
            if source_id is None:
                source_id = "未知来源"
            if dest_id is None:
                dest_id = "未知目标"
            
            del watch_config[user_id][watch_key]
            
            if not watch_config[user_id]:
                del watch_config[user_id]
            
            save_watch_config(watch_config)
            reload_monitored_sources()
            
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回监控管理", callback_data="menu_watch")]])
            text = f"**✅ 监控任务已删除**\n\n来源：`{source_id}`\n目标：`{dest_id}`"
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer("✅ 删除成功")
        
        elif data.startswith("set_dest_"):
            dest_choice = data.split("_")[2]
            
            if user_id not in user_states or "source_id" not in user_states[user_id]:
                callback_query.answer("❌ 会话已过期，请重新开始", show_alert=True)
                return
            
            if dest_choice == "me":
                user_states[user_id]["dest_id"] = "me"
                user_states[user_id]["dest_name"] = "个人收藏"
            
            show_filter_options(chat_id, message_id, user_id)
            callback_query.answer()
        
        elif data == "mode_single":
            if user_id not in user_states or "source_id" not in user_states[user_id]:
                callback_query.answer("❌ 会话已过期，请重新开始", show_alert=True)
                return
            
            user_states[user_id]["dest_id"] = None
            user_states[user_id]["dest_name"] = "记录模式"
            user_states[user_id]["record_mode"] = True
            
            show_filter_options_single(chat_id, message_id, user_id)
            callback_query.answer()
        
        elif data == "mode_forward":
            if user_id not in user_states or "source_id" not in user_states[user_id]:
                callback_query.answer("❌ 会话已过期，请重新开始", show_alert=True)
                return
            
            user_states[user_id]["action"] = "choose_dest"
            user_states[user_id]["record_mode"] = False
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("💾 保存到收藏夹", callback_data="set_dest_me")],
                [InlineKeyboardButton("📤 自定义目标", callback_data="dest_custom")],
                [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]
            ])
            
            source_name = user_states[user_id].get("source_name", "未知")
            
            text = "**➕ 添加监控任务**\n\n"
            text += f"✅ 来源已设置：`{source_name}`\n\n"
            text += "**步骤 3：** 选择转发目标\n\n"
            text += "💾 **保存到收藏夹** - 转发到你的个人收藏\n"
            text += "📤 **自定义目标** - 转发到其他频道/群组"
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer()
        
        elif data == "dest_custom":
            user_states[user_id]["action"] = "add_dest"
            
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]])
            
            text = "**➕ 添加监控任务**\n\n"
            text += "**步骤 3：** 请发送目标频道/群组\n\n"
            text += "可以发送：\n"
            text += "• 频道/群组用户名（如 `@channel_name`）\n"
            text += "• 频道/群组ID（如 `-1001234567890`）\n"
            text += "• 转发一条来自该频道/群组的消息\n\n"
            text += "💡 机器人需要有发送消息的权限"
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer()
        
        elif data == "filter_none":
            if user_id not in user_states:
                callback_query.answer("❌ 会话已过期", show_alert=True)
                return
            
            user_states[user_id]["whitelist"] = []
            user_states[user_id]["blacklist"] = []
            user_states[user_id]["whitelist_regex"] = []
            user_states[user_id]["blacklist_regex"] = []
            show_preserve_source_options(chat_id, message_id, user_id)
            callback_query.answer()
        
        elif data == "filter_none_single":
            if user_id not in user_states:
                callback_query.answer("❌ 会话已过期", show_alert=True)
                return
            
            user_states[user_id]["whitelist"] = []
            user_states[user_id]["blacklist"] = []
            user_states[user_id]["whitelist_regex"] = []
            user_states[user_id]["blacklist_regex"] = []
            
            msg = bot.send_message(chat_id, "⏳ 正在完成设置...")
            bot.delete_messages(chat_id, [message_id])
            complete_watch_setup_single(msg.chat.id, msg.id, user_id, [], [], [], [])
            callback_query.answer()
        
        elif data == "filter_regex_whitelist":
            user_states[user_id]["action"] = "add_regex_whitelist"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⏭ 跳过", callback_data="skip_regex_whitelist")],
                [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]
            ])
            
            text = "**➕ 添加监控任务**\n\n"
            text += "**步骤 3：设置正则白名单**\n\n"
            text += "请发送正则表达式，用逗号分隔\n\n"
            text += "示例：`https?://[^\\s]+,\\d{6,}`\n\n"
            text += "💡 只有匹配这些正则的消息才会被转发"
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer()
        
        elif data == "filter_regex_blacklist":
            user_states[user_id]["action"] = "add_regex_blacklist"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⏭ 跳过", callback_data="skip_regex_blacklist")],
                [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]
            ])
            
            text = "**➕ 添加监控任务**\n\n"
            text += "**步骤 3：设置正则黑名单**\n\n"
            text += "请发送正则表达式，用逗号分隔\n\n"
            text += "示例：`广告|推广|垃圾`\n\n"
            text += "💡 匹配这些正则的消息不会被转发"
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer()
        
        elif data == "skip_regex_whitelist":
            if user_id in user_states:
                user_states[user_id]["whitelist_regex"] = []
                msg = bot.send_message(chat_id, "⏳ 继续设置...")
                show_filter_options(chat_id, msg.id, user_id)
                bot.delete_messages(chat_id, [message_id])
                callback_query.answer("已跳过正则白名单")
        
        elif data == "skip_regex_blacklist":
            if user_id in user_states:
                user_states[user_id]["blacklist_regex"] = []
                msg = bot.send_message(chat_id, "⏳ 继续设置...")
                show_filter_options(chat_id, msg.id, user_id)
                bot.delete_messages(chat_id, [message_id])
                callback_query.answer("已跳过正则黑名单")
        
        elif data == "filter_whitelist":
            user_states[user_id]["action"] = "add_whitelist"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⏭ 跳过", callback_data="skip_whitelist")],
                [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]
            ])
            
            text = "**➕ 添加监控任务**\n\n"
            text += "**步骤 3：设置白名单**\n\n"
            text += "请发送白名单关键词，用逗号分隔\n\n"
            text += "示例：`重要,紧急,通知`\n\n"
            text += "💡 只有包含这些关键词的消息才会被转发"
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer()
        
        elif data == "filter_blacklist":
            user_states[user_id]["action"] = "add_blacklist"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⏭ 跳过", callback_data="skip_blacklist")],
                [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]
            ])
            
            text = "**➕ 添加监控任务**\n\n"
            text += "**步骤 3：设置黑名单**\n\n"
            text += "请发送黑名单关键词，用逗号分隔\n\n"
            text += "示例：`广告,推广,垃圾`\n\n"
            text += "💡 包含这些关键词的消息不会被转发"
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer()
        
        elif data == "skip_whitelist":
            if user_id in user_states:
                user_states[user_id]["whitelist"] = []
                msg = bot.send_message(chat_id, "⏳ 继续设置...")
                show_filter_options(chat_id, msg.id, user_id)
                bot.delete_messages(chat_id, [message_id])
                callback_query.answer("已跳过关键词白名单")
        
        elif data == "skip_blacklist":
            if user_id in user_states:
                user_states[user_id]["blacklist"] = []
                msg = bot.send_message(chat_id, "⏳ 继续设置...")
                show_filter_options(chat_id, msg.id, user_id)
                bot.delete_messages(chat_id, [message_id])
                callback_query.answer("已跳过关键词黑名单")
        
        elif data.startswith("preserve_"):
            preserve = data.split("_")[1] == "yes"
            
            if user_id not in user_states:
                callback_query.answer("❌ 会话已过期", show_alert=True)
                return
            
            whitelist = user_states[user_id].get("whitelist", [])
            blacklist = user_states[user_id].get("blacklist", [])
            whitelist_regex = user_states[user_id].get("whitelist_regex", [])
            blacklist_regex = user_states[user_id].get("blacklist_regex", [])
            
            # Show forward mode selection
            show_forward_mode_options(chat_id, message_id, user_id, whitelist, blacklist, whitelist_regex, blacklist_regex, preserve)
            callback_query.answer()
        
        elif data.startswith("edit_preserve_"):
            task_id = int(data.split("_")[2])
            watch_config = load_watch_config()
            
            if user_id not in watch_config or not watch_config[user_id]:
                callback_query.answer("❌ 监控任务不存在", show_alert=True)
                return
            
            if task_id < 1 or task_id > len(watch_config[user_id]):
                callback_query.answer("❌ 任务编号无效", show_alert=True)
                return
            
            watch_key = list(watch_config[user_id].keys())[task_id - 1]
            
            if isinstance(watch_config[user_id][watch_key], dict):
                current_preserve = watch_config[user_id][watch_key].get("preserve_forward_source", False)
                watch_config[user_id][watch_key]["preserve_forward_source"] = not current_preserve
            else:
                # Old format compatibility - convert to new format
                old_dest = watch_config[user_id][watch_key]
                source_id = watch_key
                watch_config[user_id][watch_key] = {
                    "source": source_id,
                    "dest": old_dest,
                    "whitelist": [],
                    "blacklist": [],
                    "preserve_forward_source": True
                }
            
            save_watch_config(watch_config)
            
            # Refresh the view
            callback_query.data = f"watch_view_{task_id}"
            callback_handler(client, callback_query)
            return
        
        elif data.startswith("edit_mode_"):
            task_id = int(data.split("_")[2])
            watch_config = load_watch_config()
            
            if user_id not in watch_config or not watch_config[user_id]:
                callback_query.answer("❌ 监控任务不存在", show_alert=True)
                return
            
            if task_id < 1 or task_id > len(watch_config[user_id]):
                callback_query.answer("❌ 任务编号无效", show_alert=True)
                return
            
            watch_key = list(watch_config[user_id].keys())[task_id - 1]
            
            if isinstance(watch_config[user_id][watch_key], dict):
                current_mode = watch_config[user_id][watch_key].get("forward_mode", "full")
            else:
                current_mode = "full"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📦 完整转发", callback_data=f"setmode_full_{task_id}")],
                [InlineKeyboardButton("🎯 提取模式", callback_data=f"setmode_extract_{task_id}")],
                [InlineKeyboardButton("🔙 返回", callback_data=f"watch_view_{task_id}")]
            ])
            
            text = f"**🔄 选择转发模式**\n\n"
            text += f"当前模式：**{'🎯 提取模式' if current_mode == 'extract' else '📦 完整转发'}**\n\n"
            text += "📦 **完整转发** - 转发整条消息\n"
            text += "🎯 **提取模式** - 使用正则提取特定内容后转发"
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer()
        
        elif data.startswith("setmode_"):
            parts = data.split("_")
            mode = parts[1]
            task_id = int(parts[2])
            
            watch_config = load_watch_config()
            
            if user_id not in watch_config or not watch_config[user_id]:
                callback_query.answer("❌ 监控任务不存在", show_alert=True)
                return
            
            if task_id < 1 or task_id > len(watch_config[user_id]):
                callback_query.answer("❌ 任务编号无效", show_alert=True)
                return
            
            watch_key = list(watch_config[user_id].keys())[task_id - 1]
            
            if isinstance(watch_config[user_id][watch_key], dict):
                watch_config[user_id][watch_key]["forward_mode"] = mode
                if mode == "extract" and not watch_config[user_id][watch_key].get("extract_patterns"):
                    # Extract source_id for user_states
                    source_id = watch_config[user_id][watch_key].get("source", watch_key.split("|")[0] if "|" in watch_key else watch_key)
                    
                    user_states[user_id] = {
                        "action": "edit_extract_patterns",
                        "task_id": task_id,
                        "watch_key": watch_key
                    }
                    
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("❌ 取消", callback_data=f"watch_view_{task_id}")]
                    ])
                    
                    text = "**🎯 设置提取规则**\n\n"
                    text += "请发送提取用的正则表达式，用逗号分隔\n\n"
                    text += "示例：`https?://[^\\s]+,\\d{6,}`\n\n"
                    text += "💡 消息匹配过滤规则后，将使用这些正则提取内容并转发"
                    
                    bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
                    callback_query.answer("请输入提取规则")
                    save_watch_config(watch_config)
                    return
            else:
                # Old format compatibility - convert to new format
                old_dest = watch_config[user_id][watch_key]
                source_id = watch_key
                watch_config[user_id][watch_key] = {
                    "source": source_id,
                    "dest": old_dest,
                    "whitelist": [],
                    "blacklist": [],
                    "preserve_forward_source": False,
                    "forward_mode": mode,
                    "extract_patterns": []
                }
            
            save_watch_config(watch_config)
            
            # Refresh the view
            callback_query.data = f"watch_view_{task_id}"
            callback_handler(client, callback_query)
            return
        
        elif data.startswith("edit_filter_"):
            task_id = int(data.split("_")[2])
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🟢 修改关键词白名单", callback_data=f"editf_kw_white_{task_id}")],
                [InlineKeyboardButton("🔴 修改关键词黑名单", callback_data=f"editf_kw_black_{task_id}")],
                [InlineKeyboardButton("🟢 修改正则白名单", callback_data=f"editf_re_white_{task_id}")],
                [InlineKeyboardButton("🔴 修改正则黑名单", callback_data=f"editf_re_black_{task_id}")],
                [InlineKeyboardButton("🎯 修改提取规则", callback_data=f"editf_extract_{task_id}")],
                [InlineKeyboardButton("🔙 返回", callback_data=f"watch_view_{task_id}")]
            ])
            
            text = "**✏️ 编辑过滤规则**\n\n"
            text += "选择要修改的规则：\n\n"
            text += "🟢 **关键词白名单** - 包含关键词才转发\n"
            text += "🔴 **关键词黑名单** - 包含关键词不转发\n"
            text += "🟢 **正则白名单** - 匹配正则才转发\n"
            text += "🔴 **正则黑名单** - 匹配正则不转发\n"
            text += "🎯 **提取规则** - 提取模式的正则表达式"
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer()
        
        elif data.startswith("editf_"):
            parts = data.split("_")
            filter_type = parts[1]
            color = parts[2]
            task_id = int(parts[3])
            
            user_states[user_id] = {
                "action": f"edit_filter_{filter_type}_{color}",
                "task_id": task_id
            }
            
            watch_config = load_watch_config()
            watch_key = list(watch_config[user_id].keys())[task_id - 1]
            user_states[user_id]["watch_key"] = watch_key
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑 清空", callback_data=f"clear_filter_{filter_type}_{color}_{task_id}")],
                [InlineKeyboardButton("❌ 取消", callback_data=f"watch_view_{task_id}")]
            ])
            
            if filter_type == "kw":
                filter_name = "关键词白名单" if color == "white" else "关键词黑名单"
                example = "重要,紧急,通知" if color == "white" else "广告,推广,垃圾"
            elif filter_type == "re":
                filter_name = "正则白名单" if color == "white" else "正则黑名单"
                example = "https?://[^\\s]+,\\d{6,}" if color == "white" else "广告|推广"
            else:  # extract
                filter_name = "提取规则"
                example = "https?://[^\\s]+,\\d{6,}"
            
            text = f"**✏️ 修改{filter_name}**\n\n"
            text += f"请发送新的规则，用逗号分隔\n\n"
            text += f"示例：`{example}`\n\n"
            text += "💡 发送新规则将覆盖原有规则\n"
            text += "💡 点击\"清空\"可删除所有规则"
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer("请输入新规则")
        
        elif data.startswith("clear_filter_"):
            parts = data.split("_")
            filter_type = parts[2]
            color = parts[3]
            task_id = int(parts[4])
            
            watch_config = load_watch_config()
            
            if user_id not in watch_config or not watch_config[user_id]:
                callback_query.answer("❌ 监控任务不存在", show_alert=True)
                return
            
            if task_id < 1 or task_id > len(watch_config[user_id]):
                callback_query.answer("❌ 任务编号无效", show_alert=True)
                return
            
            watch_key = list(watch_config[user_id].keys())[task_id - 1]
            
            if isinstance(watch_config[user_id][watch_key], dict):
                if filter_type == "kw":
                    key = "whitelist" if color == "white" else "blacklist"
                elif filter_type == "re":
                    key = "whitelist_regex" if color == "white" else "blacklist_regex"
                else:  # extract
                    key = "extract_patterns"
                
                watch_config[user_id][watch_key][key] = []
                save_watch_config(watch_config)
                
                callback_query.answer("✅ 已清空")
            
            # Refresh the view
            callback_query.data = f"watch_view_{task_id}"
            callback_handler(client, callback_query)
            return
        
        elif data.startswith("fwdmode_"):
            mode = data.split("_")[1]
            
            if user_id not in user_states:
                callback_query.answer("❌ 会话已过期", show_alert=True)
                return
            
            if mode == "extract":
                user_states[user_id]["action"] = "add_extract_patterns"
                
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]
                ])
                
                text = "**➕ 添加监控任务**\n\n"
                text += "**设置提取规则**\n\n"
                text += "请发送提取用的正则表达式，用逗号分隔\n\n"
                text += "示例：`https?://[^\\s]+,\\d{6,}`\n\n"
                text += "💡 消息匹配过滤规则后，将使用这些正则提取内容并转发"
                
                bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
                callback_query.answer("请输入提取规则")
            else:
                whitelist = user_states[user_id].get("whitelist", [])
                blacklist = user_states[user_id].get("blacklist", [])
                whitelist_regex = user_states[user_id].get("whitelist_regex", [])
                blacklist_regex = user_states[user_id].get("blacklist_regex", [])
                preserve_source = user_states[user_id].get("preserve_source", False)
                
                complete_watch_setup(chat_id, message_id, user_id, whitelist, blacklist, whitelist_regex, blacklist_regex, preserve_source, "full", [])
                callback_query.answer("✅ 监控已添加")
        
    except Exception as e:
        print(f"Callback error: {e}")
        callback_query.answer(f"❌ 错误: {str(e)}", show_alert=True)

def show_filter_options(chat_id, message_id, user_id):
    source_name = user_states[user_id].get("source_name", "未知")
    dest_name = user_states[user_id].get("dest_name", "未知")
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 关键词白名单", callback_data="filter_whitelist")],
        [InlineKeyboardButton("🔴 关键词黑名单", callback_data="filter_blacklist")],
        [InlineKeyboardButton("🟢 正则白名单", callback_data="filter_regex_whitelist")],
        [InlineKeyboardButton("🔴 正则黑名单", callback_data="filter_regex_blacklist")],
        [InlineKeyboardButton("⏭ 不设置过滤", callback_data="filter_none")],
        [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]
    ])
    
    text = "**➕ 添加监控任务**\n\n"
    text += f"来源：`{source_name}`\n"
    text += f"目标：`{dest_name}`\n\n"
    text += "**步骤 3：** 是否需要过滤规则？\n\n"
    text += "🟢 **关键词白名单** - 包含关键词才转发\n"
    text += "🔴 **关键词黑名单** - 包含关键词不转发\n"
    text += "🟢 **正则白名单** - 匹配正则才转发\n"
    text += "🔴 **正则黑名单** - 匹配正则不转发\n"
    text += "⏭ **不设置** - 转发所有消息\n\n"
    text += "💡 可以设置多种规则，按顺序生效"
    
    bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)

def show_filter_options_single(chat_id, message_id, user_id):
    source_name = user_states[user_id].get("source_name", "未知")
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 关键词白名单", callback_data="filter_whitelist")],
        [InlineKeyboardButton("🔴 关键词黑名单", callback_data="filter_blacklist")],
        [InlineKeyboardButton("🟢 正则白名单", callback_data="filter_regex_whitelist")],
        [InlineKeyboardButton("🔴 正则黑名单", callback_data="filter_regex_blacklist")],
        [InlineKeyboardButton("⏭ 不设置过滤", callback_data="filter_none_single")],
        [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]
    ])
    
    text = "**➕ 添加监控任务（记录模式）**\n\n"
    text += f"来源：`{source_name}`\n"
    text += f"模式：📝 **记录模式**（保存到网页笔记）\n\n"
    text += "**步骤 3：** 是否需要过滤规则？\n\n"
    text += "🟢 **关键词白名单** - 包含关键词才记录\n"
    text += "🔴 **关键词黑名单** - 包含关键词不记录\n"
    text += "🟢 **正则白名单** - 匹配正则才记录\n"
    text += "🔴 **正则黑名单** - 匹配正则不记录\n"
    text += "⏭ **不设置** - 记录所有消息\n\n"
    text += "💡 可以设置多种规则，按顺序生效"
    
    bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)

def show_preserve_source_options(chat_id, message_id, user_id):
    source_name = user_states[user_id].get("source_name", "未知")
    dest_name = user_states[user_id].get("dest_name", "未知")
    whitelist = user_states[user_id].get("whitelist", [])
    blacklist = user_states[user_id].get("blacklist", [])
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ 否（推荐）", callback_data="preserve_no")],
        [InlineKeyboardButton("✅ 是", callback_data="preserve_yes")],
        [InlineKeyboardButton("🔙 取消", callback_data="menu_watch")]
    ])
    
    text = "**➕ 添加监控任务**\n\n"
    text += f"来源：`{source_name}`\n"
    text += f"目标：`{dest_name}`\n"
    if whitelist:
        text += f"白名单：`{', '.join(whitelist)}`\n"
    if blacklist:
        text += f"黑名单：`{', '.join(blacklist)}`\n"
    text += "\n**最后一步：** 是否保留转发来源信息？\n\n"
    text += "✅ **是** - 显示 \"Forwarded from...\"\n"
    text += "❌ **否** - 不显示来源（推荐）"
    
    bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)

def show_forward_mode_options(chat_id, message_id, user_id, whitelist, blacklist, whitelist_regex, blacklist_regex, preserve_source):
    source_name = user_states[user_id].get("source_name", "未知")
    dest_name = user_states[user_id].get("dest_name", "未知")
    
    user_states[user_id]["whitelist"] = whitelist
    user_states[user_id]["blacklist"] = blacklist
    user_states[user_id]["whitelist_regex"] = whitelist_regex
    user_states[user_id]["blacklist_regex"] = blacklist_regex
    user_states[user_id]["preserve_source"] = preserve_source
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 完整转发", callback_data="fwdmode_full")],
        [InlineKeyboardButton("🎯 提取模式", callback_data="fwdmode_extract")],
        [InlineKeyboardButton("🔙 取消", callback_data="menu_watch")]
    ])
    
    text = "**➕ 添加监控任务**\n\n"
    text += f"来源：`{source_name}`\n"
    text += f"目标：`{dest_name}`\n\n"
    text += "**选择转发模式：**\n\n"
    text += "📦 **完整转发** - 转发整条消息（默认）\n"
    text += "🎯 **提取模式** - 使用正则提取特定内容后转发\n\n"
    text += "💡 提取模式需要设置提取规则"
    
    bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)

def complete_watch_setup(chat_id, message_id, user_id, whitelist, blacklist, whitelist_regex, blacklist_regex, preserve_source, forward_mode, extract_patterns):
    try:
        source_id = user_states[user_id]["source_id"]
        source_name = user_states[user_id]["source_name"]
        dest_id = user_states[user_id]["dest_id"]
        dest_name = user_states[user_id]["dest_name"]
        
        watch_config = load_watch_config()
        
        if user_id not in watch_config:
            watch_config[user_id] = {}
        
        # Use composite key: source_id|dest_id to allow one source to multiple targets
        watch_key = f"{source_id}|{dest_id}"
        
        if watch_key in watch_config[user_id]:
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="menu_watch")]])
            bot.edit_message_text(chat_id, message_id, f"**⚠️ 该监控任务已存在**\n\n来源：`{source_name}`\n目标：`{dest_name}`", reply_markup=keyboard)
            del user_states[user_id]
            return
        
        watch_config[user_id][watch_key] = {
            "source": source_id,
            "dest": dest_id,
            "whitelist": whitelist,
            "blacklist": blacklist,
            "whitelist_regex": whitelist_regex,
            "blacklist_regex": blacklist_regex,
            "preserve_forward_source": preserve_source,
            "forward_mode": forward_mode,
            "extract_patterns": extract_patterns,
            "record_mode": False
        }
        save_watch_config(watch_config)
        reload_monitored_sources()
        
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回监控管理", callback_data="menu_watch")]])
        
        result_msg = f"**✅ 监控任务添加成功！**\n\n"
        result_msg += f"来源：`{source_name}`\n"
        result_msg += f"目标：`{dest_name}`\n"
        result_msg += f"转发模式：{'🎯 提取模式' if forward_mode == 'extract' else '📦 完整转发'}\n"
        if whitelist:
            result_msg += f"关键词白名单：`{', '.join(whitelist)}`\n"
        if blacklist:
            result_msg += f"关键词黑名单：`{', '.join(blacklist)}`\n"
        if whitelist_regex:
            result_msg += f"正则白名单：`{', '.join(whitelist_regex)}`\n"
        if blacklist_regex:
            result_msg += f"正则黑名单：`{', '.join(blacklist_regex)}`\n"
        if extract_patterns:
            result_msg += f"提取规则：`{', '.join(extract_patterns)}`\n"
        if preserve_source:
            result_msg += f"保留来源：`是`\n"
        result_msg += "\n从现在开始，新消息将自动转发 🎉"
        
        bot.edit_message_text(chat_id, message_id, result_msg, reply_markup=keyboard)
        del user_states[user_id]
        
    except Exception as e:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="menu_watch")]])
        bot.edit_message_text(chat_id, message_id, f"**❌ 错误：** `{str(e)}`", reply_markup=keyboard)
        if user_id in user_states:
            del user_states[user_id]

def complete_watch_setup_single(chat_id, message_id, user_id, whitelist, blacklist, whitelist_regex, blacklist_regex):
    try:
        source_id = user_states[user_id]["source_id"]
        source_name = user_states[user_id]["source_name"]
        
        watch_config = load_watch_config()
        
        if user_id not in watch_config:
            watch_config[user_id] = {}
        
        # Use composite key with "record" as dest for record mode
        watch_key = f"{source_id}|record"
        
        if watch_key in watch_config[user_id]:
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="menu_watch")]])
            bot.edit_message_text(chat_id, message_id, f"**⚠️ 该监控任务已存在**\n\n来源：`{source_name}`\n模式：记录模式", reply_markup=keyboard)
            del user_states[user_id]
            return
        
        watch_config[user_id][watch_key] = {
            "source": source_id,
            "dest": None,
            "whitelist": whitelist,
            "blacklist": blacklist,
            "whitelist_regex": whitelist_regex,
            "blacklist_regex": blacklist_regex,
            "preserve_forward_source": False,
            "forward_mode": "full",
            "extract_patterns": [],
            "record_mode": True
        }
        save_watch_config(watch_config)
        reload_monitored_sources()
        
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回监控管理", callback_data="menu_watch")]])
        
        result_msg = f"**✅ 监控任务添加成功！**\n\n"
        result_msg += f"来源：`{source_name}`\n"
        result_msg += f"模式：📝 **记录模式**\n"
        if whitelist:
            result_msg += f"关键词白名单：`{', '.join(whitelist)}`\n"
        if blacklist:
            result_msg += f"关键词黑名单：`{', '.join(blacklist)}`\n"
        if whitelist_regex:
            result_msg += f"正则白名单：`{', '.join(whitelist_regex)}`\n"
        if blacklist_regex:
            result_msg += f"正则黑名单：`{', '.join(blacklist_regex)}`\n"
        result_msg += "\n从现在开始，新消息将自动记录到网页笔记 📝"
        
        bot.edit_message_text(chat_id, message_id, result_msg, reply_markup=keyboard)
        del user_states[user_id]
        
    except Exception as e:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="menu_watch")]])
        bot.edit_message_text(chat_id, message_id, f"**❌ 错误：** `{str(e)}`", reply_markup=keyboard)
        if user_id in user_states:
            del user_states[user_id]

def handle_add_source(message, user_id):
    try:
        if message.forward_from_chat:
            source_id = str(message.forward_from_chat.id)
            source_name = message.forward_from_chat.title or message.forward_from_chat.username or source_id
        else:
            text = message.text.strip()
            # Special handling for "me" - monitor Saved Messages (user's own favorites)
            if text.lower() == "me":
                source_id = str(message.from_user.id)
                source_name = "我的收藏夹 (Saved Messages)"
            elif text.startswith('@'):
                source_info = acc.get_chat(text)
                source_id = str(source_info.id)
                source_name = source_info.title or source_info.username or source_id
            else:
                try:
                    source_chat_id = int(text)
                    source_info = acc.get_chat(source_chat_id)
                    source_id = str(source_info.id)
                    source_name = source_info.title or source_info.username or source_id
                except ValueError:
                    bot.send_message(message.chat.id, "**❌ 无效的频道/群组ID**\n\n请输入正确的格式")
                    return
        
        user_states[user_id]["source_id"] = source_id
        user_states[user_id]["source_name"] = source_name
        user_states[user_id]["action"] = "choose_mode"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 单一监控（记录模式）", callback_data="mode_single")],
            [InlineKeyboardButton("➡️ 转发到另一个", callback_data="mode_forward")],
            [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]
        ])
        
        text = "**➕ 添加监控任务**\n\n"
        text += f"✅ 来源已设置：`{source_name}`\n\n"
        text += "**步骤 2：** 选择监控模式\n\n"
        text += "📝 **单一监控（记录模式）** - 只监控这一个频道，消息保存到网页笔记\n"
        text += "➡️ **转发到另一个** - 从这个频道转发消息到另一个频道/群组"
        
        bot.send_message(message.chat.id, text, reply_markup=keyboard)
    
    except ChannelPrivate:
        bot.send_message(message.chat.id, "**❌ 无法访问该频道/群组**\n\n请确保账号已加入")
    except UsernameInvalid:
        bot.send_message(message.chat.id, "**❌ 频道/群组用户名无效**\n\n请检查输入")
    except Exception as e:
        bot.send_message(message.chat.id, f"**❌ 错误：** `{str(e)}`")

def handle_add_dest(message, user_id):
    try:
        if message.forward_from_chat:
            dest_id = str(message.forward_from_chat.id)
            dest_name = message.forward_from_chat.title or message.forward_from_chat.username or dest_id
        else:
            text = message.text.strip()
            if text.lower() == "me":
                dest_id = "me"
                dest_name = "个人收藏"
            elif text.startswith('@'):
                dest_info = acc.get_chat(text)
                dest_id = str(dest_info.id)
                dest_name = dest_info.title or dest_info.username or dest_id
            else:
                try:
                    dest_chat_id = int(text)
                    dest_info = acc.get_chat(dest_chat_id)
                    dest_id = str(dest_info.id)
                    dest_name = dest_info.title or dest_info.username or dest_id
                except ValueError:
                    bot.send_message(message.chat.id, "**❌ 无效的频道/群组ID**\n\n请输入正确的格式")
                    return
        
        user_states[user_id]["dest_id"] = dest_id
        user_states[user_id]["dest_name"] = dest_name
        
        msg = bot.send_message(message.chat.id, "⏳ 正在设置...")
        show_filter_options(message.chat.id, msg.id, user_id)
    
    except ChannelPrivate:
        bot.send_message(message.chat.id, "**❌ 无法访问该频道/群组**\n\n请确保机器人有发送权限")
    except UsernameInvalid:
        bot.send_message(message.chat.id, "**❌ 频道/群组用户名无效**\n\n请检查输入")
    except Exception as e:
        bot.send_message(message.chat.id, f"**❌ 错误：** `{str(e)}`")

# Handle user text input during multi-step interactions
@bot.on_message(filters.text & filters.private & ~filters.command(["start", "help", "watch"]))
def save(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    print(message.text)
    user_id = str(message.from_user.id)
    
    if user_id in user_states:
        action = user_states[user_id].get("action")
        
        if action == "add_source":
            handle_add_source(message, user_id)
            return
        
        elif action == "add_dest":
            handle_add_dest(message, user_id)
            return
        
        elif action == "add_whitelist":
            keywords = [kw.strip() for kw in message.text.split(',') if kw.strip()]
            if keywords:
                user_states[user_id]["whitelist"] = keywords
                msg = bot.send_message(message.chat.id, f"✅ 关键词白名单已设置：`{', '.join(keywords)}`\n\n⏳ 继续设置...")
                if user_states[user_id].get("record_mode"):
                    show_filter_options_single(message.chat.id, msg.id, user_id)
                else:
                    show_filter_options(message.chat.id, msg.id, user_id)
            else:
                bot.send_message(message.chat.id, "**❌ 请输入至少一个关键词**")
            return
        
        elif action == "add_blacklist":
            keywords = [kw.strip() for kw in message.text.split(',') if kw.strip()]
            if keywords:
                user_states[user_id]["blacklist"] = keywords
                msg = bot.send_message(message.chat.id, f"✅ 关键词黑名单已设置：`{', '.join(keywords)}`\n\n⏳ 继续设置...")
            else:
                user_states[user_id]["blacklist"] = []
                msg = bot.send_message(message.chat.id, "⏳ 继续设置...")
            if user_states[user_id].get("record_mode"):
                show_filter_options_single(message.chat.id, msg.id, user_id)
            else:
                show_filter_options(message.chat.id, msg.id, user_id)
            return
        
        elif action == "add_regex_whitelist":
            patterns = [p.strip() for p in message.text.split(',') if p.strip()]
            if patterns:
                try:
                    for pattern in patterns:
                        re.compile(pattern)
                    user_states[user_id]["whitelist_regex"] = patterns
                    msg = bot.send_message(message.chat.id, f"✅ 正则白名单已设置：`{', '.join(patterns)}`\n\n⏳ 继续设置...")
                    if user_states[user_id].get("record_mode"):
                        show_filter_options_single(message.chat.id, msg.id, user_id)
                    else:
                        show_filter_options(message.chat.id, msg.id, user_id)
                except re.error as e:
                    bot.send_message(message.chat.id, f"**❌ 正则表达式错误：** `{str(e)}`\n\n请重新输入")
            else:
                bot.send_message(message.chat.id, "**❌ 请输入至少一个正则表达式**")
            return
        
        elif action == "add_regex_blacklist":
            patterns = [p.strip() for p in message.text.split(',') if p.strip()]
            if patterns:
                try:
                    for pattern in patterns:
                        re.compile(pattern)
                    user_states[user_id]["blacklist_regex"] = patterns
                    msg = bot.send_message(message.chat.id, f"✅ 正则黑名单已设置：`{', '.join(patterns)}`\n\n⏳ 继续设置...")
                    if user_states[user_id].get("record_mode"):
                        show_filter_options_single(message.chat.id, msg.id, user_id)
                    else:
                        show_filter_options(message.chat.id, msg.id, user_id)
                except re.error as e:
                    bot.send_message(message.chat.id, f"**❌ 正则表达式错误：** `{str(e)}`\n\n请重新输入")
            else:
                bot.send_message(message.chat.id, "**❌ 请输入至少一个正则表达式**")
            return
        
        elif action == "add_extract_patterns":
            patterns = [p.strip() for p in message.text.split(',') if p.strip()]
            if patterns:
                try:
                    for pattern in patterns:
                        re.compile(pattern)
                    
                    whitelist = user_states[user_id].get("whitelist", [])
                    blacklist = user_states[user_id].get("blacklist", [])
                    whitelist_regex = user_states[user_id].get("whitelist_regex", [])
                    blacklist_regex = user_states[user_id].get("blacklist_regex", [])
                    preserve_source = user_states[user_id].get("preserve_source", False)
                    
                    msg = bot.send_message(message.chat.id, "⏳ 正在完成设置...")
                    complete_watch_setup(message.chat.id, msg.id, user_id, whitelist, blacklist, whitelist_regex, blacklist_regex, preserve_source, "extract", patterns)
                except re.error as e:
                    bot.send_message(message.chat.id, f"**❌ 正则表达式错误：** `{str(e)}`\n\n请重新输入")
            else:
                bot.send_message(message.chat.id, "**❌ 请输入至少一个正则表达式**")
            return
        
        elif action.startswith("edit_filter_"):
            parts = action.split("_")
            filter_type = parts[2]
            color = parts[3]
            task_id = user_states[user_id].get("task_id")
            watch_key = user_states[user_id].get("watch_key")
            
            watch_config = load_watch_config()
            user_id_str = str(message.from_user.id)
            
            if filter_type == "kw":
                keywords = [kw.strip() for kw in message.text.split(',') if kw.strip()]
                key = "whitelist" if color == "white" else "blacklist"
                watch_config[user_id_str][watch_key][key] = keywords
            elif filter_type == "re":
                patterns = [p.strip() for p in message.text.split(',') if p.strip()]
                try:
                    for pattern in patterns:
                        re.compile(pattern)
                    key = "whitelist_regex" if color == "white" else "blacklist_regex"
                    watch_config[user_id_str][watch_key][key] = patterns
                except re.error as e:
                    bot.send_message(message.chat.id, f"**❌ 正则表达式错误：** `{str(e)}`\n\n请重新输入")
                    return
            
            save_watch_config(watch_config)
            
            del user_states[user_id]
            
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回详情", callback_data=f"watch_view_{task_id}")]])
            bot.send_message(message.chat.id, "**✅ 规则已更新**", reply_markup=keyboard)
            return
        
        elif action == "edit_extract_patterns":
            patterns = [p.strip() for p in message.text.split(',') if p.strip()]
            task_id = user_states[user_id].get("task_id")
            watch_key = user_states[user_id].get("watch_key")
            
            if patterns:
                try:
                    for pattern in patterns:
                        re.compile(pattern)
                    
                    watch_config = load_watch_config()
                    user_id_str = str(message.from_user.id)
                    
                    if isinstance(watch_config[user_id_str][watch_key], dict):
                        watch_config[user_id_str][watch_key]["extract_patterns"] = patterns
                    
                    save_watch_config(watch_config)
                    del user_states[user_id]
                    
                    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回详情", callback_data=f"watch_view_{task_id}")]])
                    bot.send_message(message.chat.id, "**✅ 提取规则已设置**", reply_markup=keyboard)
                except re.error as e:
                    bot.send_message(message.chat.id, f"**❌ 正则表达式错误：** `{str(e)}`\n\n请重新输入")
            else:
                bot.send_message(message.chat.id, "**❌ 请输入至少一个正则表达式**")
            return

    # joining chats
    if "https://t.me/+" in message.text or "https://t.me/joinchat/" in message.text:

        if acc is None:
            bot.send_message(message.chat.id,f"**❌ 未设置 String Session**", reply_to_message_id=message.id)
            return

        try:
            try: acc.join_chat(message.text)
            except Exception as e: 
                bot.send_message(message.chat.id,f"**❌ 错误** : __{e}__", reply_to_message_id=message.id)
                return
            bot.send_message(message.chat.id,"**✅ 已加入频道**", reply_to_message_id=message.id)
        except UserAlreadyParticipant:
            bot.send_message(message.chat.id,"**✅ 已经加入该频道**", reply_to_message_id=message.id)
        except InviteHashExpired:
            bot.send_message(message.chat.id,"**❌ 无效链接**", reply_to_message_id=message.id)

    # getting message
    elif "https://t.me/" in message.text:

        datas = message.text.split("/")
        temp = datas[-1].replace("?single","").split("-")
        fromID = int(temp[0].strip())
        try: toID = int(temp[1].strip())
        except: toID = fromID

        for msgid in range(fromID, toID+1):

            # private
            if "https://t.me/c/" in message.text:
                chatid = int("-100" + datas[4])
                
                if acc is None:
                    bot.send_message(message.chat.id,f"**❌ 未设置 String Session**", reply_to_message_id=message.id)
                    return
                
                try: handle_private(message,chatid,msgid)
                except Exception as e: pass  # Silently ignore forwarding failures
            
            # bot
            elif "https://t.me/b/" in message.text:
                username = datas[4]
                
                if acc is None:
                    bot.send_message(message.chat.id,f"**❌ 未设置 String Session**", reply_to_message_id=message.id)
                    return
                try: handle_private(message,username,msgid)
                except Exception as e: pass  # Silently ignore forwarding failures

            # public
            else:
                username = datas[3]

                try: msg  = bot.get_messages(username,msgid)
                except UsernameNotOccupied: 
                    bot.send_message(message.chat.id,f"**❌ 该用户名未被占用**", reply_to_message_id=message.id)
                    return
                try:
                    if '?single' not in message.text:
                        bot.copy_message(message.chat.id, msg.chat.id, msg.id)
                    else:
                        bot.copy_media_group(message.chat.id, msg.chat.id, msg.id)
                except:
                    if acc is None:
                        bot.send_message(message.chat.id,f"**❌ 未设置 String Session**", reply_to_message_id=message.id)
                        return
                    try: handle_private(message,username,msgid)
                    except Exception as e: pass  # Silently ignore forwarding failures

            # wait time
            time.sleep(3)


# handle private
def handle_private(message: pyrogram.types.messages_and_media.message.Message, chatid: int, msgid: int):
        msg: pyrogram.types.messages_and_media.message.Message = acc.get_messages(chatid,msgid)
        msg_type = get_message_type(msg)

        if "Text" == msg_type:
            bot.send_message(message.chat.id, msg.text, entities=msg.entities)
            return

        smsg = bot.send_message(message.chat.id, '__⬇️ 下载中__', reply_to_message_id=message.id)
        dosta = threading.Thread(target=lambda:downstatus(f'{message.id}downstatus.txt',smsg),daemon=True)
        dosta.start()
        file = acc.download_media(msg, progress=progress, progress_args=[message,"down"])
        os.remove(f'{message.id}downstatus.txt')

        upsta = threading.Thread(target=lambda:upstatus(f'{message.id}upstatus.txt',smsg),daemon=True)
        upsta.start()
        
        if "Document" == msg_type:
            try:
                thumb = acc.download_media(msg.document.thumbs[0].file_id)
            except: thumb = None
            
            bot.send_document(message.chat.id, file, thumb=thumb, caption=msg.caption, caption_entities=msg.caption_entities, progress=progress, progress_args=[message,"up"])
            if thumb != None: os.remove(thumb)

        elif "Video" == msg_type:
            try: 
                thumb = acc.download_media(msg.video.thumbs[0].file_id)
            except: thumb = None

            bot.send_video(message.chat.id, file, duration=msg.video.duration, width=msg.video.width, height=msg.video.height, thumb=thumb, caption=msg.caption, caption_entities=msg.caption_entities, progress=progress, progress_args=[message,"up"])
            if thumb != None: os.remove(thumb)

        elif "Animation" == msg_type:
            bot.send_animation(message.chat.id, file)
               
        elif "Sticker" == msg_type:
            bot.send_sticker(message.chat.id, file)

        elif "Voice" == msg_type:
            bot.send_voice(message.chat.id, file, caption=msg.caption, thumb=thumb, caption_entities=msg.caption_entities, progress=progress, progress_args=[message,"up"])

        elif "Audio" == msg_type:
            try:
                thumb = acc.download_media(msg.audio.thumbs[0].file_id)
            except: thumb = None
                
            bot.send_audio(message.chat.id, file, caption=msg.caption, caption_entities=msg.caption_entities, progress=progress, progress_args=[message,"up"])   
            if thumb != None: os.remove(thumb)

        elif "Photo" == msg_type:
            bot.send_photo(message.chat.id, file, caption=msg.caption, caption_entities=msg.caption_entities)

        os.remove(file)
        if os.path.exists(f'{message.id}upstatus.txt'): os.remove(f'{message.id}upstatus.txt')
        bot.delete_messages(message.chat.id,[smsg.id])


# get the type of message
def get_message_type(msg: pyrogram.types.messages_and_media.message.Message):
    try:
        msg.document.file_id
        return "Document"
    except: pass

    try:
        msg.video.file_id
        return "Video"
    except: pass

    try:
        msg.animation.file_id
        return "Animation"
    except: pass

    try:
        msg.sticker.file_id
        return "Sticker"
    except: pass

    try:
        msg.voice.file_id
        return "Voice"
    except: pass

    try:
        msg.audio.file_id
        return "Audio"
    except: pass

    try:
        msg.photo.file_id
        return "Photo"
    except: pass

    try:
        msg.text
        return "Text"
    except: pass


USAGE = """**📌 公开频道/群组**

__直接发送帖子链接即可__

**🔒 私有频道/群组**

__首先发送频道邀请链接（如果 String Session 账号已加入则不需要）
然后发送帖子链接__

**🤖 机器人聊天**

__发送带有 '/b/'、机器人用户名和消息 ID 的链接，你可能需要使用一些非官方客户端来获取 ID，如下所示__

```
https://t.me/b/botusername/4321
```

**📦 批量下载**

__按照上述方式发送公开/私有帖子链接，使用 "from - to" 格式发送多条消息，如下所示__

```
https://t.me/xxxx/1001-1010

https://t.me/c/xxxx/101 - 120
```

__注意：中间的空格无关紧要__
"""

# Track media groups to process only once per task
processed_media_groups = set()
processed_media_groups_order = []


def register_processed_media_group(key):
    if not key:
        return
    processed_media_groups.add(key)
    processed_media_groups_order.append(key)
    if len(processed_media_groups_order) > 300:
        old_key = processed_media_groups_order.pop(0)
        processed_media_groups.discard(old_key)

# Message deduplication cache
processed_messages = {}
MESSAGE_CACHE_TTL = 5


def is_message_processed(message_id, chat_id):
    """Check if message has already been processed"""
    key = f"{chat_id}_{message_id}"
    if key in processed_messages:
        if time.time() - processed_messages[key] < MESSAGE_CACHE_TTL:
            return True
        else:
            del processed_messages[key]
    return False


def mark_message_processed(message_id, chat_id):
    """Mark message as processed"""
    key = f"{chat_id}_{message_id}"
    processed_messages[key] = time.time()


def cleanup_old_messages():
    """Clean up expired message records"""
    current_time = time.time()
    expired_keys = [key for key, timestamp in processed_messages.items() 
                    if current_time - timestamp > MESSAGE_CACHE_TTL]
    for key in expired_keys:
        del processed_messages[key]

# Build set of monitored source channels for efficient filtering
def build_monitored_sources():
    """Build a set of all monitored source chat IDs from watch config"""
    watch_config = load_watch_config()
    sources = set()
    
    for user_id, watches in watch_config.items():
        for watch_key, watch_data in watches.items():
            if isinstance(watch_data, dict):
                source = watch_data.get('source')
            else:
                # Old format: key is the source
                source = watch_key
            
            # Add to set if valid (exclude None and special values like "me")
            if source and source != 'me':
                sources.add(str(source))
    
    return sources

def reload_monitored_sources():
    """Reload the monitored sources set (call after config changes)"""
    global monitored_sources
    monitored_sources = build_monitored_sources()
    logger.info(f"🔄 监控源已更新: {monitored_sources if monitored_sources else '无'}")

# Initialize monitored sources set
monitored_sources = build_monitored_sources()
if monitored_sources:
    logger.info(f"📋 正在监控的源频道: {monitored_sources}")
else:
    logger.info(f"📋 当前没有配置监控源")

# Auto-forward handler for watched channels (lightweight - just enqueue messages)
if acc is not None:
    @acc.on_message(filters.channel | filters.group | filters.private)
    def auto_forward(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
        try:
            # Validate message object and its attributes
            if not message or not hasattr(message, 'chat') or not message.chat:
                logger.debug("跳过：消息对象无效或缺少 chat 属性")
                return
            
            # Validate chat ID
            if not hasattr(message.chat, 'id') or message.chat.id is None:
                logger.debug("跳过：消息缺少有效的 chat ID")
                return
            
            # Check for duplicate messages
            if not hasattr(message, 'id') or message.id is None:
                logger.debug("跳过：消息缺少有效的 message ID")
                return
            
            if is_message_processed(message.id, message.chat.id):
                logger.debug(f"⏭️ 跳过已处理的消息: chat_id={message.chat.id}, message_id={message.id}")
                return
            
            # Mark message as processed immediately to prevent duplicate processing
            mark_message_processed(message.id, message.chat.id)
            
            # Periodically clean up old message records
            if len(processed_messages) > 1000:
                cleanup_old_messages()
            
            # Early filter: check if message is from a monitored source
            source_chat_id = str(message.chat.id)
            if source_chat_id not in monitored_sources:
                # Not in monitored list, skip silently
                return
            
            # Log message reception (only for monitored sources)
            chat_id = message.chat.id
            chat_title = getattr(message.chat, 'title', None) or getattr(message.chat, 'username', None) or str(chat_id)
            message_preview = ""
            if message.text:
                message_preview = f"文本={message.text[:50]}..." if len(message.text) > 50 else f"文本={message.text}"
            elif message.caption:
                message_preview = f"标题={message.caption[:50]}..." if len(message.caption) > 50 else f"标题={message.caption}"
            elif message.photo:
                message_preview = "图片"
            elif message.video:
                message_preview = "视频"
            elif message.document:
                message_preview = "文档"
            elif message.media_group_id:
                message_preview = f"媒体组 (ID: {message.media_group_id})"
            else:
                message_preview = "其他类型"
            
            logger.info(f"📨 收到消息: chat_id={chat_id}, chat_name={chat_title}, 内容={message_preview}")
            
            # Ensure the peer is resolved to prevent "Peer id invalid" errors
            try:
                # Skip if chat_id is invalid or zero
                if not chat_id or chat_id == 0:
                    logger.debug(f"跳过：chat_id 无效 (chat_id={chat_id})")
                    return
                
                # Try to get chat info to ensure it's cached
                acc.get_chat(chat_id)
                logger.debug(f"✅ 频道信息已缓存: {chat_id}")
            except (ValueError, KeyError) as e:
                # Peer ID invalid or not found - skip this message silently
                error_msg = str(e)
                if "Peer id invalid" not in error_msg and "ID not found" not in error_msg:
                    logger.warning(f"⚠️ 跳过无法解析的频道 ID {chat_id}: {type(e).__name__}")
                return
            except Exception as e:
                # Other errors - log and skip
                logger.warning(f"⚠️ 无法访问频道 {chat_id}: {str(e)}")
                return
            
            watch_config = load_watch_config()
            source_chat_id = str(message.chat.id)
            
            logger.debug(f"🔍 检查监控配置: source_chat_id={source_chat_id}")
            logger.debug(f"   当前配置中有 {len(watch_config)} 个用户的监控任务")
            
            # Count enqueued messages for this batch
            enqueued_count = 0
            
            for user_id, watches in watch_config.items():
                logger.debug(f"   检查用户 {user_id} 的监控任务 ({len(watches)} 个)")
                # Iterate through all watch tasks for this user
                for watch_key, watch_data in watches.items():
                    # Check if this task matches the source
                    if isinstance(watch_data, dict):
                        # New format: check if source matches
                        task_source = watch_data.get("source", watch_key.split("|")[0] if "|" in watch_key else watch_key)
                        
                        # Handle None value for task_source
                        if task_source is None:
                            logger.debug(f"      跳过任务 {watch_key}: task_source 为 None")
                            continue
                        
                        if task_source != source_chat_id:
                            logger.debug(f"      跳过任务 {watch_key}: 来源不匹配 (task_source={task_source} != {source_chat_id})")
                            continue
                        
                        dest_chat_id = watch_data.get("dest")
                        record_mode = watch_data.get("record_mode", False)
                        
                        logger.info(f"✅ 找到匹配的监控任务: user_id={user_id}, watch_key={watch_key}")
                        logger.info(f"   record_mode={record_mode}, dest={dest_chat_id}")
                    else:
                        # Old format compatibility: key is source
                        if watch_key != source_chat_id:
                            logger.debug(f"      跳过任务 {watch_key}: 来源不匹配 (旧格式)")
                            continue
                        
                        dest_chat_id = watch_data
                        record_mode = False
                        
                        logger.info(f"✅ 找到匹配的监控任务 (旧格式): user_id={user_id}, watch_key={watch_key}")
                    
                    # Handle None value for dest_chat_id (skip if not in record mode)
                    if not record_mode and dest_chat_id is None:
                        logger.debug(f"      跳过任务: 非记录模式但 dest_chat_id 为 None")
                        continue
                    
                    # Pre-cache destination peer to reduce API calls during forwarding
                    if not record_mode and dest_chat_id and dest_chat_id != "me":
                        try:
                            acc.get_chat(int(dest_chat_id))
                            logger.debug(f"   ✅ 目标频道已缓存: {dest_chat_id}")
                        except Exception as e:
                            logger.debug(f"   ⚠️ 无法缓存目标频道 {dest_chat_id}: {str(e)}")
                    
                    # Check media group deduplication
                    media_group_key = None
                    if message.media_group_id:
                        media_group_key = f"{user_id}_{watch_key}_{message.media_group_id}"
                        if media_group_key in processed_media_groups:
                            logger.debug(f"   跳过：媒体组已处理 (media_group_key={media_group_key})")
                            continue
                        # Mark media group as processed immediately
                        register_processed_media_group(media_group_key)
                    
                    # Extract message text for filtering
                    message_text = message.text or message.caption or ""
                    logger.debug(f"   消息文本长度: {len(message_text)}")
                    
                    # Create Message object and enqueue
                    msg_obj = Message(
                        user_id=user_id,
                        watch_key=watch_key,
                        message=message,
                        watch_data=watch_data,
                        source_chat_id=source_chat_id,
                        dest_chat_id=dest_chat_id,
                        message_text=message_text,
                        media_group_key=media_group_key
                    )
                    
                    # Enqueue message for processing
                    message_queue.put(msg_obj)
                    enqueued_count += 1
                    logger.info(f"📬 消息已入队: user={user_id}, source={source_chat_id}, 队列大小={message_queue.qsize()}")
            
            if enqueued_count > 0:
                logger.info(f"✅ 本次共入队 {enqueued_count} 条消息")
        
        except (ValueError, KeyError) as e:
            # Catch Pyrogram peer resolution errors
            error_msg = str(e)
            if "Peer id invalid" not in error_msg and "ID not found" not in error_msg:
                logger.error(f"⚠️ auto_forward 错误: {type(e).__name__}: {e}", exc_info=True)
        except Exception as e:
            # Catch all other exceptions to prevent bot crash
            logger.error(f"⚠️ auto_forward 意外错误: {type(e).__name__}: {e}", exc_info=True)


# 启动时加载并打印配置信息
def print_startup_config():
    print("\n" + "="*60)
    print("🤖 Telegram Save-Restricted Bot 启动成功")
    print("="*60)
    
    if acc is not None:
        print("\n🔧 消息队列系统已启用")
        print("   - 消息处理模式：队列 + 工作线程")
        print("   - 最大重试次数：3 次")
        print("   - 自动故障恢复：是")
    
    watch_config = load_watch_config()
    if not watch_config:
        print("\n📋 当前没有监控任务")
    else:
        total_tasks = sum(len(watches) for watches in watch_config.values())
        print(f"\n📋 已加载 {len(watch_config)} 个用户的 {total_tasks} 个监控任务：\n")
        
        # Count record mode tasks
        record_mode_count = 0
        for user_id, watches in watch_config.items():
            for watch_key, watch_data in watches.items():
                if isinstance(watch_data, dict) and watch_data.get("record_mode", False):
                    record_mode_count += 1
        
        if record_mode_count > 0:
            print(f"🔍 配置的记录模式任务: {record_mode_count} 个\n")
        
        # Collect all unique source IDs to pre-cache
        source_ids_to_cache = set()
        
        for user_id, watches in watch_config.items():
            print(f"👤 用户 {user_id}:")
            for watch_key, watch_data in watches.items():
                if isinstance(watch_data, dict):
                    source_id = watch_data.get("source", watch_key.split("|")[0] if "|" in watch_key else watch_key)
                    dest_id = watch_data.get("dest", "未知")
                    record_mode = watch_data.get("record_mode", False)
                    
                    # Handle None values
                    if source_id is None:
                        source_id = "未知来源"
                    if dest_id is None:
                        dest_id = "未知目标"
                    
                    # Add to cache list if it's a valid chat ID (channels/groups have negative IDs)
                    if source_id not in ["未知来源", "me"] and source_id:
                        try:
                            # Try to parse as int to verify it's a valid chat ID
                            # Only cache negative IDs (channels/groups), not positive IDs (users)
                            chat_id_int = int(source_id)
                            if chat_id_int < 0:
                                source_ids_to_cache.add(source_id)
                        except (ValueError, TypeError):
                            pass
                    
                    if record_mode:
                        print(f"   📝 {source_id} → 记录模式")
                    else:
                        print(f"   📤 {source_id} → {dest_id}")
                else:
                    # Handle None values in old format
                    source_display = watch_key if watch_key is not None else "未知来源"
                    dest_display = watch_data if watch_data is not None else "未知目标"
                    
                    # Add to cache list if it's a valid chat ID (channels/groups have negative IDs)
                    if watch_key not in ["未知来源", "me", None] and watch_key:
                        try:
                            # Only cache negative IDs (channels/groups), not positive IDs (users)
                            chat_id_int = int(watch_key)
                            if chat_id_int < 0:
                                source_ids_to_cache.add(watch_key)
                        except (ValueError, TypeError):
                            pass
                    
                    print(f"   📤 {source_display} → {dest_display}")
            print()
        
        # Pre-cache all source channels to prevent "Peer id invalid" errors
        if acc is not None and source_ids_to_cache:
            print("🔄 预加载频道信息到缓存...")
            cached_count = 0
            for source_id in source_ids_to_cache:
                try:
                    acc.get_chat(int(source_id))
                    cached_count += 1
                    print(f"   ✅ 已缓存: {source_id}")
                except Exception as e:
                    print(f"   ⚠️ 无法缓存 {source_id}: {str(e)}")
            print(f"📦 成功缓存 {cached_count}/{len(source_ids_to_cache)} 个频道\n")
    
    print("="*60)
    print("✅ 机器人已就绪，正在监听消息...")
    print("="*60 + "\n")

# 初始化数据库
print("\n🔧 初始化数据库系统...")
try:
    init_database()
except Exception as e:
    print(f"⚠️ 数据库初始化时发生错误: {e}")
    print("⚠️ 继续启动，但记录模式可能无法工作")

# 打印启动配置
print_startup_config()

# infinty polling
bot.run()
if acc is not None:
    acc.stop()
