import os
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from database import init_database, get_notes, get_note_count, get_sources, verify_user, update_password
import math

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your-secret-key-change-this-in-production')

# 初始化数据库
init_database()

# 每页显示的笔记数量
NOTES_PER_PAGE = 50

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
    
    # 计算偏移量
    offset = (page - 1) * NOTES_PER_PAGE
    
    # 获取笔记
    notes_list = get_notes(source_chat_id=source_filter, search_query=search_query, limit=NOTES_PER_PAGE, offset=offset)
    
    # 获取总数和来源列表
    total_count = get_note_count(source_chat_id=source_filter, search_query=search_query)
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
                         search_query=search_query)

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
    
    media_dir = os.path.join(os.path.dirname(__file__), 'media')
    return send_from_directory(media_dir, filename)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
