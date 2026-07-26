"""WebDAV media cache helpers."""

from __future__ import annotations

import hashlib
import logging
import os
import threading

import requests

from database import DATA_DIR
from config import load_webdav_config

logger = logging.getLogger(__name__)

DOWNLOAD_CHUNK_SIZE = 65536
WEBDAV_DOWNLOAD_TIMEOUT_SECONDS = 60
WEBDAV_CACHE_DIR = os.path.join(DATA_DIR, "cache", "webdav")
os.makedirs(WEBDAV_CACHE_DIR, exist_ok=True)

_file_locks = {}
_file_locks_lock = threading.Lock()


class WebDAVFetchError(Exception):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"Failed to fetch from WebDAV: {status_code}")


def get_cached_webdav_file(file_url: str, download_name: str) -> str:
    cache_path = _get_cache_path(file_url)
    if _is_cache_valid(cache_path):
        logger.debug(f"📦 Cache hit: {download_name}")
        return cache_path

    with _get_file_lock(cache_path):
        if _is_cache_valid(cache_path):
            logger.debug(f"📦 Cache populated by another request: {download_name}")
            return cache_path
        logger.info(f"📥 Cache miss, downloading: {download_name}")
        _download_webdav_file(file_url, cache_path)
        logger.info(f"✅ Cached: {download_name} ({os.path.getsize(cache_path)} bytes)")
        return cache_path


def _get_file_lock(cache_path: str) -> threading.Lock:
    with _file_locks_lock:
        if cache_path not in _file_locks:
            _file_locks[cache_path] = threading.Lock()
        return _file_locks[cache_path]


def _get_cache_path(file_url: str) -> str:
    url_hash = hashlib.md5(file_url.encode()).hexdigest()[:16]
    filename = os.path.basename(file_url.split("?")[0])
    return os.path.join(WEBDAV_CACHE_DIR, f"{url_hash}_{filename}")


def _is_cache_valid(cache_path: str) -> bool:
    return os.path.exists(cache_path) and os.path.getsize(cache_path) > 0


def _download_webdav_file(file_url: str, cache_path: str) -> None:
    response = _fetch_webdav_response(file_url)
    temp_cache_path = cache_path + ".tmp"
    try:
        _write_response_to_cache(response, temp_cache_path)
        os.rename(temp_cache_path, cache_path)
    except Exception:
        _remove_temp_cache_file(temp_cache_path)
        raise


def _fetch_webdav_response(file_url: str):
    webdav_config = load_webdav_config()
    response = requests.get(
        file_url,
        auth=(webdav_config.get("username", ""), webdav_config.get("password", "")),
        stream=True,
        timeout=WEBDAV_DOWNLOAD_TIMEOUT_SECONDS,
    )
    if response.status_code != 200:
        raise WebDAVFetchError(response.status_code)
    return response


def _write_response_to_cache(response, temp_cache_path: str) -> None:
    with open(temp_cache_path, "wb") as cache_file:
        for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
            if chunk:
                cache_file.write(chunk)


def _remove_temp_cache_file(temp_cache_path: str) -> None:
    if not os.path.exists(temp_cache_path):
        return
    try:
        os.remove(temp_cache_path)
    except OSError:
        pass
