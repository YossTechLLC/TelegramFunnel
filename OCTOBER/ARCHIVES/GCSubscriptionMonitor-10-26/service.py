#!/usr/bin/env python
"""
GCSubscriptionMonitor-10-26: Subscription Expiration Monitoring Service
Cloud Run webhook triggered by Cloud Scheduler every 60 seconds
"""
from flask import Flask, request, jsonify
import logging
import os
import sqlalchemy
from config_manager import ConfigManager
from database_manager import DatabaseManager
from telegram_client import TelegramClient
from expiration_handler import ExpirationHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app():
    """Application factory pattern"""
    app = Flask(__name__)

    # Initialize configuration
    logger.info("🚀 Starting GCSubscriptionMonitor-10-26...")
    config_manager = ConfigManager()
    config = config_manager.initialize_config()

    if not config['bot_token']:
        logger.error("❌ Failed to initialize: Telegram bot token not available")
        raise RuntimeError("Cannot start service without bot token")

    # Initialize managers
    logger.info("🔌 Initializing database manager...")
    db_manager = DatabaseManager(
        instance_connection_name=config['instance_connection_name'],
        db_name=config['db_name'],
        db_user=config['db_user'],
        db_password=config['db_password']
    )

    logger.info("🤖 Initializing Telegram client...")
    telegram_client = TelegramClient(bot_token=config['bot_token'])

    logger.info("🔧 Initializing expiration handler...")
    expiration_handler = ExpirationHandler(
        db_manager=db_manager,
        telegram_client=telegram_client
    )

    logger.info("✅ All components initialized successfully")

    @app.route('/check-expirations', methods=['POST'])
    def check_expirations():
        """
        Main endpoint triggered by Cloud Scheduler every 60 seconds.
        Processes expired subscriptions and returns summary statistics.
        """
        try:
            logger.info("🕐 Checking for expired subscriptions...")

            result = expiration_handler.process_expired_subscriptions()

            logger.info(
                f"✅ Expiration check complete: "
                f"{result['expired_count']} found, "
                f"{result['processed_count']} processed, "
                f"{result['failed_count']} failed"
            )

            return jsonify({
                "status": "success",
                "expired_count": result['expired_count'],
                "processed_count": result['processed_count'],
                "failed_count": result['failed_count'],
                "details": result.get('details', [])
            }), 200

        except Exception as e:
            logger.error(f"❌ Error in expiration check: {e}", exc_info=True)
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

    @app.route('/health', methods=['GET'])
    def health():
        """Health check endpoint for Cloud Run"""
        try:
            # Verify database connectivity
            with db_manager.get_connection() as conn:
                result = conn.execute(sqlalchemy.text("SELECT 1"))
                result.fetchone()

            # Verify Telegram client is initialized
            if telegram_client.bot is None:
                raise RuntimeError("Telegram client not initialized")

            return jsonify({
                "status": "healthy",
                "service": "GCSubscriptionMonitor-10-26",
                "database": "connected",
                "telegram": "initialized"
            }), 200

        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            return jsonify({
                "status": "unhealthy",
                "error": str(e)
            }), 503

    logger.info("✅ Flask application created successfully")
    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"🌐 Starting server on port {port}...")
    app.run(host="0.0.0.0", port=port)
