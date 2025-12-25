"""
Web Presentation
================

Flask web application for the notes viewer.
"""

from flask import Flask
from typing import Optional


def create_app(config: Optional[dict] = None) -> Flask:
    """
    Application factory for Flask app

    Args:
        config: Optional configuration dictionary

    Returns:
        Configured Flask application
    """
    app = Flask(
        __name__,
        template_folder='../../../templates',
        static_folder='../../../static'
    )

    # Load configuration
    app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'

    if config:
        app.config.update(config)

    # Register blueprints
    from src.presentation.web.routes import register_routes
    register_routes(app)

    return app
