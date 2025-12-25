"""
Main Routes
===========

Main page routes.
"""

from flask import Blueprint, render_template, redirect, url_for, session

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Home page - redirect to notes or login"""
    if session.get('logged_in'):
        return redirect(url_for('main.notes'))
    return redirect(url_for('auth.login'))


@main_bp.route('/notes')
def notes():
    """Notes page"""
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))
    return render_template('notes.html')


@main_bp.route('/health')
def health():
    """Health check endpoint"""
    return {'status': 'healthy'}
