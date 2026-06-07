from dataclasses import dataclass

from src.application.services.qbittorrent_service import QBittorrentService


@dataclass
class _NoteDTO:
    magnet_link: str | None = None
    message_text: str | None = None
    filename: str | None = None


def test_extract_note_magnets_for_download_deduplicates_info_hash() -> None:
    magnet = "magnet:?xt=urn:btih:ABCDEF1234567890&dn=file1"
    note = _NoteDTO(
        magnet_link=magnet,
        message_text=f"first {magnet} second {magnet}",
        filename="file1",
    )

    results = QBittorrentService.extract_note_magnets_for_download(note)

    assert len(results) == 1
    assert results[0]["info_hash"] == "ABCDEF1234567890"


def test_map_status_handles_done_and_pending() -> None:
    done = QBittorrentService._map_status({"progress": 1, "state": "uploading"})
    pending = QBittorrentService._map_status({"progress": 0, "state": "queuedDL"})

    assert done == ("done", 1.0)
    assert pending == ("pending", 0.0)
