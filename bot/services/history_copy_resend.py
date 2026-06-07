"""Resend helpers for history copy tasks."""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from bot.utils.helpers import get_message_type

OperationExecutor = Callable[[str, Callable[[], Any]], Any]


@dataclass(frozen=True)
class HistoryCopyResendContext:
    client: Any
    source_chat_id: str
    dest_chat_id: str
    fetch_executor: OperationExecutor
    send_executor: OperationExecutor


class HistoryCopyMessageResender:
    """Re-send source messages into the destination chat."""

    def __init__(
        self,
        context: HistoryCopyResendContext | Any = None,
        *legacy_args: Any,
        **legacy_fields: Any,
    ) -> None:
        context = _resolve_resend_context(context, legacy_args, legacy_fields)
        self._client = context.client
        self._source_chat_id = int(context.source_chat_id)
        self._dest_chat_id = int(context.dest_chat_id)
        self._fetch = context.fetch_executor
        self._send = context.send_executor

    def resend(self, message_id: int) -> None:
        source_message = self._fetch(
            "读取消息详情",
            lambda: self._client.get_messages(self._source_chat_id, message_id),
        )
        if source_message is None:
            raise RuntimeError(f"消息不存在: message_id={message_id}")

        message_type = get_message_type(source_message)
        if message_type == "Text":
            self._send(
                "重发文本消息",
                lambda: self._client.send_message(
                    self._dest_chat_id,
                    source_message.text or "",
                    entities=source_message.entities,
                ),
            )
            return

        if message_type == "Document":
            self._resend_document(source_message)
            return
        if message_type == "Video":
            self._resend_video(source_message)
            return
        if message_type == "Animation":
            self._resend_animation(source_message)
            return
        if message_type == "Sticker":
            self._resend_sticker(source_message)
            return
        if message_type == "Voice":
            self._resend_voice(source_message)
            return
        if message_type == "Audio":
            self._resend_audio(source_message)
            return
        if message_type == "Photo":
            self._resend_photo(source_message)
            return

        raise RuntimeError(f"暂不支持的消息类型: {message_type or 'unknown'}")

    def _resend_document(self, message: Any) -> None:
        with self._download_paths(message, thumb_attr="document") as payload:
            self._send(
                "重发文档消息",
                lambda: self._client.send_document(
                    self._dest_chat_id,
                    payload.file_path,
                    thumb=payload.thumb_path,
                    caption=message.caption,
                    caption_entities=message.caption_entities,
                ),
            )

    def _resend_video(self, message: Any) -> None:
        with self._download_paths(message, thumb_attr="video") as payload:
            self._send(
                "重发视频消息",
                lambda: self._client.send_video(
                    self._dest_chat_id,
                    payload.file_path,
                    duration=message.video.duration,
                    width=message.video.width,
                    height=message.video.height,
                    thumb=payload.thumb_path,
                    caption=message.caption,
                    caption_entities=message.caption_entities,
                ),
            )

    def _resend_animation(self, message: Any) -> None:
        with self._download_paths(message) as payload:
            self._send(
                "重发动图消息",
                lambda: self._client.send_animation(self._dest_chat_id, payload.file_path),
            )

    def _resend_sticker(self, message: Any) -> None:
        with self._download_paths(message) as payload:
            self._send(
                "重发贴纸消息",
                lambda: self._client.send_sticker(self._dest_chat_id, payload.file_path),
            )

    def _resend_voice(self, message: Any) -> None:
        with self._download_paths(message) as payload:
            self._send(
                "重发语音消息",
                lambda: self._client.send_voice(
                    self._dest_chat_id,
                    payload.file_path,
                    caption=message.caption,
                    caption_entities=message.caption_entities,
                ),
            )

    def _resend_audio(self, message: Any) -> None:
        with self._download_paths(message, thumb_attr="audio") as payload:
            self._send(
                "重发音频消息",
                lambda: self._client.send_audio(
                    self._dest_chat_id,
                    payload.file_path,
                    caption=message.caption,
                    caption_entities=message.caption_entities,
                ),
            )

    def _resend_photo(self, message: Any) -> None:
        with self._download_paths(message) as payload:
            self._send(
                "重发图片消息",
                lambda: self._client.send_photo(
                    self._dest_chat_id,
                    payload.file_path,
                    caption=message.caption,
                    caption_entities=message.caption_entities,
                ),
            )

    def _download_paths(self, message: Any, thumb_attr: str | None = None) -> "_DownloadedPayload":
        return _DownloadedPayload(
            base_dir=Path(tempfile.mkdtemp(prefix="history_copy_resend_")),
            message=message,
            fetch_executor=self._fetch,
            client=self._client,
            thumb_attr=thumb_attr,
        )


class _DownloadedPayload:
    """Manage temporary downloaded files for resend operations."""

    def __init__(
        self,
        *,
        base_dir: Path,
        message: Any,
        fetch_executor: OperationExecutor,
        client: Any,
        thumb_attr: str | None,
    ) -> None:
        self._base_dir = base_dir
        self._message = message
        self._fetch = fetch_executor
        self._client = client
        self._thumb_attr = thumb_attr
        self.file_path: str | None = None
        self.thumb_path: str | None = None

    def __enter__(self) -> "_DownloadedPayload":
        self.file_path = self._fetch(
            "下载媒体文件",
            lambda: self._client.download_media(
                self._message,
                file_name=self._download_dir(self._base_dir / "media"),
            ),
        )
        self.thumb_path = self._download_thumb()
        return self

    def __exit__(self, *_args: object) -> None:
        shutil.rmtree(self._base_dir, ignore_errors=True)

    def _download_thumb(self) -> str | None:
        if not self._thumb_attr:
            return None
        media = getattr(self._message, self._thumb_attr, None)
        thumbs = getattr(media, "thumbs", None) or []
        if not thumbs:
            return None
        return self._fetch(
            "下载缩略图",
            lambda: self._client.download_media(
                thumbs[0].file_id,
                file_name=self._download_dir(self._base_dir / "thumb"),
            ),
        )

    @staticmethod
    def _download_dir(path: Path) -> str:
        return f"{path.as_posix().rstrip('/')}/"


def _resolve_resend_context(
    context: HistoryCopyResendContext | Any,
    legacy_args: tuple[Any, ...],
    legacy_fields: dict[str, Any],
) -> HistoryCopyResendContext:
    if isinstance(context, HistoryCopyResendContext):
        if legacy_args or legacy_fields:
            raise TypeError("resend context cannot be combined with legacy arguments")
        return context
    if context is None:
        return _resend_context_from_fields(legacy_fields)
    return _resend_context_from_values((context, *legacy_args), legacy_fields)


def _resend_context_from_fields(fields: dict[str, Any]) -> HistoryCopyResendContext:
    values = dict(fields)
    expected = ("client", "source_chat_id", "dest_chat_id", "fetch_executor", "send_executor")
    unknown = set(values) - set(expected)
    if unknown:
        raise TypeError(f"unexpected argument: {sorted(unknown)[0]}")
    return HistoryCopyResendContext(**{field: values.pop(field) for field in expected})


def _resend_context_from_values(
    values: tuple[Any, ...],
    fields: dict[str, Any],
) -> HistoryCopyResendContext:
    names = ("client", "source_chat_id", "dest_chat_id", "fetch_executor", "send_executor")
    if len(values) != len(names):
        raise TypeError("HistoryCopyMessageResender requires five legacy positional arguments")
    if fields:
        raise TypeError("legacy positional arguments cannot be combined with keywords")
    return HistoryCopyResendContext(**dict(zip(names, values)))
