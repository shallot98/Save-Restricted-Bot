"""
记录服务模块 - 专门处理记录模式的业务逻辑
遵循 SOLID 原则：
- S: 单一职责 - 只负责记录消息到数据库
- O: 开闭原则 - 易于扩展新的记录类型
- D: 依赖倒置 - 依赖抽象的数据库接口
"""
import os
import re
import traceback
from datetime import datetime
from typing import Optional, List, Set
from pathlib import Path

class RecordService:
    """记录服务 - 负责将消息保存到数据库"""

    def __init__(self, acc_client, database_module, config_manager):
        """
        初始化记录服务

        Args:
            acc_client: Pyrogram账号客户端
            database_module: 数据库模块
            config_manager: 配置管理器
        """
        self.acc = acc_client
        self.db = database_module
        self.config = config_manager
        self.processed_media_groups: Set[str] = set()

        print("✅ 记录服务已初始化")

    def record_message(self, message, user_id: int, watch_config: dict) -> bool:
        """
        记录消息到数据库

        Args:
            message: Pyrogram消息对象
            user_id: 用户ID
            watch_config: 监控配置（包含过滤规则和提取模式）

        Returns:
            bool: 是否成功记录
        """
        try:
            source_chat_id = str(message.chat.id)
            source_name = message.chat.title or message.chat.username or source_chat_id
            message_text = message.text or message.caption or ""

            print(f"\n{'='*60}")
            print(f"📝 [记录模式] 开始处理消息")
            print(f"   来源: {source_name} ({source_chat_id})")
            print(f"   消息ID: {message.id}")
            print(f"   文本长度: {len(message_text)}")
            print(f"{'='*60}")

            # 检查是否是媒体组的重复消息
            media_group_id = getattr(message, 'media_group_id', None)
            if media_group_id and media_group_id in self.processed_media_groups:
                print(f"⏭️ 跳过已处理的媒体组: {media_group_id}")
                return True

            # 应用提取模式（如果配置了）
            content_to_save = self._apply_extract_patterns(
                message_text,
                watch_config.get("forward_mode", "full"),
                watch_config.get("extract_patterns", [])
            )

            # 处理不同类型的消息
            if media_group_id and (message.photo or message.video):
                # 媒体组消息
                success = self._record_media_group(
                    message, user_id, source_chat_id, source_name,
                    content_to_save, media_group_id
                )
            elif message.photo:
                # 单张图片
                success = self._record_single_photo(
                    message, user_id, source_chat_id, source_name,
                    content_to_save, media_group_id
                )
            elif message.video:
                # 单个视频
                success = self._record_single_video(
                    message, user_id, source_chat_id, source_name,
                    content_to_save, media_group_id
                )
            else:
                # 纯文本消息
                success = self._record_text_only(
                    user_id, source_chat_id, source_name,
                    content_to_save, media_group_id
                )

            if success:
                print(f"✅ [记录模式] 消息记录成功")
            else:
                print(f"⚠️ [记录模式] 消息记录失败")

            return success

        except Exception as e:
            print(f"\n❌ [记录模式] 记录消息时发生错误:")
            print(f"   错误类型: {type(e).__name__}")
            print(f"   错误信息: {str(e)}")
            print(f"   详细堆栈:")
            traceback.print_exc()
            return False

    def _apply_extract_patterns(self, text: str, forward_mode: str, patterns: List[str]) -> str:
        """应用提取模式"""
        if forward_mode != "extract" or not patterns:
            return text

        print(f"🎯 应用提取模式: {len(patterns)} 个规则")
        extracted_content = []

        for pattern in patterns:
            try:
                matches = re.findall(pattern, text)
                if matches:
                    print(f"   ✅ 规则 '{pattern}' 匹配到 {len(matches)} 个结果")
                    if isinstance(matches[0], tuple):
                        for match_group in matches:
                            extracted_content.extend(match_group)
                    else:
                        extracted_content.extend(matches)
            except re.error as e:
                print(f"   ❌ 正则表达式错误: {pattern} - {e}")

        if extracted_content:
            result = "\n".join(set(extracted_content))
            print(f"   📤 提取结果长度: {len(result)}")
            return result
        else:
            print(f"   ⚠️ 未提取到任何内容")
            return ""

    def _record_media_group(self, message, user_id: int, source_chat_id: str,
                           source_name: str, content: str, media_group_id: str) -> bool:
        """记录媒体组消息"""
        print(f"📁 处理媒体组: {media_group_id}")

        try:
            # 创建笔记记录
            note_id = self.db.add_note(
                user_id=user_id,
                source_chat_id=source_chat_id,
                source_name=source_name,
                message_text=content if content else None,
                media_type="media_group",
                media_path=None,
                media_group_id=media_group_id,
                is_media_group=True
            )
            print(f"   ✅ 创建笔记记录 ID: {note_id}")

            # 获取媒体组中的所有消息
            try:
                group_messages = self.acc.get_media_group(message.chat.id, message.id)
                print(f"   📦 媒体组包含 {len(group_messages)} 个文件")

                # 下载并保存每个媒体文件
                for idx, group_msg in enumerate(group_messages, 1):
                    print(f"   处理第 {idx}/{len(group_messages)} 个文件...")
                    if group_msg.photo:
                        self._download_and_save_photo(group_msg, note_id)
                    elif group_msg.video:
                        self._download_and_save_video_thumb(group_msg, note_id)

                # 标记媒体组已处理
                self.processed_media_groups.add(media_group_id)
                print(f"   ✅ 媒体组处理完成")
                return True

            except Exception as e:
                print(f"   ⚠️ 获取媒体组失败: {e}")
                # 降级处理：只保存当前消息的媒体
                if message.photo:
                    self._download_and_save_photo(message, note_id)
                elif message.video:
                    self._download_and_save_video_thumb(message, note_id)

                self.processed_media_groups.add(media_group_id)
                return True

        except Exception as e:
            print(f"   ❌ 记录媒体组失败: {e}")
            traceback.print_exc()
            return False

    def _record_single_photo(self, message, user_id: int, source_chat_id: str,
                            source_name: str, content: str, media_group_id: Optional[str]) -> bool:
        """记录单张图片"""
        print(f"🖼️ 处理单张图片")

        try:
            # 下载图片
            file_name = f"{message.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            file_path = self.config.media_dir / file_name

            print(f"   ⬇️ 下载图片到: {file_path}")
            self.acc.download_media(message.photo.file_id, file_name=str(file_path))

            # 创建笔记记录
            note_id = self.db.add_note(
                user_id=user_id,
                source_chat_id=source_chat_id,
                source_name=source_name,
                message_text=content if content else None,
                media_type="photo",
                media_path=file_name,
                media_group_id=media_group_id,
                is_media_group=False
            )
            print(f"   ✅ 图片记录成功 ID: {note_id}")
            return True

        except Exception as e:
            print(f"   ❌ 记录图片失败: {e}")
            traceback.print_exc()
            return False

    def _record_single_video(self, message, user_id: int, source_chat_id: str,
                            source_name: str, content: str, media_group_id: Optional[str]) -> bool:
        """记录单个视频（保存缩略图）"""
        print(f"🎬 处理单个视频")

        try:
            media_path = None

            # 尝试下载视频缩略图
            if message.video.thumbs:
                thumb = message.video.thumbs[0]
                file_name = f"{message.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_thumb.jpg"
                file_path = self.config.media_dir / file_name

                print(f"   ⬇️ 下载视频缩略图到: {file_path}")
                self.acc.download_media(thumb.file_id, file_name=str(file_path))
                media_path = file_name
                print(f"   ✅ 缩略图下载成功")
            else:
                print(f"   ⚠️ 视频没有缩略图")

            # 创建笔记记录
            note_id = self.db.add_note(
                user_id=user_id,
                source_chat_id=source_chat_id,
                source_name=source_name,
                message_text=content if content else None,
                media_type="video",
                media_path=media_path,
                media_group_id=media_group_id,
                is_media_group=False
            )
            print(f"   ✅ 视频记录成功 ID: {note_id}")
            return True

        except Exception as e:
            print(f"   ❌ 记录视频失败: {e}")
            traceback.print_exc()
            return False

    def _record_text_only(self, user_id: int, source_chat_id: str,
                          source_name: str, content: str, media_group_id: Optional[str]) -> bool:
        """记录纯文本消息"""
        print(f"📝 处理纯文本消息")

        try:
            note_id = self.db.add_note(
                user_id=user_id,
                source_chat_id=source_chat_id,
                source_name=source_name,
                message_text=content if content else None,
                media_type=None,
                media_path=None,
                media_group_id=media_group_id,
                is_media_group=False
            )
            print(f"   ✅ 文本记录成功 ID: {note_id}")
            return True

        except Exception as e:
            print(f"   ❌ 记录文本失败: {e}")
            traceback.print_exc()
            return False

    def _download_and_save_photo(self, message, note_id: int):
        """下载并保存图片到笔记"""
        try:
            file_name = f"{message.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            file_path = self.config.media_dir / file_name

            self.acc.download_media(message.photo.file_id, file_name=str(file_path))
            self.db.add_media_to_note(note_id, "photo", file_name, message.photo.file_id)
            print(f"      ✅ 图片已保存: {file_name}")

        except Exception as e:
            print(f"      ❌ 保存图片失败: {e}")

    def _download_and_save_video_thumb(self, message, note_id: int):
        """下载并保存视频缩略图到笔记"""
        try:
            if not message.video.thumbs:
                print(f"      ⚠️ 视频没有缩略图")
                return

            thumb = message.video.thumbs[0]
            file_name = f"{message.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_thumb.jpg"
            file_path = self.config.media_dir / file_name

            self.acc.download_media(thumb.file_id, file_name=str(file_path))
            self.db.add_media_to_note(note_id, "video", file_name, thumb.file_id)
            print(f"      ✅ 视频缩略图已保存: {file_name}")

        except Exception as e:
            print(f"      ❌ 保存视频缩略图失败: {e}")
