"""
Jinja2 自定义过滤器模块

遵循 SRP 原则：仅负责模板过滤器的定义和注册
"""
import re
from typing import Optional, Union
from flask import Flask
from markupsafe import Markup, escape


_SEARCH_TOKEN_PATTERN = re.compile(r"[0-9A-Za-z\u4e00-\u9fff]+")


def _extract_search_tokens(search_query: str) -> list[str]:
    tokens = _SEARCH_TOKEN_PATTERN.findall(search_query)

    normalized: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        term = token.strip()
        if not term:
            continue
        key = term.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(term)

    return normalized


def highlight_filter(text: Optional[str], search_query: Optional[str]) -> Union[str, Markup]:
    """高亮搜索关键词过滤器

    Args:
        text: 原始文本
        search_query: 搜索关键词

    Returns:
        处理后的文本，关键词被 <span class="highlight"> 包裹
    """
    if not text or not search_query:
        return text or ''

    # 转义 HTML 特殊字符
    escaped_text = escape(text)
    tokens = _extract_search_tokens(str(search_query))
    if not tokens:
        return Markup(escaped_text)

    tokens = sorted(tokens, key=len, reverse=True)
    pattern = re.compile("|".join(re.escape(token) for token in tokens), re.IGNORECASE)
    highlighted = pattern.sub(
        lambda m: f'<span class="highlight">{m.group()}</span>',
        str(escaped_text)
    )

    return Markup(highlighted)


def format_text_with_magnet_break(message_text: Optional[str]) -> Union[str, Markup]:
    """在第一个磁力链接前添加换行标签

    Args:
        message_text: 笔记文本

    Returns:
        处理后的 HTML 安全文本
    """
    if not message_text:
        return message_text or ''

    # 转义 HTML 特殊字符
    text = escape(message_text)

    # 正则匹配第一个 magnet 链接
    magnet_pattern = r'magnet:\?xt=urn:btih:[a-zA-Z0-9]+(?:[&?][^\s\n]*)?'
    match = re.search(magnet_pattern, str(text), re.IGNORECASE)

    if match:
        start_pos = match.start()
        # 在磁力链接前添加 <br> 标签
        text = str(text[:start_pos]) + '<br>' + str(text[start_pos:])

    return Markup(text)


def register_filters(app: Flask) -> None:
    """注册所有自定义过滤器到 Flask 应用

    Args:
        app: Flask 应用实例
    """
    app.template_filter('highlight')(highlight_filter)
    app.template_filter('magnet_break')(format_text_with_magnet_break)
