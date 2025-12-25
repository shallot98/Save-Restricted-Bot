"""
Authentication Routes
=====================

Login and logout routes.
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Import here to avoid circular imports
        from database import verify_user

        if verify_user(username, password):
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('main.notes'))
        else:
            flash('Invalid credentials', 'error')

    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    """Logout"""
    session.clear()
    return redirect(url_for('auth.login'))
