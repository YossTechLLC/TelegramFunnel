#!/usr/bin/env python
"""
GCBotCommand - Telegram Bot Webhook Service
Handles all bot commands, callbacks, and conversation flows
"""
import os
from flask import Flask
from config_manager import ConfigManager
from database_manager import DatabaseManager
from routes.webhook import webhook_bp
import logging

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def create_app():
    """Application factory pattern for Flask"""
    app = Flask(__name__)

    logger.info("🚀 Initializing GCBotCommand...")

    # Load configuration
    try:
        config_manager = ConfigManager()
        config = config_manager.initialize_config()
        app.config.update(config)
        logger.info("✅ Configuration loaded")
    except Exception as e:
        logger.error(f"❌ Failed to load configuration: {e}")
        raise

    # Initialize database manager
    try:
        db_manager = DatabaseManager()
        app.db = db_manager
        logger.info("✅ Database manager initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        raise

    # Store configuration in app context for handlers
    app.config_manager = config_manager

    # Register blueprints
    app.register_blueprint(webhook_bp)
    logger.info("✅ Routes registered")

    logger.info("🎉 GCBotCommand initialization complete!")

    return app

if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"🌐 Starting GCBotCommand on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
