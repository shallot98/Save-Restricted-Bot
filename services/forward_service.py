"""
转发服务模块 - 处理消息转发逻辑
遵循 SOLID 原则：
- S: 单一职责 - 只负责消息转发
- O: 开闭原则 - 易于扩展新的转发方式
"""
import re
import traceback
from typing import List, Set

class ForwardService:
    """消息转发服务"""

    def __init__(self, acc_client):
        """
        初始化转发服务

        Args:
            acc_client: Pyrogram账号客户端
        """
        self.acc = acc_client
        self.processed_media_groups: Set[str] = set()

        print("✅ 转发服务已初始化")

    def forward_message(self, message, watch_config: dict) -> bool:
        """
        转发消息

        Args:
            message: Pyrogram消息对象
            watch_config: 监控配置

        Returns:
            bool: 是否成功转发
        """
        try:
            dest_chat_id = watch_config.get("dest")
            preserve_source = watch_config.get("preserve_forward_source", False)
            forward_mode = watch_config.get("forward_mode", "full")
            extract_patterns = watch_config.get("extract_patterns", [])

            print(f"\n{'='*60}")
            print(f"📤 [转发模式] 开始转发消息")
            print(f"   目标: {dest_chat_id}")
            print(f"   模式: {forward_mode}")
            print(f"   保留来源: {preserve_source}")
            print(f"{'='*60}")

            # 检查是否是已处理的媒体组
            media_group_id = getattr(message, 'media_group_id', None)
            if media_group_id and media_group_id in self.processed_media_groups and not preserve_source:
                print(f"⏭️ 跳过已处理的媒体组: {media_group_id}")
                return True

            # 标记媒体组为已处理
            if media_group_id and not preserve_source:
                self.processed_media_groups.add(media_group_id)

            # 提取模式
            if forward_mode == "extract" and extract_patterns:
                return self._forward_extracted_content(message, dest_chat_id, extract_patterns)

            # 完整转发模式
            return self._forward_full_message(message, dest_chat_id, preserve_source)

        except Exception as e:
            print(f"\n❌ [转发模式] 转发消息时发生错误:")
            print(f"   错误类型: {type(e).__name__}")
            print(f"   错误信息: {str(e)}")
            print(f"   详细堆栈:")
            traceback.print_exc()
            return False

    def _forward_extracted_content(self, message, dest_chat_id: str, patterns: List[str]) -> bool:
        """转发提取的内容"""
        print(f"🎯 提取模式转发")

        message_text = message.text or message.caption or ""
        extracted_content = []

        for pattern in patterns:
            try:
                matches = re.findall(pattern, message_text)
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
            extracted_text = "\n".join(set(extracted_content))
            print(f"   📤 发送提取内容，长度: {len(extracted_text)}")

            if dest_chat_id == "me":
                self.acc.send_message("me", extracted_text)
            else:
                self.acc.send_message(int(dest_chat_id), extracted_text)

            print(f"   ✅ 提取内容已发送")
            return True
        else:
            print(f"   ⚠️ 未提取到任何内容，跳过转发")
            return False

    def _forward_full_message(self, message, dest_chat_id: str, preserve_source: bool) -> bool:
        """完整转发消息"""
        print(f"📦 完整转发模式")

        try:
            if preserve_source:
                # 保留转发来源
                print(f"   📋 保留转发来源")
                if dest_chat_id == "me":
                    self.acc.forward_messages("me", message.chat.id, message.id)
                else:
                    self.acc.forward_messages(int(dest_chat_id), message.chat.id, message.id)
            else:
                # 不保留转发来源
                print(f"   📋 不保留转发来源")
                media_group_id = getattr(message, 'media_group_id', None)

                if media_group_id:
                    # 媒体组消息
                    print(f"   📁 转发媒体组: {media_group_id}")
                    try:
                        if dest_chat_id == "me":
                            self.acc.copy_media_group("me", message.chat.id, message.id)
                        else:
                            self.acc.copy_media_group(int(dest_chat_id), message.chat.id, message.id)
                    except Exception as e:
                        print(f"   ⚠️ 媒体组转发失败，降级为单条消息: {e}")
                        if dest_chat_id == "me":
                            self.acc.copy_message("me", message.chat.id, message.id)
                        else:
                            self.acc.copy_message(int(dest_chat_id), message.chat.id, message.id)
                else:
                    # 单条消息
                    print(f"   📄 转发单条消息")
                    if dest_chat_id == "me":
                        self.acc.copy_message("me", message.chat.id, message.id)
                    else:
                        self.acc.copy_message(int(dest_chat_id), message.chat.id, message.id)

            print(f"   ✅ 消息已转发")
            return True

        except Exception as e:
            print(f"   ❌ 转发失败: {e}")
            traceback.print_exc()
            return False
