#!/usr/bin/env python3
"""
Copy Telegram chat history into another chat with resume support.

Usage:
  python3 scripts/tg_history_copy.py --source-chat <source> --dest-chat <target>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.services.history_copy import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_FAILURE_COOLDOWN_SECONDS,
    DEFAULT_FAILURE_THRESHOLD,
    DEFAULT_FLOODWAIT_BUFFER_SECONDS,
    DEFAULT_HOURLY_SEND_BUDGET,
    DEFAULT_MAX_FLOOD_RETRIES,
    DEFAULT_RATE_LIMIT_DELAY,
    DEFAULT_SESSION_NAME,
    DEFAULT_STATE_DB_PATH,
    HistoryCopyFatalError,
    HistoryCopyRunner,
    HistoryCopyStateStore,
    create_history_copy_client,
    resolve_history_copy_settings,
)
from src.infrastructure.logging import get_logger, setup_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="复制 Telegram 历史消息到另一个群/频道")
    parser.add_argument("--source-chat", required=True, help="源 chat 的 chat_id 或用户名")
    parser.add_argument("--dest-chat", required=True, help="目标 chat 的 chat_id 或用户名")
    parser.add_argument("--session-name", default=DEFAULT_SESSION_NAME, help="独立 user session 名称")
    parser.add_argument("--state-db", default=str(DEFAULT_STATE_DB_PATH), help="断点续传状态 SQLite 文件")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help="每批历史读取条数")
    parser.add_argument("--history-limit", type=int, default=None, help="只复制最近 N 条历史消息")
    parser.add_argument(
        "--flood-retries",
        type=int,
        default=DEFAULT_MAX_FLOOD_RETRIES,
        help="FloodWait 最大重试次数",
    )
    parser.add_argument(
        "--rate-limit-delay",
        type=float,
        default=DEFAULT_RATE_LIMIT_DELAY,
        help="最小发送间隔秒数",
    )
    parser.add_argument(
        "--hourly-send-budget",
        type=int,
        default=DEFAULT_HOURLY_SEND_BUDGET,
        help="滑动一小时窗口内允许复制的最大消息数；设为 0 可关闭预算",
    )
    parser.add_argument(
        "--failure-threshold",
        type=int,
        default=DEFAULT_FAILURE_THRESHOLD,
        help="连续失败达到阈值后触发自动冷却；设为 0 可关闭熔断",
    )
    parser.add_argument(
        "--failure-cooldown-seconds",
        type=float,
        default=DEFAULT_FAILURE_COOLDOWN_SECONDS,
        help="连续失败熔断后的自动冷却秒数",
    )
    parser.add_argument(
        "--floodwait-buffer-seconds",
        type=float,
        default=DEFAULT_FLOODWAIT_BUFFER_SECONDS,
        help="在 Telegram 返回 FloodWait 基础上追加的保护缓冲秒数",
    )
    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    setup_logging()
    logger = get_logger(__name__)
    client = None

    try:
        client = create_history_copy_client(session_name=args.session_name)
        settings = resolve_history_copy_settings(
            client,
            args.source_chat,
            args.dest_chat,
            state_db_path=Path(args.state_db),
            batch_size=args.batch_size,
            history_limit=args.history_limit,
            max_flood_retries=args.flood_retries,
            rate_limit_delay=args.rate_limit_delay,
            hourly_send_budget=args.hourly_send_budget,
            failure_threshold=args.failure_threshold,
            failure_cooldown_seconds=args.failure_cooldown_seconds,
            floodwait_buffer_seconds=args.floodwait_buffer_seconds,
        )
        with HistoryCopyStateStore(settings.state_db_path) as state_store:
            stats = HistoryCopyRunner(client, settings, state_store).run()
        logger.info("🏁 脚本结束: %s", stats.summary())
        return 0
    except HistoryCopyFatalError as exc:
        logger.error("❌ 历史复制终止: %s", exc)
        return 1
    except Exception as exc:
        logger.error("❌ 脚本执行失败: %s: %s", type(exc).__name__, exc)
        return 1
    finally:
        if client is not None:
            client.stop()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
