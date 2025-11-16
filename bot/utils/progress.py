"""
Progress tracking utilities for downloads/uploads
"""
import os
import time
import pyrogram
import logging

logger = logging.getLogger(__name__)


def downstatus(statusfile: str, message: pyrogram.types.messages_and_media.message.Message, bot):
    """Monitor and update download status
    
    Args:
        statusfile: Path to status file
        message: Telegram message to update
        bot: Pyrogram bot client
    """
    while True:
        if os.path.exists(statusfile):
            break

    time.sleep(3)      
    while os.path.exists(statusfile):
        with open(statusfile, "r") as downread:
            txt = downread.read()
        try:
            bot.edit_message_text(message.chat.id, message.id, f"__⬇️ 已下载__ : **{txt}**")
            time.sleep(10)
        except:
            time.sleep(5)


def upstatus(statusfile: str, message: pyrogram.types.messages_and_media.message.Message, bot):
    """Monitor and update upload status
    
    Args:
        statusfile: Path to status file
        message: Telegram message to update
        bot: Pyrogram bot client
    """
    while True:
        if os.path.exists(statusfile):
            break

    time.sleep(3)      
    while os.path.exists(statusfile):
        with open(statusfile, "r") as upread:
            txt = upread.read()
        try:
            bot.edit_message_text(message.chat.id, message.id, f"__⬆️ 已上传__ : **{txt}**")
            time.sleep(10)
        except:
            time.sleep(5)


def progress(current: int, total: int, message: pyrogram.types.messages_and_media.message.Message, type: str):
    """Write progress to status file
    
    Args:
        current: Current bytes transferred
        total: Total bytes to transfer
        message: Telegram message
        type: Transfer type ('down' or 'up')
    """
    with open(f'{type}status{str(message.chat.id)}{str(message.id)}.txt', "w") as fileup:
        fileup.write(f"{current * 100 / total:.1f}%")
