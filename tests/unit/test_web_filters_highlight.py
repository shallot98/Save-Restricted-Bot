"""
Unit tests for web.utils.filters.highlight_filter.
"""

from __future__ import annotations

from markupsafe import Markup

from web.utils.filters import highlight_filter


def test_highlight_filter_returns_original_when_missing_inputs() -> None:
    assert highlight_filter(None, "a") == ""
    assert highlight_filter("", "a") == ""
    assert highlight_filter("text", None) == "text"
    assert highlight_filter("text", "") == "text"


def test_highlight_filter_highlights_each_token_case_insensitive() -> None:
    result = highlight_filter("Hello world", "hello world")
    assert isinstance(result, Markup)
    assert '<span class="highlight">Hello</span>' in str(result)
    assert '<span class="highlight">world</span>' in str(result)


def test_highlight_filter_tokenizes_non_word_separators() -> None:
    result = highlight_filter("hello-world", "hello world")
    assert '<span class="highlight">hello</span>-<span class="highlight">world</span>' in str(result)


def test_highlight_filter_escapes_html_before_highlighting() -> None:
    result = highlight_filter("<b>Hello</b>", "hello")
    assert isinstance(result, Markup)
    assert str(result) == "&lt;b&gt;<span class=\"highlight\">Hello</span>&lt;/b&gt;"


def test_highlight_filter_returns_escaped_text_when_no_tokens() -> None:
    result = highlight_filter("<b>Hello</b>", "!!!")
    assert isinstance(result, Markup)
    assert str(result) == "&lt;b&gt;Hello&lt;/b&gt;"

