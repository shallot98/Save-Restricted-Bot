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
                                    if comma_pos > 0:
                                        # 提取冒号到第一个逗号之间的内容
                                        filename = after_colon[:comma_pos].strip()
                                        return filename
                                    else:
                                        # 如果没有逗号，返回冒号后的全部内容
                                        return after_colon.strip()

                                # 如果没有冒号，返回整行内容
                                return first_line.strip()

                            # 否则直接返回文本（可能就是文件名）
                            return text

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
