"""
Unit tests for basic web security baseline: CSRF, security headers, and login rate limiting.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

import pytest
from flask import Flask

from web.security.csrf import csrf_token, init_csrf
from web.security.headers import init_security_headers
from web.security.rate_limit import RateLimitConfig, SlidingWindowRateLimiter


def _templates_dir() -> str:
    repo_root = Path(__file__).resolve().parents[2]
    return str(repo_root / "templates")


@pytest.fixture
def app() -> Flask:
    app = Flask(__name__, template_folder=_templates_dir())
    app.secret_key = "test-secret"
    init_csrf(app)
    init_security_headers(app)

    @app.get("/token")
    def _token():
        return csrf_token()

    @app.post("/protected")
    def _protected():
        return "ok"

    return app


@pytest.fixture
def client(app: Flask):
    return app.test_client()


def test_security_headers_present(client) -> None:
    resp = client.get("/token")
    assert resp.status_code == 200
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    csp = resp.headers.get("Content-Security-Policy")
    assert csp
    assert "script-src-attr 'none'" in csp
    assert re.search(r"script-src[^;]*'nonce-[^']+'", csp) is not None
    assert re.search(r"script-src[^;]*'unsafe-inline'", csp) is None
    assert resp.headers.get("Cache-Control") == "no-store"
    assert resp.headers.get("Pragma") == "no-cache"
    assert resp.headers.get("Expires") == "0"


def test_can_disable_unsafe_eval_per_request(app: Flask) -> None:
    from flask import g

    @app.get("/no-unsafe-eval")
    def _no_unsafe_eval():
        g.csp_allow_unsafe_eval = False
        return "ok"

    client = app.test_client()
    resp = client.get("/no-unsafe-eval")
    csp = resp.headers.get("Content-Security-Policy") or ""
    assert "unsafe-eval" not in csp


def test_csrf_blocks_missing_token(client) -> None:
    resp = client.post("/protected")
    assert resp.status_code == 403


def test_csrf_accepts_form_token(client) -> None:
    token = client.get("/token").data.decode("utf-8")
    resp = client.post("/protected", data={"csrf_token": token})
    assert resp.status_code == 200
    assert resp.data == b"ok"


def test_csrf_accepts_header_token(client) -> None:
    token = client.get("/token").data.decode("utf-8")
    resp = client.post("/protected", headers={"X-CSRFToken": token})
    assert resp.status_code == 200


def test_csrf_accepts_json_token(client) -> None:
    token = client.get("/token").data.decode("utf-8")
    resp = client.post("/protected", json={"csrf_token": token})
    assert resp.status_code == 200


def test_login_rate_limiter_basic_behavior() -> None:
    limiter = SlidingWindowRateLimiter(RateLimitConfig(max_attempts=2, window_seconds=3600))
    key = "ip:user"

    assert limiter.allow(key) is True
    assert limiter.allow(key) is True
    assert limiter.allow(key) is False

    limiter.reset(key)
    assert limiter.allow(key) is True


def test_login_route_returns_429_when_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    from web.routes.auth import auth_bp
    import web.routes.auth as auth_module

    app = Flask(__name__, template_folder=_templates_dir())
    app.secret_key = "test-secret"
    init_csrf(app)
    init_security_headers(app)
    app.register_blueprint(auth_bp)

    class _DenyLimiter:
        def allow(self, _key: str) -> bool:
            return False

        def reset(self, _key: str) -> None:
            return None

    monkeypatch.setattr(auth_module, "get_login_rate_limiter", lambda: _DenyLimiter(), raising=True)

    client = app.test_client()
    html = client.get("/login").data.decode("utf-8")
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match is not None
    token = match.group(1)

    resp = client.post("/login", data={"username": "admin", "password": "x", "csrf_token": token})
    assert resp.status_code == 429
