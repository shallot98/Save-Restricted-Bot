"""
客户端初始化模块
职责：初始化Bot客户端和User客户端
"""
import os
from pyrogram import Client
from bot.utils.logger import get_logger
from config import load_config, getenv, getenv_optional
from bot.utils.threadsafe_client import SingleThreadClientProxy

logger = get_logger(__name__)


def _load_client_config() -> tuple:
    data = load_config()
    return data, getenv("TOKEN", data), getenv("HASH", data), getenv("ID", data)


def initialize_clients():
    """
    初始化Telegram客户端

    Returns:
        tuple: (bot_client, user_client)
            - bot_client: Bot客户端实例
            - user_client: User客户端实例（如果配置了session string），否则为None
    """
    data, bot_token, api_hash, api_id = _load_client_config()
    bot = _create_bot_client(api_id, api_hash, bot_token)
    acc = _create_user_client(data, api_id, api_hash)
    return bot, acc


def _create_bot_client(api_id, api_hash, bot_token) -> Client:
    logger.info("🤖 正在初始化Bot客户端...")
    os.makedirs("data", exist_ok=True)
    bot = Client("data/mybot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)
    logger.info("✅ Bot客户端初始化完成")
    return bot


def _create_user_client(data: dict, api_id, api_hash):
    ss = getenv_optional("STRING", data)
    if ss:
        return _initialize_user_client(data, api_id, api_hash, session_string=ss)
    logger.warning("⚠️ 未找到 session string，User客户端未初始化")
    logger.warning("   部分功能（如自动转发）将不可用")
    return None


def _initialize_user_client(data: dict, api_id, api_hash, *, session_string: str):
    logger.info("👤 正在初始化User客户端...")
    _log_session_string_source(data)
    session_file = _session_file_path()
    acc = _build_user_client(session_file, api_id, api_hash, session_string=session_string)
    acc.start()
    acc = SingleThreadClientProxy(acc)
    _log_session_file_state(session_file)
    logger.info("✅ User客户端初始化完成")
    return acc


def _log_session_string_source(data: dict) -> None:
    if data.get("STRING"):
        logger.info("✅ 使用 config.json 中的 session string")
    else:
        logger.info("✅ 使用环境变量 STRING 中的 session string")


def _session_file_path() -> str:
    session_dir = "data"
    os.makedirs(session_dir, exist_ok=True)
    return os.path.join(session_dir, "myacc")


def _build_user_client(session_file: str, api_id, api_hash, *, session_string: str) -> Client:
    if os.path.exists(f"{session_file}.session"):
        logger.info("📂 发现已有 Session 文件，将保留 Peer 缓存")
        return Client(session_file, api_id=api_id, api_hash=api_hash)
    logger.info("📝 首次启动，使用 Session String 创建 Session 文件")
    return Client(
        session_file,
        api_id=api_id,
        api_hash=api_hash,
        session_string=session_string,
        in_memory=False,
    )


def _log_session_file_state(session_file: str) -> None:
    if os.path.exists(f"{session_file}.session"):
        logger.info("✅ Session文件已存在")
        return
    logger.warning("⚠️ Session文件未自动创建")
    logger.info("💡 Pyrogram 2.x使用session_string时默认不创建文件，但不影响功能")
    logger.info("   Session数据已加载到内存，消息接收功能正常")
