#!/usr/bin/env python3
"""
磁力链接校准助手 - 通过Telegram机器人获取文件名
通过给机器人发送磁力链接，机器人会返回种子的真实文件名
"""
import sys
import os
import time
from pyrogram import Client
from pyrogram.errors import FloodWait

# Telegram配置
API_ID = int(os.environ.get('ID', 0))
API_HASH = os.environ.get('HASH', '')
SESSION_STRING = os.environ.get('STRING', '')
BOT_USERNAME = os.environ.get('CALIBRATE_BOT_USERNAME', 'x_2dland_bot')


def _is_valid_filename(filename: str, original_text: str = '') -> bool:
    """验证文件名是否有效

    Args:
        filename: 待验证的文件名
        original_text: 原始回复文本（用于日志）

    Returns:
        是否是有效的文件名
    """
    if not filename:
        return False

    # 去除首尾空格
    filename = filename.strip()

    # 文件名不能为空或只是标点符号
    if not filename or filename in [',', '，', '.', '。', ':', '：']:
        return False

    # 文件名长度应该合理（至少1个字符）
    if len(filename) < 1:
        return False

    # 文件名不应该以逗号开头（这是解析错误的标志）
    if filename.startswith(',') or filename.startswith('，'):
        return False

    # 文件名不应该包含路径标记（这是解析错误的标志）
    invalid_patterns = [
        '到 /Downloads',
        '/Downloads',
        '到 /',
    ]
    for pattern in invalid_patterns:
        if pattern in filename:
            return False

    # 文件名不应该只是hash值（32或40个十六进制字符）
    # 这表示机器人未能获取到真正的文件名
    import re
    if re.match(r'^[a-fA-F0-9]{32,40}$', filename):
        return False

    # 文件名不应该看起来像是错误消息
    error_indicators = [
        '失败',
        '错误',
        '超时',
        'error',
        'failed',
        'timeout',
    ]
    filename_lower = filename.lower()
    for indicator in error_indicators:
        if indicator in filename_lower:
            return False

    return True

def calibrate_via_bot(info_hash: str, timeout: int = 60) -> str:
    """通过Telegram机器人获取种子文件名

    Args:
        info_hash: 磁力链接的info hash
        timeout: 超时时间（秒）

    Returns:
        文件名，失败抛出异常
    """
    if not API_ID or not API_HASH or not SESSION_STRING:
        raise Exception("缺少Telegram配置（ID, HASH, STRING）")

    # 构造磁力链接
    magnet_uri = f"magnet:?xt=urn:btih:{info_hash}"

    # 创建客户端
    app = Client(
        "calibrate_bot_session",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=SESSION_STRING,
        in_memory=True
    )

    try:
        app.start()

        # 发送磁力链接给机器人
        sent_message = app.send_message(BOT_USERNAME, magnet_uri)
        sent_time = time.time()

        # 等待机器人回复
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # 获取与机器人的最近消息
                messages = app.get_chat_history(BOT_USERNAME, limit=10)

                for message in messages:
                    # 跳过我们发送的消息
                    if message.id == sent_message.id:
                        continue

                    # 只处理机器人在我们发送消息之后的回复
                    if message.date.timestamp() <= sent_time:
                        continue

                    # 检查是否是机器人的回复
                    if message.from_user and message.from_user.username == BOT_USERNAME:
                        # 提取文件名
                        if message.text:
                            text = message.text.strip()

                            # 如果包含磁力链接，提取dn参数
                            if 'magnet:' in text:
                                import re
                                from urllib.parse import unquote
                                match = re.search(r'[&?]dn=([^&\s\n]+)', text)
                                if match:
                                    filename = unquote(match.group(1))
                                    return filename

                            # 检查是否是离线任务添加的回复（包含文件名）
                            # 格式: "离线任务已添加: 文件名, hash值, 到 /Downloads"
                            # 提取规则：获取冒号(:)到第一个逗号(,)之间的内容
                            if '离线任务已添加' in text or ':' in text:
                                import re
                                # 只处理第一行（可能有多行）
                                first_line = text.split('\n')[0].strip()

                                # 查找冒号位置
                                colon_pos = first_line.find(':')
                                if colon_pos >= 0:
                                    # 提取冒号后的内容
                                    after_colon = first_line[colon_pos + 1:].strip()

                                    # 查找第一个逗号位置
                                    comma_pos = after_colon.find(',')
                                    if comma_pos >= 0:
                                        # 提取冒号到第一个逗号之间的内容
                                        filename = after_colon[:comma_pos].strip()

                                        # 验证文件名是否有效
                                        if not _is_valid_filename(filename, text):
                                            raise ValueError(f"机器人返回的文件名无效，原始回复: {text}")

                                        return filename
                                    else:
                                        # 如果没有逗号，返回冒号后的全部内容
                                        candidate = after_colon.strip()
                                        if _is_valid_filename(candidate, text):
                                            return candidate
                                        raise ValueError(f"机器人返回的文件名无效，原始回复: {text}")

                                # 如果没有冒号，返回整行内容
                                candidate = first_line.strip()
                                if _is_valid_filename(candidate, text):
                                    return candidate
                                raise ValueError(f"机器人返回的文件名无效，原始回复: {text}")

                            # 否则直接返回文本（可能就是文件名）
                            # 但需要验证是否是有效的文件名
                            if _is_valid_filename(text, text):
                                return text
                            raise ValueError(f"机器人返回的文件名无效，原始回复: {text}")

                # 等待一段时间再检查
                time.sleep(2)

            except FloodWait as e:
                print(f"FloodWait: 等待 {e.value} 秒", file=sys.stderr)
                time.sleep(e.value)

        raise TimeoutError(f"机器人在 {timeout} 秒内未回复")

    finally:
        app.stop()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python3 calibrate_bot_helper.py <info_hash>", file=sys.stderr)
        sys.exit(1)

    try:
        filename = calibrate_via_bot(sys.argv[1])
        print(filename)
        sys.exit(0)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
