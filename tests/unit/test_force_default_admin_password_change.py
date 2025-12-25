"""
Unit tests for enforcing a password change when logged in with default admin/admin.
"""

from __future__ import annotations

from flask import Blueprint, Flask

from web.auth import api_login_required, login_required


def test_must_change_password_redirects_and_blocks_api() -> None:
    app = Flask(__name__)
    app.secret_key = "test-secret"

    admin_bp = Blueprint("admin", __name__)

    @admin_bp.get("/admin")
    @login_required
    def admin():
        return "admin"

    notes_bp = Blueprint("notes", __name__)

    @notes_bp.get("/notes")
    @login_required
    def notes():
        return "notes"

    api_bp = Blueprint("api", __name__)

    @api_bp.get("/api/ping")
    @api_login_required
    def ping():
        return {"success": True}

    app.register_blueprint(admin_bp)
    app.register_blueprint(notes_bp)
    app.register_blueprint(api_bp)

    client = app.test_client()
    with client.session_transaction() as session:
        session["username"] = "admin"
        session["must_change_password"] = True

    resp = client.get("/notes", follow_redirects=False)
    assert resp.status_code in {302, 303}
    assert resp.headers.get("Location", "").endswith("/admin")

    resp_admin = client.get("/admin")
    assert resp_admin.status_code == 200

    resp_api = client.get("/api/ping")
    assert resp_api.status_code == 403
    payload = resp_api.get_json()
    assert payload is not None
    assert payload.get("success") is False


def test_without_must_change_password_allows_access() -> None:
    app = Flask(__name__)
    app.secret_key = "test-secret"

    admin_bp = Blueprint("admin", __name__)

    @admin_bp.get("/admin")
    @login_required
    def admin():
        return "admin"

    notes_bp = Blueprint("notes", __name__)

    @notes_bp.get("/notes")
    @login_required
    def notes():
        return "notes"

    app.register_blueprint(admin_bp)
    app.register_blueprint(notes_bp)

    client = app.test_client()
    with client.session_transaction() as session:
        session["username"] = "admin"

    resp = client.get("/notes")
    assert resp.status_code == 200
    assert resp.data == b"notes"

