#!/usr/bin/env python3
"""
GCBroadcastService-10-26 - Main Application
Flask application for automated and manual broadcast management
"""

import os
import logging
from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager

# Import routes
from routes.broadcast_routes import broadcast_bp
from routes.api_routes import api_bp

# Import utilities
from utils.config import Config
from utils.logging_utils import setup_logging

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)


def create_app(config=None):
    """
    Application factory for GCBroadcastService.

    Args:
        config: Optional config override (for testing)

    Returns:
        Flask app instance
    """
    app = Flask(__name__)

    # Load configuration
    app_config = config or Config()
    app.config.update(app_config.to_dict())

    # Configure CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": ["https://www.paygateprime.com"],
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "supports_credentials": True,
            "max_age": 3600
        }
    })

    # Initialize JWT authentication
    jwt = JWTManager(app)

    # Register error handlers
    register_error_handlers(jwt)

    # Register blueprints
    app.register_blueprint(broadcast_bp)
    app.register_blueprint(api_bp)

    logger.info("✅ GCBroadcastService-10-26 initialized successfully")

    return app


def register_error_handlers(jwt):
    """Register JWT error handlers"""

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        logger.warning("⚠️ JWT token expired")
        return {'error': 'Token expired', 'message': 'Session expired. Please log in again.'}, 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        logger.warning(f"⚠️ Invalid JWT token: {error}")
        return {'error': 'Invalid token', 'message': 'Session expired. Please log in again.'}, 401

    @jwt.unauthorized_loader
    def unauthorized_callback(error):
        logger.warning("⚠️ Missing JWT token")
        return {'error': 'Missing Authorization header', 'message': 'Authentication required'}, 401


# Create app instance for gunicorn
app = create_app()


if __name__ == "__main__":
    # For local development only (production uses gunicorn)
    port = int(os.getenv('PORT', 8080))
    logger.info(f"🌟 Starting development server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=True)
