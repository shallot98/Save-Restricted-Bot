"""
API Routes
==========

REST API endpoints using new architecture services.
"""

import logging
from functools import wraps
from flask import Blueprint, jsonify, request, session
from dataclasses import asdict

from src.core.container import get_note_service, get_calibration_service
from src.core.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)


def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated


def handle_errors(f):
    """Decorator to handle service exceptions"""
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except NotFoundError as e:
            return jsonify({'error': str(e)}), 404
        except ValidationError as e:
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            logger.exception(f"API error in {f.__name__}: {e}")
            return jsonify({'error': 'Internal server error'}), 500
    return decorated


@api_bp.route('/notes')
@require_auth
@handle_errors
def get_notes():
    """Get notes list using NoteService"""
    note_service = get_note_service()

    # Parse query parameters
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 50, type=int)
    source = request.args.get('source')
    search = request.args.get('search')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    favorite_only = request.args.get('favorite_only', 'false').lower() == 'true'
    user_id = request.args.get('user_id', type=int)

    # Get paginated notes
    result = note_service.get_notes(
        user_id=user_id,
        source_chat_id=source,
        search_query=search,
        date_from=date_from,
        date_to=date_to,
        favorite_only=favorite_only,
        page=page,
        page_size=page_size
    )

    # Convert DTOs to dicts for JSON serialization
    notes = [asdict(note) for note in result.items]

    return jsonify({
        'notes': notes,
        'total': result.total,
        'page': result.page,
        'page_size': result.page_size,
        'total_pages': result.total_pages
    })


@api_bp.route('/notes/<int:note_id>')
@require_auth
@handle_errors
def get_note(note_id):
    """Get single note using NoteService"""
    note_service = get_note_service()
    note_dto = note_service.get_note(note_id)
    return jsonify(asdict(note_dto))


@api_bp.route('/notes/<int:note_id>', methods=['DELETE'])
@require_auth
@handle_errors
def delete_note(note_id):
    """Delete note using NoteService"""
    note_service = get_note_service()
    note_service.delete_note(note_id)
    return jsonify({'success': True})


@api_bp.route('/notes/<int:note_id>/favorite', methods=['POST'])
@require_auth
@handle_errors
def toggle_favorite(note_id):
    """Toggle note favorite status using NoteService"""
    note_service = get_note_service()
    new_status = note_service.toggle_favorite(note_id)
    return jsonify({'success': True, 'is_favorite': new_status})


@api_bp.route('/sources')
@require_auth
@handle_errors
def get_sources():
    """Get unique sources using NoteService"""
    note_service = get_note_service()
    user_id = request.args.get('user_id', type=int)
    sources = note_service.get_sources(user_id) if user_id else []
    return jsonify(sources)


# ==================== Calibration API ====================

@api_bp.route('/calibration/config')
@require_auth
@handle_errors
def get_calibration_config():
    """Get calibration configuration"""
    calibration_service = get_calibration_service()
    config = calibration_service.get_config()
    return jsonify(config.to_dict())


@api_bp.route('/calibration/config', methods=['PUT'])
@require_auth
@handle_errors
def update_calibration_config():
    """Update calibration configuration"""
    calibration_service = get_calibration_service()
    config_data = request.get_json()
    config = calibration_service.update_config(config_data)
    return jsonify(config.to_dict())


@api_bp.route('/calibration/stats')
@require_auth
@handle_errors
def get_calibration_stats():
    """Get calibration statistics"""
    calibration_service = get_calibration_service()
    stats = calibration_service.get_stats()
    return jsonify(stats)
