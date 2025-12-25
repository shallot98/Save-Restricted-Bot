"""
Unit tests for StorageManager path safety.
"""

from __future__ import annotations

from pathlib import Path

from bot.storage.webdav_client import StorageManager


class TestStorageManagerSecurity:
    def test_get_file_path_allows_safe_local(self, tmp_path: Path) -> None:
        (tmp_path / "ok.txt").write_bytes(b"hello")
        manager = StorageManager(str(tmp_path))

        assert manager.get_file_path("local:ok.txt") == str(tmp_path / "ok.txt")
        assert manager.get_file_path("ok.txt") == str(tmp_path / "ok.txt")

    def test_get_file_path_rejects_path_traversal(self, tmp_path: Path) -> None:
        manager = StorageManager(str(tmp_path))

        assert manager.get_file_path("../../etc/passwd") is None
        assert manager.get_file_path("local:../ok.txt") is None
        assert manager.get_file_path("local:sub/ok.txt") is None
        assert manager.get_file_path(r"local:sub\\ok.txt") is None

    def test_delete_file_rejects_path_traversal(self, tmp_path: Path) -> None:
        outside_file = tmp_path.parent / "outside.txt"
        outside_file.write_bytes(b"do-not-delete")

        manager = StorageManager(str(tmp_path))
        assert manager.delete_file(f"../{outside_file.name}") is False
        assert outside_file.exists()

