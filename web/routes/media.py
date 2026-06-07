"""
媒体文件服务路由模块

遵循 SRP 原则：仅负责媒体文件的访问和代理

Architecture: Uses new layered architecture
- src/compat for backward compatibility

Performance: WebDAV files are cached locally to avoid repeated remote fetches
"""
import os
import logging
from urllib.parse import unquote
from flask import Blueprint, request, Response, send_from_directory, current_app

from web.auth import login_required
from web.utils.media import get_mimetype
from web.routes.media_cache import WebDAVFetchError, get_cached_webdav_file
from web.routes.media_range import iter_file_range, parse_byte_range

media_bp = Blueprint('media', __name__)
logger = logging.getLogger(__name__)


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
    """代理 WebDAV 文件请求（带本地缓存 + 并发优化）

    缓存策略：
    1. 首次请求：从 WebDAV 下载并缓存到本地
    2. 后续请求：直接从本地缓存提供文件
    3. 支持 Range 请求（针对缓存文件）
    4. 使用文件级锁，允许多个文件并发下载
    """
    try:
        cache_path = get_cached_webdav_file(file_url, download_name)
        return _serve_local_file(cache_path)
    except WebDAVFetchError as e:
        return Response(f"Failed to fetch from WebDAV: {e.status_code}", status=502)
    except Exception as e:
        logger.error(f"❌ WebDAV proxy error: {e}")
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
    byte_range = parse_byte_range(range_header, file_size)
    if byte_range is None:
        return Response("Invalid Range header", status=416)

    response = Response(
        iter_file_range(file_path, byte_range),
        status=206,
        mimetype=get_mimetype(file_path),
        direct_passthrough=True,
    )
    response.headers['Content-Range'] = f'bytes {byte_range.start}-{byte_range.end}/{file_size}'
    response.headers['Content-Length'] = str(byte_range.length)
    response.headers['Accept-Ranges'] = 'bytes'
    response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    return response
