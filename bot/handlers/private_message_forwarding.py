"""Private Telegram message download and resend helpers."""

import os
import threading
from dataclasses import dataclass
from typing import Optional

import pyrogram

from bot.utils.helpers import get_message_type
from bot.utils.progress import downstatus, progress, upstatus


@dataclass(frozen=True, kw_only=True)
class PrivateMessageContext:
    message: object
    chatid: object
    msgid: int
    bot: object
    acc: object


@dataclass(frozen=True, kw_only=True)
class DownloadedMedia:
    msg: object
    msg_type: str
    file_path: str


def forward_private_message(context: PrivateMessageContext) -> None:
    """Download a private message through the user client and resend it through the bot."""
    msg: pyrogram.types.messages_and_media.message.Message = context.acc.get_messages(
        context.chatid,
        context.msgid,
    )
    msg_type = get_message_type(msg)

    if msg_type == "Text":
        context.bot.send_message(context.message.chat.id, msg.text, entities=msg.entities)
        return

    status_message = _start_download_status(context)
    file_path = context.acc.download_media(msg, progress=progress, progress_args=[context.message, "down"])
    os.remove(f"{context.message.id}downstatus.txt")
    _start_upload_status(context, status_message)
    _send_downloaded_media(context, DownloadedMedia(msg=msg, msg_type=msg_type, file_path=file_path))
    _cleanup_forwarded_media(context, status_message, file_path)


def _start_download_status(context: PrivateMessageContext):
    status_message = context.bot.send_message(
        context.message.chat.id,
        "__⬇️ 下载中__",
        reply_to_message_id=context.message.id,
    )
    thread = threading.Thread(
        target=lambda: downstatus(f"{context.message.id}downstatus.txt", status_message),
        daemon=True,
    )
    thread.start()
    return status_message


def _start_upload_status(context: PrivateMessageContext, status_message) -> None:
    thread = threading.Thread(
        target=lambda: upstatus(f"{context.message.id}upstatus.txt", status_message),
        daemon=True,
    )
    thread.start()


def _send_downloaded_media(context: PrivateMessageContext, media: DownloadedMedia) -> None:
    handler = {
        "Document": _send_document,
        "Video": _send_video,
        "Animation": _send_animation,
        "Sticker": _send_sticker,
        "Voice": _send_voice,
        "Audio": _send_audio,
        "Photo": _send_photo,
    }.get(media.msg_type)
    if handler is not None:
        handler(context, media)


def _send_animation(context: PrivateMessageContext, media: DownloadedMedia) -> None:
    context.bot.send_animation(context.message.chat.id, media.file_path)


def _send_sticker(context: PrivateMessageContext, media: DownloadedMedia) -> None:
    context.bot.send_sticker(context.message.chat.id, media.file_path)


def _send_photo(context: PrivateMessageContext, media: DownloadedMedia) -> None:
    context.bot.send_photo(
        context.message.chat.id,
        media.file_path,
        caption=media.msg.caption,
        caption_entities=media.msg.caption_entities,
    )


def _send_document(context: PrivateMessageContext, media: DownloadedMedia) -> None:
    thumb = _download_thumb(context.acc, media.msg.document)
    context.bot.send_document(
        context.message.chat.id,
        media.file_path,
        thumb=thumb,
        caption=media.msg.caption,
        caption_entities=media.msg.caption_entities,
        progress=progress,
        progress_args=[context.message, "up"],
    )
    if thumb is not None:
        os.remove(thumb)


def _send_video(context: PrivateMessageContext, media: DownloadedMedia) -> None:
    thumb = _download_thumb(context.acc, media.msg.video)
    context.bot.send_video(
        context.message.chat.id,
        media.file_path,
        duration=media.msg.video.duration,
        width=media.msg.video.width,
        height=media.msg.video.height,
        thumb=thumb,
        caption=media.msg.caption,
        caption_entities=media.msg.caption_entities,
        progress=progress,
        progress_args=[context.message, "up"],
    )
    if thumb is not None:
        os.remove(thumb)


def _send_voice(context: PrivateMessageContext, media: DownloadedMedia) -> None:
    context.bot.send_voice(
        context.message.chat.id,
        media.file_path,
        caption=media.msg.caption,
        caption_entities=media.msg.caption_entities,
        progress=progress,
        progress_args=[context.message, "up"],
    )


def _send_audio(context: PrivateMessageContext, media: DownloadedMedia) -> None:
    thumb = _download_thumb(context.acc, media.msg.audio)
    context.bot.send_audio(
        context.message.chat.id,
        media.file_path,
        caption=media.msg.caption,
        caption_entities=media.msg.caption_entities,
        progress=progress,
        progress_args=[context.message, "up"],
    )
    if thumb is not None:
        os.remove(thumb)


def _download_thumb(acc, media_obj) -> Optional[str]:
    try:
        return acc.download_media(media_obj.thumbs[0].file_id)
    except Exception:
        return None


def _cleanup_forwarded_media(context: PrivateMessageContext, status_message, file_path: str) -> None:
    os.remove(file_path)
    if os.path.exists(f"{context.message.id}upstatus.txt"):
        os.remove(f"{context.message.id}upstatus.txt")
    context.bot.delete_messages(context.message.chat.id, [status_message.id])
