"""
认证装饰器和工具模块

遵循 DRY 原则：统一认证逻辑，避免重复代码
"""
from functools import wraps
from typing import Callable, Any
from flask import session, redirect, url_for, jsonify, request


def login_required(f: Callable) -> Callable:
    """视图函数登录验证装饰器

    用于需要登录才能访问的页面路由

    Args:
        f: 被装饰的视图函数

    Returns:
        Callable: 包装后的函数
    """
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        if 'username' not in session:
            return redirect(url_for('auth.login'))
        if session.get("must_change_password") and request.endpoint not in {"admin.admin", "auth.logout"}:
            return redirect(url_for("admin.admin"))
        return f(*args, **kwargs)
    return decorated_function


def api_login_required(f: Callable) -> Callable:
    """API 端点登录验证装饰器

    用于需要登录才能访问的 API 端点，返回 JSON 错误响应

    Args:
        f: 被装饰的视图函数

    Returns:
        Callable: 包装后的函数
    """
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        if 'username' not in session:
            return jsonify({'success': False, 'error': '未登录'}), 401
        if session.get("must_change_password"):
            return jsonify({'success': False, 'error': '请先修改默认密码'}), 403
        return f(*args, **kwargs)
    return decorated_function
