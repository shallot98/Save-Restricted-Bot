import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from functools import wraps
from database import get_notes, get_sources, count_notes, verify_user, change_password

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    if 'username' in session:
        return redirect(url_for('notes'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if verify_user(username, password):
            session['username'] = username
            return redirect(url_for('notes'))
        else:
            return render_template('login.html', error='用户名或密码错误')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/notes')
@login_required
def notes():
    user_id = request.args.get('user_id', '')
    source_filters = request.args.getlist('sources')
    page = int(request.args.get('page', 1))
    per_page = 50
    
    offset = (page - 1) * per_page
    
    # Get notes
    if source_filters:
        notes_list = get_notes(user_id if user_id else None, source_filters, per_page, offset)
        total_notes = count_notes(user_id if user_id else None, source_filters)
    else:
        notes_list = get_notes(user_id if user_id else None, None, per_page, offset)
        total_notes = count_notes(user_id if user_id else None, None)
    
    # Get all sources for filter
    all_sources = get_sources(user_id) if user_id else []
    
    total_pages = (total_notes + per_page - 1) // per_page
    
    return render_template('notes.html', 
                         notes=notes_list, 
                         sources=all_sources,
                         selected_sources=source_filters,
                         current_page=page,
                         total_pages=total_pages,
                         user_id=user_id)

@app.route('/admin')
@login_required
def admin():
    return render_template('admin.html')

@app.route('/admin/change_password', methods=['POST'])
@login_required
def admin_change_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    username = session.get('username')
    
    # Verify current password
    if not verify_user(username, current_password):
        return jsonify({'success': False, 'message': '当前密码错误'})
    
    # Check if new passwords match
    if new_password != confirm_password:
        return jsonify({'success': False, 'message': '两次输入的新密码不一致'})
    
    # Check password length
    if len(new_password) < 6:
        return jsonify({'success': False, 'message': '密码长度至少为6位'})
    
    # Change password
    change_password(username, new_password)
    
    return jsonify({'success': True, 'message': '密码修改成功'})

@app.route('/media/<path:filename>')
@login_required
def serve_media(filename):
    return send_from_directory('media', filename)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
