"""
Unit tests for local media route security and Range handling.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flask import Flask

from bot.storage.webdav_client import StorageManager
from web.routes.media import media_bp


@pytest.fixture
def app(tmp_path: Path) -> Flask:
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.storage_manager = StorageManager(str(tmp_path))
    app.register_blueprint(media_bp)
    return app


@pytest.fixture
def client(app: Flask):
    client = app.test_client()
    with client.session_transaction() as session:
        session["username"] = "test"
    return client


class TestMediaRouteRange:
    def test_serves_local_file(self, tmp_path: Path, client) -> None:
        (tmp_path / "a.txt").write_bytes(b"hello world")
        response = client.get("/media/local%3Aa.txt")
        assert response.status_code == 200
        assert response.data == b"hello world"

    def test_serves_range_prefix(self, tmp_path: Path, client) -> None:
        (tmp_path / "a.txt").write_bytes(b"hello world")
        response = client.get("/media/local%3Aa.txt", headers={"Range": "bytes=0-4"})
        assert response.status_code == 206
        assert response.data == b"hello"
        assert response.headers.get("Content-Range") == "bytes 0-4/11"

    def test_serves_range_suffix(self, tmp_path: Path, client) -> None:
        (tmp_path / "a.txt").write_bytes(b"hello world")
        response = client.get("/media/local%3Aa.txt", headers={"Range": "bytes=-5"})
        assert response.status_code == 206
        assert response.data == b"world"

    def test_rejects_traversal(self, client) -> None:
        response = client.get("/media/%2e%2e%2f%2e%2e%2fetc%2fpasswd")
        assert response.status_code == 404

