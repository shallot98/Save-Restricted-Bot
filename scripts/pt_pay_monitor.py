#!/usr/bin/env python3
"""
监听指定群聊消息，提取多行 PT 编号，并按顺序调用目标 Bot 的 `/pay`。

用法：
  python3 scripts/pt_pay_monitor.py --source-chat -1001234567890 --target-bot some_pay_bot
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pyrogram import idle

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.infrastructure.logging import setup_logging
from bot.services.pt_pay_monitor import (
    create_dedicated_user_client,
    resolve_monitor_settings,
    PtPayMonitor,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PT 编号监控与 /pay 自动尝试脚本")
    parser.add_argument("--source-chat", required=True, help="被监听的群聊/频道 chat_id 或用户名")
    parser.add_argument("--target-bot", required=True, help="接收 /pay 命令的目标 Bot 用户名或 chat_id")
    parser.add_argument("--success-keyword", action="append", default=None, help="成功判定关键字，可重复传入")
    parser.add_argument("--reply-timeout", type=float, default=20.0, help="单次 /pay 等待回复超时秒数")
    parser.add_argument("--poll-interval", type=float, default=1.0, help="轮询目标 Bot 回复的间隔秒数")
    parser.add_argument("--send-interval", type=float, default=1.0, help="相邻两次 /pay 之间的间隔秒数")
    parser.add_argument("--history-limit", type=int, default=10, help="轮询目标 Bot 时读取的最近消息条数")
    parser.add_argument("--session-name", default="pt_pay_monitor", help="独立 user session 名称")
    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    setup_logging()

    client = create_dedicated_user_client(session_name=args.session_name)
    monitor = None

    try:
        settings = resolve_monitor_settings(
            client=client,
            source_chat_ref=args.source_chat,
            target_bot_ref=args.target_bot,
            success_keywords=args.success_keyword,
            reply_timeout_seconds=args.reply_timeout,
            poll_interval_seconds=args.poll_interval,
            send_interval_seconds=args.send_interval,
            history_limit=args.history_limit,
        )
        monitor = PtPayMonitor(client=client, settings=settings)
        monitor.start()
        idle()
        return 0
    finally:
        if monitor is not None:
            monitor.stop()
        client.stop()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
