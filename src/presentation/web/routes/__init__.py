"""
Web Routes
==========

Flask route blueprints.
"""

from flask import Flask


def register_routes(app: Flask) -> None:
    """
    Register all route blueprints

    Args:
        app: Flask application instance
    """
    from src.presentation.web.routes.main import main_bp
    from src.presentation.web.routes.api import api_bp
    from src.presentation.web.routes.auth import auth_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(auth_bp, url_prefix='/auth')
