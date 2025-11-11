import os
import re
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash, jsonify
from markupsafe import Markup, escape
from database import init_database, get_notes, get_note_count, get_sources, verify_user, update_password, get_note_by_id, update_note, delete_note, DATA_DIR
import math

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your-secret-key-change-this-in-production')

# 初始化数据库
init_database()

# 每页显示的笔记数量
NOTES_PER_PAGE = 50

# 自定义Jinja2过滤器：高亮搜索关键词
@app.template_filter('highlight')
def highlight_filter(text, search_query):
    if not text or not search_query:
        return text
    
    # 转义HTML特殊字符
    text = escape(text)
    search_query = escape(search_query)
    
    # 使用正则表达式进行不区分大小写的替换
    pattern = re.compile(re.escape(str(search_query)), re.IGNORECASE)
    highlighted = pattern.sub(lambda m: f'<span class="highlight">{m.group()}</span>', str(text))
    
    return Markup(highlighted)

@app.route('/')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('notes'))

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
def notes():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    # 获取分页和过滤参数
    page = request.args.get('page', 1, type=int)
    source_filter = request.args.get('source', None)
    search_query = request.args.get('search', None)
    date_from = request.args.get('date_from', None)
    date_to = request.args.get('date_to', None)
    
    # 计算偏移量
    offset = (page - 1) * NOTES_PER_PAGE
    
    # 获取笔记
    notes_list = get_notes(source_chat_id=source_filter, search_query=search_query, 
                          date_from=date_from, date_to=date_to, 
                          limit=NOTES_PER_PAGE, offset=offset)
    
    # 获取总数和来源列表
    total_count = get_note_count(source_chat_id=source_filter, search_query=search_query,
                                 date_from=date_from, date_to=date_to)
    sources = get_sources()
    
    # 计算总页数
    total_pages = math.ceil(total_count / NOTES_PER_PAGE) if total_count > 0 else 1
    
    return render_template('notes.html',
                         notes=notes_list,
                         sources=sources,
                         total_count=total_count,
                         current_page=page,
                         total_pages=total_pages,
                         selected_source=source_filter,
                         search_query=search_query,
                         date_from=date_from,
                         date_to=date_to)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # 验证当前密码
        if not verify_user(session['username'], current_password):
            return render_template('admin.html', error='当前密码不正确')
        
        # 验证新密码
        if len(new_password) < 6:
            return render_template('admin.html', error='新密码长度至少为 6 个字符')
        
        if new_password != confirm_password:
            return render_template('admin.html', error='两次输入的新密码不一致')
        
        # 更新密码
        update_password(session['username'], new_password)
        return render_template('admin.html', success='密码更新成功')
    
    return render_template('admin.html')

@app.route('/media/<path:filename>')
def media(filename):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    media_dir = os.path.join(os.path.dirname(__file__), DATA_DIR, 'media')
    return send_from_directory(media_dir, filename)

@app.route('/edit_note/<int:note_id>', methods=['GET', 'POST'])
def edit_note(note_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    note = get_note_by_id(note_id)
    if not note:
        flash('笔记不存在')
        return redirect(url_for('notes'))
    
    if request.method == 'POST':
        new_text = request.form.get('message_text', '').strip()
        if update_note(note_id, new_text):
            flash('笔记更新成功')
            return redirect(url_for('notes'))
        else:
            flash('更新失败')
    
    return render_template('edit_note.html', note=note)

@app.route('/delete_note/<int:note_id>', methods=['POST'])
def delete_note_route(note_id):
    if 'username' not in session:
        return jsonify({'success': False, 'error': '未登录'}), 401
    
    if delete_note(note_id):
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': '删除失败'}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
