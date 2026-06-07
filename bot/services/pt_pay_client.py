"""PT pay user-client bootstrap helpers."""

from __future__ import annotations

import os

from pyrogram import Client

from bot.utils.threadsafe_client import SingleThreadClientProxy
from config import getenv, getenv_optional, load_config


def create_dedicated_user_client(session_name: str = "pt_pay_monitor") -> SingleThreadClientProxy:
    config = load_config()
    api_id = getenv("ID", config)
    api_hash = getenv("HASH", config)
    session_string = getenv_optional("STRING", config)

    os.makedirs("data", exist_ok=True)
    session_file = os.path.join("data", session_name)
    session_path = f"{session_file}.session"
    if os.path.exists(session_path):
        client = Client(session_file, api_id=api_id, api_hash=api_hash)
    else:
        if not session_string:
            raise RuntimeError("未找到 STRING，且独立 session 尚未创建；请先在配置中提供 STRING")
        client = Client(
            session_file,
            api_id=api_id,
            api_hash=api_hash,
            session_string=session_string,
            in_memory=False,
        )

    client.start()
    return SingleThreadClientProxy(client)


def coerce_chat_ref(chat_ref: str) -> int | str:
    value = str(chat_ref).strip()
    try:
        return int(value)
    except ValueError:
        return value
