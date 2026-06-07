from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bot.services.history_copy_resend import HistoryCopyMessageResender


@dataclass
class _DummyThumb:
    file_id: str


@dataclass
class _DummyDocument:
    file_id: str
    thumbs: list[_DummyThumb]


@dataclass
class _DummyMessage:
    id: int
    document: _DummyDocument
    caption: str | None = None
    caption_entities: list | None = None


class _DummyClient:
    def __init__(self, message: _DummyMessage) -> None:
        self._message = message
        self.download_targets: list[str] = []
        self.sent_payload: tuple[str, str | None] | None = None

    def get_messages(self, _chat_id: int, _message_id: int) -> _DummyMessage:
        return self._message

    def download_media(self, _media, file_name: str) -> str:
        self.download_targets.append(file_name)
        normalized = file_name.rstrip("/")
        target_dir = Path(normalized)
        target_dir.mkdir(parents=True, exist_ok=True)
        output = target_dir / f"{len(self.download_targets)}.bin"
        output.write_bytes(b"payload")
        return str(output)

    def send_document(
        self,
        _dest_chat_id: int,
        file_path: str,
        *,
        thumb: str | None = None,
        caption: str | None = None,
        caption_entities: list | None = None,
    ) -> None:
        assert Path(file_path).exists()
        if thumb is not None:
            assert Path(thumb).exists()
        self.sent_payload = (file_path, thumb)


def test_resender_uses_separate_temp_targets_for_media_and_thumb() -> None:
    message = _DummyMessage(
        id=7,
        document=_DummyDocument(file_id="doc-1", thumbs=[_DummyThumb(file_id="thumb-1")]),
        caption="hello",
    )
    client = _DummyClient(message)
    resender = HistoryCopyMessageResender(
        client=client,
        source_chat_id="-1001",
        dest_chat_id="-1002",
        fetch_executor=lambda _name, operation: operation(),
        send_executor=lambda _name, operation: operation(),
    )

    resender.resend(7)

    assert len(client.download_targets) == 2
    media_target, thumb_target = client.download_targets
    assert media_target.endswith("/media/")
    assert thumb_target.endswith("/thumb/")
    assert Path(media_target.rstrip("/")).parent == Path(thumb_target.rstrip("/")).parent
    assert client.sent_payload is not None
    file_path, thumb_path = client.sent_payload
    assert not Path(file_path).exists()
    assert thumb_path is not None
    assert not Path(thumb_path).exists()
