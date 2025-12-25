"""
媒体文件处理工具模块

遵循 SRP 原则：仅负责媒体文件相关的工具函数
"""
import mimetypes


def get_mimetype(file_path: str) -> str:
    """获取文件的 MIME 类型

    Args:
        file_path: 文件路径

    Returns:
        str: MIME 类型字符串
    """
    mimetype, _ = mimetypes.guess_type(file_path)
    return mimetype or 'application/octet-stream'
