from dataclasses import dataclass

from src.application.services.message_worker_service import MessageWorkerService


@dataclass
class _NoteDTO:
    id: int


class _DummyNoteService:
    def __init__(self) -> None:
        self.created = None
        self.updated = None

    def create_note(self, note_data):
        self.created = note_data
        return _NoteDTO(id=123)

    def update_magnet(self, note_id, magnet_link, filename=None):
        self.updated = (note_id, magnet_link, filename)
        return True


def test_build_watch_task_maps_raw_watch_data() -> None:
    task = MessageWorkerService.build_watch_task(
        source_chat_id="src",
        dest_chat_id="dst",
        watch_data={
            "whitelist": ["foo"],
            "blacklist": ["bar"],
            "preserve_forward_source": True,
            "forward_mode": "extract",
            "extract_patterns": ["id=(\\d+)"],
            "record_mode": False,
        },
    )

    assert task.source == "src"
    assert task.dest == "dst"
    assert task.whitelist == ["foo"]
    assert task.preserve_forward_source is True
    assert task.forward_mode == "extract"


def test_save_recorded_note_updates_magnet_when_present() -> None:
    note_service = _DummyNoteService()
    service = MessageWorkerService(note_service)

    note_id = service.save_recorded_note(
        user_id="1",
        source_chat_id="src",
        source_name="Source",
        content_to_save="hello magnet:?xt=urn:btih:ABCDEF1234567890",
        media_type=None,
        media_path=None,
        media_paths=[],
        media_group_id=None,
    )

    assert note_id == 123
    assert note_service.created.user_id == 1
    assert note_service.updated[0] == 123
    assert note_service.updated[1].startswith("magnet:?xt=urn:btih:ABCDEF1234567890")
