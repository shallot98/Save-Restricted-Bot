"""
Progress tracking utilities for downloads/uploads
"""
import os
import time
import pyrogram
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Constants
FILE_WAIT_TIMEOUT = 30  # seconds
STATUS_UPDATE_INTERVAL = 10  # seconds


def _wait_for_status_file(statusfile: str, action_name: str) -> bool:
    start_time = time.time()

    while True:
        if os.path.exists(statusfile):
            return True
        if time.time() - start_time > FILE_WAIT_TIMEOUT:
            logger.warning(f"⚠️ 等待{action_name}状态文件超时: {statusfile}")
            return False
        time.sleep(0.1)


def _edit_status_message(
    message: pyrogram.types.messages_and_media.message.Message,
    bot: Optional[Any],
    text: str,
) -> None:
    if bot is not None:
        bot.edit_message_text(message.chat.id, message.id, text)
        return
    message.edit_text(text)


def _cleanup_status_file(statusfile: str, action_name: str) -> None:
    try:
        if os.path.exists(statusfile):
            os.remove(statusfile)
            logger.debug(f"已清理{action_name}状态文件: {statusfile}")
    except Exception as e:
        logger.warning(f"清理{action_name}状态文件失败: {e}")


def _monitor_status_file(
    statusfile: str,
    message: pyrogram.types.messages_and_media.message.Message,
    bot: Optional[Any],
    *,
    action_name: str,
    direction_label: str,
) -> None:
    time.sleep(3)
    try:
        while os.path.exists(statusfile):
            _monitor_status_tick(
                statusfile,
                message,
                bot,
                action_name=action_name,
                direction_label=direction_label,
            )
    finally:
        _cleanup_status_file(statusfile, action_name)


def _monitor_status_tick(
    statusfile: str,
    message: pyrogram.types.messages_and_media.message.Message,
    bot: Optional[Any],
    *,
    action_name: str,
    direction_label: str,
) -> None:
    try:
        txt = _read_status_text(statusfile)
        if txt:
            _try_edit_transfer_status(
                message,
                bot,
                direction_label=direction_label,
                txt=txt,
                action_name=action_name,
            )
        time.sleep(STATUS_UPDATE_INTERVAL)
    except IOError as e:
        logger.warning(f"读取{action_name}状态文件失败: {e}")
        time.sleep(5)
    except Exception as e:
        logger.error(f"{action_name}状态更新异常: {e}")
        time.sleep(5)


def _read_status_text(statusfile: str) -> str:
    with open(statusfile, "r", encoding="utf-8") as status_read:
        return status_read.read().strip()


def _try_edit_transfer_status(
    message: pyrogram.types.messages_and_media.message.Message,
    bot: Optional[Any],
    *,
    direction_label: str,
    txt: str,
    action_name: str,
) -> None:
    try:
        _edit_status_message(message, bot, f"__{direction_label}__ : **{txt}**")
    except Exception as e:
        logger.debug(f"更新{action_name}状态消息失败: {e}")


def _status_monitor(
    statusfile: str,
    message: pyrogram.types.messages_and_media.message.Message,
    bot: Optional[Any],
    *,
    action_name: str,
    direction_label: str,
) -> None:
    if not _wait_for_status_file(statusfile, action_name):
        return
    _monitor_status_file(
        statusfile,
        message,
        bot,
        action_name=action_name,
        direction_label=direction_label,
    )


def downstatus(
    statusfile: str,
    message: pyrogram.types.messages_and_media.message.Message,
    bot: Optional[Any] = None,
):
    """Monitor and update download status.

    Args:
        statusfile: Path to status file
        message: Telegram message to update
        bot: Optional Pyrogram bot client
    """
    _status_monitor(statusfile, message, bot, action_name="下载", direction_label="⬇️ 已下载")


def upstatus(
    statusfile: str,
    message: pyrogram.types.messages_and_media.message.Message,
    bot: Optional[Any] = None,
):
    """Monitor and update upload status.

    Args:
        statusfile: Path to status file
        message: Telegram message to update
        bot: Optional Pyrogram bot client
    """
    _status_monitor(statusfile, message, bot, action_name="上传", direction_label="⬆️ 已上传")


def progress(
    current: int,
    total: int,
    message: pyrogram.types.messages_and_media.message.Message,
    *legacy_args,
    transfer_type: str | None = None,
):
    """Write progress to status file

    Args:
        current: Current bytes transferred
        total: Total bytes to transfer
        message: Telegram message
        type: Transfer type ('down' or 'up')

	    Note:
	        This function is designed to be called as a callback during file transfers.
	        It writes progress percentage to a temporary status file.
	    """
    if not _has_valid_progress_message(message):
        logger.warning("⚠️ progress: 无效的message对象")
        return

    transfer_type = _resolve_transfer_type(legacy_args, transfer_type)
    statusfile = _progress_status_file(transfer_type, message)
    _write_progress_status(statusfile, current, total)


def _has_valid_progress_message(message: Any) -> bool:
    return bool(message and hasattr(message, 'chat') and hasattr(message, 'id'))


def _resolve_transfer_type(legacy_args: tuple[Any, ...], transfer_type: str | None) -> str:
    if legacy_args:
        if len(legacy_args) > 1 or transfer_type is not None:
            raise TypeError("progress received conflicting transfer type arguments")
        transfer_type = legacy_args[0]
    if transfer_type is None:
        raise TypeError("progress requires transfer_type")
    return transfer_type


def _progress_status_file(transfer_type: str, message: Any) -> str:
    return f'{transfer_type}status{str(message.chat.id)}{str(message.id)}.txt'


def _progress_percentage(current: int, total: int) -> float:
    if total > 0:
        return current * 100 / total
    return 0.0


def _write_progress_status(statusfile: str, current: int, total: int) -> None:
    try:
        _write_status_text(statusfile, f"{_progress_percentage(current, total):.1f}%")
    except ZeroDivisionError:
        logger.error(f"❌ progress: 除零错误 (total={total})")
        _write_status_text(statusfile, "0.0%")
    except IOError as e:
        logger.error(f"❌ progress: 写入状态文件失败: {e}")
    except Exception as e:
        logger.error(f"❌ progress: 未预期的错误: {e}")


def _write_status_text(statusfile: str, text: str) -> None:
    with open(statusfile, "w", encoding="utf-8") as fileup:
        fileup.write(text)
