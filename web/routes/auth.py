"""
认证路由模块

遵循 SRP 原则：仅负责用户登录和登出
"""
from datetime import timedelta
from flask import Blueprint, render_template, request, redirect, url_for, session, current_app, g
from database import verify_user
from bot.config.constants import AppConstants
from web.security.rate_limit import get_login_rate_limiter

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录

    GET: 显示登录页面
    POST: 处理登录请求
    """
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember')

        # 基础限流：降低暴力破解风险（进程内，默认 10 次/10 分钟，可通过环境变量调整）
        limiter = get_login_rate_limiter()
        client_ip = request.remote_addr or "unknown"
        limit_key = f"{client_ip}:{username or ''}"
        if not limiter.allow(limit_key):
            g.csp_allow_unsafe_eval = False
            return render_template('login.html', error='尝试过于频繁，请稍后再试'), 429

        if verify_user(username, password):
            # 防止会话固定：登录成功后清理旧 session
            session.clear()
            session['username'] = username
            limiter.reset(limit_key)

            # 默认 admin/admin 强制首次改密（提升基线安全性，避免长期使用弱口令）
            must_change_password = username == "admin" and password == "admin"
            if must_change_password:
                session["must_change_password"] = True

            # 如果勾选了"记住密码"，设置 session 为永久
            if remember:
                session.permanent = True
                current_app.permanent_session_lifetime = timedelta(
                    days=AppConstants.SESSION_LIFETIME_DAYS
                )
            else:
                session.permanent = False

            if must_change_password:
                return redirect(url_for("admin.admin"))

            return redirect(url_for('notes.notes_list'))
        else:
            g.csp_allow_unsafe_eval = False
            return render_template('login.html', error='用户名或密码错误')

    g.csp_allow_unsafe_eval = False
    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    """用户登出"""
    session.clear()
    return redirect(url_for('auth.login'))
