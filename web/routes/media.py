"""
媒体文件服务路由模块

遵循 SRP 原则：仅负责媒体文件的访问和代理

Architecture: Uses new layered architecture
- src/compat for backward compatibility
"""
import os
import re
from urllib.parse import unquote
from flask import Blueprint, redirect, url_for, request, Response, send_from_directory, current_app
import requests

# New architecture imports
from src.compat.config_compat import load_webdav_config
from web.auth import login_required
from web.utils.media import get_mimetype

media_bp = Blueprint('media', __name__)


def _extract_filename(storage_location: str) -> str:
    """从 storage_location 中提取展示用文件名（不参与权限/路径校验）。"""
    raw = storage_location
    if ":" in raw:
        raw = raw.split(":", 1)[1]
    return os.path.basename(raw)


@media_bp.route('/media/<path:storage_location>')
@login_required
def media(storage_location: str):
    """提供媒体文件访问

    支持本地文件和 WebDAV 代理，支持 Range 请求

    Args:
        storage_location: 存储位置路径
    """
    try:
        # URL 解码存储位置
        storage_location = unquote(storage_location)
        download_name = _extract_filename(storage_location)

        # 获取文件路径或 URL
        storage_manager = current_app.storage_manager
        file_path_or_url = storage_manager.get_file_path(storage_location)

        if not file_path_or_url:
            return "File not found", 404

        # 如果是 HTTP/HTTPS URL（WebDAV），代理请求
        if file_path_or_url.startswith(('http://', 'https://')):
            return _proxy_webdav_file(file_path_or_url, download_name)

        # 本地文件
        return _serve_local_file(file_path_or_url)

    except Exception as e:
        return f"Error: {str(e)}", 500


def _proxy_webdav_file(file_url: str, download_name: str) -> Response:
    """代理 WebDAV 文件请求

    Args:
        file_url: WebDAV 文件 URL
        download_name: 展示用文件名

    Returns:
        Response: Flask 响应对象
    """
    try:
        webdav_config = load_webdav_config()
        username = webdav_config.get('username', '')
        password = webdav_config.get('password', '')

        # 检查是否有 Range 请求头
        range_header = request.headers.get('Range')
        headers = {}
        if range_header:
            headers['Range'] = range_header

        # 代理请求到 WebDAV 服务器
        response = requests.get(
            file_url,
            auth=(username, password),
            headers=headers,
            stream=True,
            timeout=30
        )

        if response.status_code in (200, 206):
            response_headers = {
                'Content-Disposition': f'inline; filename="{download_name}"',
                'Accept-Ranges': 'bytes',
                'Cache-Control': 'public, max-age=31536000, immutable'
            }

            if 'Content-Length' in response.headers:
                response_headers['Content-Length'] = response.headers['Content-Length']
            if 'Content-Range' in response.headers:
                response_headers['Content-Range'] = response.headers['Content-Range']

            return Response(
                response.iter_content(chunk_size=8192),
                status=response.status_code,
                content_type=response.headers.get('Content-Type', 'application/octet-stream'),
                headers=response_headers
            )
        else:
            return Response(f"Failed to fetch from WebDAV: {response.status_code}", status=502)

    except Exception as e:
        return Response(f"Error fetching from WebDAV: {str(e)}", status=502)


def _serve_local_file(file_path: str) -> Response:
    """提供本地文件服务

    Args:
        file_path: 本地文件路径

    Returns:
        Response: Flask 响应对象
    """
    if not os.path.exists(file_path):
        return Response("File not found", status=404)

    file_size = os.path.getsize(file_path)
    range_header = request.headers.get('Range')

    if range_header:
        return _serve_partial_content(file_path, file_size, range_header)

    # 正常返回整个文件
    media_dir = os.path.dirname(file_path)
    filename = os.path.basename(file_path)
    response = send_from_directory(media_dir, filename)
    response.headers['Accept-Ranges'] = 'bytes'
    response.headers['Content-Length'] = str(file_size)
    response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    return response


def _serve_partial_content(file_path: str, file_size: int, range_header: str) -> Response:
    """提供部分内容响应（Range 请求）

    Args:
        file_path: 文件路径
        file_size: 文件大小
        range_header: Range 请求头

    Returns:
        Response: 206 Partial Content 响应
    """
    match = re.search(r'bytes=(\d*)-(\d*)', range_header)
    if not match:
        return Response("Invalid Range header", status=416)

    start_str, end_str = match.group(1), match.group(2)

    # bytes=-N (suffix)
    if not start_str and end_str:
        suffix_len = int(end_str)
        if suffix_len <= 0:
            return Response("Invalid Range header", status=416)
        start = max(file_size - suffix_len, 0)
        end = file_size - 1
    else:
        if not start_str:
            return Response("Invalid Range header", status=416)
        start = int(start_str)
        end = int(end_str) if end_str else file_size - 1
        end = min(end, file_size - 1)

    if start >= file_size or start < 0 or end < start:
        return Response("Invalid Range header", status=416)

    def _iter_range(path: str, start_pos: int, end_pos: int, chunk_size: int = 8192):
        with open(path, "rb") as f:
            f.seek(start_pos)
            remaining = end_pos - start_pos + 1
            while remaining > 0:
                chunk = f.read(min(chunk_size, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    response = Response(
        _iter_range(file_path, start, end),
        status=206,
        mimetype=get_mimetype(file_path),
        direct_passthrough=True,
    )
    response.headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
    response.headers['Content-Length'] = str(end - start + 1)
    response.headers['Accept-Ranges'] = 'bytes'
    response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    return response
