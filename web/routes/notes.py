"""
笔记管理路由模块

遵循 SRP 原则：仅负责笔记的展示、编辑和删除

Architecture: Uses new layered architecture
- src/core/container for service access
- src/application/services for business logic
"""
import math
import logging
from urllib.parse import quote
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify

# New architecture imports
from src.core.container import get_note_service
from src.core.exceptions import NotFoundError

# Legacy imports (for backward compatibility)
from config import load_viewer_config
from bot.config.constants import AppConstants
from bot.utils.magnet_utils import extract_all_dns_from_note
from web.auth import login_required, api_login_required
from web.utils.filters import format_text_with_magnet_break

logger = logging.getLogger(__name__)

notes_bp = Blueprint('notes', __name__)

NOTES_PER_PAGE = AppConstants.NOTES_PER_PAGE


@notes_bp.route('/notes')
@login_required
def notes_list():
    """笔记列表页面

    支持分页、来源过滤、搜索、日期范围和收藏过滤

    Uses NoteService from new architecture for data access.
    """
    note_service = get_note_service()

    # 获取分页和过滤参数
    page = request.args.get('page', 1, type=int)
    source_filter = request.args.get('source', None)
    search_query = request.args.get('search', None)
    date_from = request.args.get('date_from', None)
    date_to = request.args.get('date_to', None)
    favorite_only = request.args.get('favorite', None) == '1'

    # 使用 NoteService 获取分页笔记
    result = note_service.get_notes(
        user_id=None,  # 不按用户过滤
        source_chat_id=source_filter,
        search_query=search_query,
        date_from=date_from,
        date_to=date_to,
        favorite_only=favorite_only,
        page=page,
        page_size=NOTES_PER_PAGE
    )

    # 将 DTO 转换为字典以便模板使用
    notes_data = [_dto_to_dict(note) for note in result.items]

    # 获取观看网站配置
    viewer_config = load_viewer_config()
    viewer_url = viewer_config.get('viewer_url', '')

    # 为每条笔记添加所有磁力链接和观看链接
    for note in notes_data:
        _process_note_magnets(note, viewer_url)

    # 使用 NoteService 获取所有来源列表
    sources = note_service.get_all_sources()

    return render_template(
        'notes.html',
        notes=notes_data,
        sources=sources,
        total_count=result.total,
        current_page=result.page,
        total_pages=result.total_pages,
        selected_source=source_filter,
        search_query=search_query,
        date_from=date_from,
        date_to=date_to,
        favorite_only=favorite_only,
        viewer_url=viewer_url
    )


def _dto_to_dict(note_dto) -> dict:
    """将 NoteDTO 转换为字典

    Args:
        note_dto: NoteDTO 对象

    Returns:
        dict: 笔记字典
    """
    return {
        'id': note_dto.id,
        'user_id': note_dto.user_id,
        'source_chat_id': note_dto.source_chat_id,
        'source_name': note_dto.source_name,
        'message_text': note_dto.message_text,
        'timestamp': note_dto.timestamp,
        'media_type': note_dto.media_type,
        'media_path': note_dto.media_path,
        'media_paths': note_dto.media_paths,
        'magnet_link': note_dto.magnet_link,
        'filename': note_dto.filename,
        'is_favorite': note_dto.is_favorite,
    }


def _process_note_magnets(note: dict, viewer_url: str) -> None:
    """处理笔记中的磁力链接

    Args:
        note: 笔记字典
        viewer_url: 观看网站 URL
    """
    # 提取所有 dn 参数
    all_dns = extract_all_dns_from_note(note)
    note['all_dns'] = all_dns

    # 格式化显示文本
    if note.get('message_text'):
        note['message_text'] = format_text_with_magnet_break(note['message_text'])

    # 为向后兼容，保留单个 watch_url
    if all_dns and viewer_url:
        note['watch_url'] = viewer_url + quote(all_dns[0]['dn']) if all_dns[0]['dn'] else None
    else:
        note['watch_url'] = None


@notes_bp.route('/edit_note/<int:note_id>', methods=['GET', 'POST'])
@login_required
def edit_note(note_id: int):
    """编辑笔记页面

    Uses NoteService for data access.

    Args:
        note_id: 笔记 ID
    """
    note_service = get_note_service()

    try:
        note_dto = note_service.get_note(note_id)
        note = _dto_to_dict(note_dto)
    except NotFoundError:
        flash('笔记不存在')
        return redirect(url_for('notes.notes_list'))

    if request.method == 'POST':
        new_text = request.form.get('message_text', '').strip()
        try:
            # 使用 NoteService 更新笔记文本
            note_service.update_text(note_id, new_text)
            flash('笔记更新成功')
            return_url = request.form.get('return_url', url_for('notes.notes_list'))
            return redirect(return_url)
        except Exception as e:
            logger.exception(f"更新笔记失败: {e}")
            flash('更新失败')

    return render_template(
        'edit_note.html',
        note=note,
        return_url=request.referrer or url_for('notes.notes_list')
    )


@notes_bp.route('/delete_note/<int:note_id>', methods=['POST'])
@api_login_required
def delete_note_route(note_id: int):
    """删除笔记 API

    Uses NoteService for data access.

    Args:
        note_id: 笔记 ID

    Returns:
        JSON 响应
    """
    note_service = get_note_service()

    try:
        note_service.delete_note(note_id)
        return jsonify({'success': True, 'reload': False})
    except NotFoundError:
        return jsonify({'success': False, 'error': '笔记不存在'}), 404
    except Exception as e:
        logger.exception(f"删除笔记失败: {e}")
        return jsonify({'success': False, 'error': '删除失败'}), 500


@notes_bp.route('/toggle_favorite/<int:note_id>', methods=['POST'])
@api_login_required
def toggle_favorite_route(note_id: int):
    """切换收藏状态 API

    Uses NoteService for data access.

    Args:
        note_id: 笔记 ID

    Returns:
        JSON 响应
    """
    note_service = get_note_service()

    try:
        new_status = note_service.toggle_favorite(note_id)
        return jsonify({'success': True, 'is_favorite': new_status})
    except NotFoundError:
        return jsonify({'success': False, 'error': '笔记不存在'}), 404
    except Exception as e:
        logger.exception(f"切换收藏状态失败: {e}")
        return jsonify({'success': False, 'error': '操作失败'}), 500
