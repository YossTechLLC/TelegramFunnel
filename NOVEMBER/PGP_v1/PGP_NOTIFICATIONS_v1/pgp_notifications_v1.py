#!/usr/bin/env python
"""
📬 PGP_NOTIFICATIONS - Standalone Notification Webhook
Sends payment notifications to channel owners via Telegram Bot API
Version: 1.0
Date: 2025-11-12
"""
from flask import Flask, request, jsonify, abort
from config_manager import ConfigManager
from database_manager import DatabaseManager
from notification_handler import NotificationHandler
from telegram_client import TelegramClient
import logging
import sys
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


def create_app():
    """
    Application factory for Flask app

    Returns:
        Flask application instance
    """
    app = Flask(__name__)

    # Initialize configuration
    logger.info("📬 [INIT] Initializing PGP_NOTIFICATIONS...")
    config_manager = ConfigManager()
    config = config_manager.initialize_config()

    # Validate configuration
    if not config['bot_token']:
        logger.error("❌ [INIT] Bot token not available")
        raise RuntimeError("Bot token not available from Secret Manager")

    if not config['database_credentials']['instance_connection_name']:
        logger.error("❌ [INIT] Database credentials not available")
        raise RuntimeError("Database credentials not available from Secret Manager")

    # Initialize database manager (NEW_ARCHITECTURE pattern with SQLAlchemy + Cloud SQL Connector)
    db_manager = DatabaseManager(
        instance_connection_name=config['database_credentials']['instance_connection_name'],
        dbname=config['database_credentials']['dbname'],
        user=config['database_credentials']['user'],
        password=config['database_credentials']['password']
    )

    # Initialize Telegram client
    telegram_client = TelegramClient(bot_token=config['bot_token'])

    # Initialize notification handler
    notification_handler = NotificationHandler(
        db_manager=db_manager,
        telegram_client=telegram_client
    )

    # Store in app context
    app.config['notification_handler'] = notification_handler

    logger.info("✅ [INIT] PGP_NOTIFICATIONS initialized successfully")

    # ============== ROUTES ==============

    @app.route('/health', methods=['GET'])
    def health():
        """Health check endpoint for Cloud Run"""
        return jsonify({
            'status': 'healthy',
            'service': 'PGP_NOTIFICATIONS',
            'version': '1.0'
        }), 200

    @app.route('/send-notification', methods=['POST'])
    def send_notification():
        """
        Send payment notification to channel owner

        Request Body:
        {
            "open_channel_id": "-1003268562225",
            "payment_type": "subscription",  // or "donation"
            "payment_data": {
                "user_id": 6271402111,
                "username": "john_doe",
                "amount_crypto": "0.00034",
                "amount_usd": "9.99",
                "crypto_currency": "ETH",
                "tier": 1,                    // subscription only
                "tier_price": "9.99",         // subscription only
                "duration_days": 30,          // subscription only
                "timestamp": "2025-11-12 14:32:15 UTC"
            }
        }

        Response:
        {
            "status": "success",
            "message": "Notification sent successfully"
        }
        """
        try:
            # Validate request
            if not request.is_json:
                logger.warning("⚠️ [REQUEST] Non-JSON request received")
                abort(400, "Content-Type must be application/json")

            data = request.get_json()

            # Validate required fields
            required = ['open_channel_id', 'payment_type', 'payment_data']
            if not all(k in data for k in required):
                missing = [k for k in required if k not in data]
                logger.warning(f"⚠️ [REQUEST] Missing fields: {missing}")
                abort(400, f"Missing required fields: {missing}")

            # Extract data
            open_channel_id = data['open_channel_id']
            payment_type = data['payment_type']
            payment_data = data['payment_data']

            # Validate payment_type
            if payment_type not in ['subscription', 'donation']:
                logger.warning(f"⚠️ [REQUEST] Invalid payment_type: {payment_type}")
                abort(400, "payment_type must be 'subscription' or 'donation'")

            logger.info(f"📬 [REQUEST] Notification request received")
            logger.info(f"   Channel ID: {open_channel_id}")
            logger.info(f"   Payment Type: {payment_type}")

            # Process notification
            handler = app.config['notification_handler']
            success = handler.send_payment_notification(
                open_channel_id=open_channel_id,
                payment_type=payment_type,
                payment_data=payment_data
            )

            if success:
                logger.info("✅ [REQUEST] Notification sent successfully")
                return jsonify({
                    'status': 'success',
                    'message': 'Notification sent successfully'
                }), 200
            else:
                logger.warning("⚠️ [REQUEST] Notification failed (disabled or error)")
                return jsonify({
                    'status': 'failed',
                    'message': 'Notification not sent (disabled or error)'
                }), 200

        except Exception as e:
            logger.error(f"❌ [REQUEST] Unexpected error: {e}", exc_info=True)
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500

    @app.route('/test-notification', methods=['POST'])
    def test_notification():
        """
        Send a test notification

        Request Body:
        {
            "chat_id": 123456789,
            "channel_title": "Test Channel"
        }
        """
        try:
            data = request.get_json()

            if not data or 'chat_id' not in data:
                abort(400, "Missing 'chat_id' field")

            chat_id = data['chat_id']
            channel_title = data.get('channel_title', 'Test Channel')

            handler = app.config['notification_handler']
            success = handler.test_notification(
                chat_id=chat_id,
                channel_title=channel_title
            )

            if success:
                return jsonify({
                    'status': 'success',
                    'message': 'Test notification sent'
                }), 200
            else:
                return jsonify({
                    'status': 'failed',
                    'message': 'Test notification failed'
                }), 200

        except Exception as e:
            logger.error(f"❌ [TEST] Error: {e}", exc_info=True)
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"🌐 Starting server on port {port}...")
    app.run(host="0.0.0.0", port=port)
