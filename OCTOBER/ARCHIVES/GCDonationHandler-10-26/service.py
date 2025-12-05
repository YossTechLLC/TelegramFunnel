#!/usr/bin/env python
"""
GCDonationHandler Flask Service
Cloud Run webhook service for donation handling

This is the main entry point for the GCDonationHandler service.
It initializes all modules and provides REST API endpoints.
"""

import logging
from flask import Flask, request, jsonify

# Import all internal modules
from config_manager import ConfigManager
from database_manager import DatabaseManager
from telegram_client import TelegramClient
from keypad_handler import KeypadHandler
from keypad_state_manager import KeypadStateManager
from broadcast_manager import BroadcastManager

# Configure logging with emoji support
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app():
    """
    Application factory for GCDonationHandler Flask app.

    Initializes all service components and configures routes.

    Returns:
        Flask app instance

    Raises:
        RuntimeError: If critical configuration is missing
    """
    logger.info("🚀 Starting GCDonationHandler service...")

    app = Flask(__name__)

    # Initialize configuration
    try:
        config_manager = ConfigManager()
        config = config_manager.initialize_config()
        logger.info("🔧 Configuration loaded successfully")
    except Exception as e:
        logger.error(f"❌ Failed to load configuration: {e}")
        raise RuntimeError(f"Configuration initialization failed: {e}")

    # Validate bot token
    bot_token = config.get('bot_token')
    if not bot_token:
        raise RuntimeError("Bot token not available - cannot start service")

    # Initialize database manager
    try:
        db_manager = DatabaseManager(
            db_host=config['db_host'],
            db_port=config['db_port'],
            db_name=config['db_name'],
            db_user=config['db_user'],
            db_password=config['db_password']
        )
        logger.info("🗄️ Database manager initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database manager: {e}")
        raise RuntimeError(f"Database initialization failed: {e}")

    # Initialize Telegram client
    try:
        telegram_client = TelegramClient(bot_token=bot_token)
        logger.info("📱 Telegram client initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Telegram client: {e}")
        raise RuntimeError(f"Telegram client initialization failed: {e}")

    # Initialize keypad state manager (database-backed state)
    try:
        state_manager = KeypadStateManager(db_manager=db_manager)
        logger.info("🗄️ Keypad state manager initialized (database-backed)")
    except Exception as e:
        logger.error(f"❌ Failed to initialize keypad state manager: {e}")
        raise RuntimeError(f"Keypad state manager initialization failed: {e}")

    # Initialize keypad handler
    try:
        keypad_handler = KeypadHandler(
            db_manager=db_manager,
            telegram_client=telegram_client,
            payment_token=config['payment_token'],
            ipn_callback_url=config['ipn_callback_url'],
            state_manager=state_manager
        )
        logger.info("🔢 Keypad handler initialized (with database-backed state)")
    except Exception as e:
        logger.error(f"❌ Failed to initialize keypad handler: {e}")
        raise RuntimeError(f"Keypad handler initialization failed: {e}")

    # Initialize broadcast manager
    try:
        broadcast_manager = BroadcastManager(
            db_manager=db_manager,
            telegram_client=telegram_client
        )
        logger.info("📢 Broadcast manager initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize broadcast manager: {e}")
        raise RuntimeError(f"Broadcast manager initialization failed: {e}")

    # Store managers in app context for access in routes
    app.db_manager = db_manager
    app.telegram_client = telegram_client
    app.keypad_handler = keypad_handler
    app.broadcast_manager = broadcast_manager

    logger.info("✅ All service components initialized successfully")

    # ==========================
    # API ENDPOINTS
    # ==========================

    @app.route("/health", methods=["GET"])
    def health_check():
        """
        Health check endpoint.

        Returns:
            JSON response with service status
        """
        return jsonify({
            "status": "healthy",
            "service": "GCDonationHandler",
            "version": "1.0"
        }), 200

    @app.route("/start-donation-input", methods=["POST"])
    def start_donation_input():
        """
        Start donation input flow - send keypad to user.

        Request Body:
            {
                "user_id": int,
                "chat_id": int,
                "open_channel_id": str,
                "callback_query_id": str
            }

        Returns:
            JSON response with result
        """
        try:
            # Parse request body
            data = request.get_json()

            if not data:
                logger.error("❌ No JSON body in request")
                return jsonify({"error": "No JSON body provided"}), 400

            # Validate required fields
            required_fields = ["user_id", "chat_id", "open_channel_id", "callback_query_id"]
            missing_fields = [field for field in required_fields if field not in data]

            if missing_fields:
                logger.error(f"❌ Missing required fields: {missing_fields}")
                return jsonify({"error": f"Missing fields: {', '.join(missing_fields)}"}), 400

            user_id = data["user_id"]
            chat_id = data["chat_id"]
            open_channel_id = data["open_channel_id"]
            callback_query_id = data["callback_query_id"]

            logger.info(f"💝 Start donation input: user_id={user_id}, channel={open_channel_id}")

            # Validate channel exists
            if not app.db_manager.channel_exists(open_channel_id):
                logger.warning(f"⚠️ Invalid channel ID: {open_channel_id}")
                return jsonify({"error": "Invalid channel ID"}), 400

            # Start donation input
            result = app.keypad_handler.start_donation_input(
                user_id=user_id,
                chat_id=chat_id,
                open_channel_id=open_channel_id,
                callback_query_id=callback_query_id
            )

            if result['success']:
                logger.info(f"✅ Donation input started for user {user_id}")
                return jsonify(result), 200
            else:
                logger.error(f"❌ Failed to start donation input: {result.get('error')}")
                return jsonify(result), 500

        except Exception as e:
            logger.error(f"❌ Error in start_donation_input endpoint: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/keypad-input", methods=["POST"])
    def keypad_input():
        """
        Handle keypad button press.

        Request Body:
            {
                "user_id": int,
                "callback_data": str,
                "callback_query_id": str,
                "message_id": int (optional),
                "chat_id": int (optional)
            }

        Returns:
            JSON response with result
        """
        try:
            # Parse request body
            data = request.get_json()

            if not data:
                logger.error("❌ No JSON body in request")
                return jsonify({"error": "No JSON body provided"}), 400

            # Validate required fields
            required_fields = ["user_id", "callback_data", "callback_query_id"]
            missing_fields = [field for field in required_fields if field not in data]

            if missing_fields:
                logger.error(f"❌ Missing required fields: {missing_fields}")
                return jsonify({"error": f"Missing fields: {', '.join(missing_fields)}"}), 400

            user_id = data["user_id"]
            callback_data = data["callback_data"]
            callback_query_id = data["callback_query_id"]
            message_id = data.get("message_id")
            chat_id = data.get("chat_id")

            logger.info(f"🔢 Keypad input: user_id={user_id}, callback_data={callback_data}")

            # Handle keypad input
            result = app.keypad_handler.handle_keypad_input(
                user_id=user_id,
                callback_data=callback_data,
                callback_query_id=callback_query_id,
                message_id=message_id,
                chat_id=chat_id
            )

            if result['success']:
                logger.info(f"✅ Keypad input handled for user {user_id}")
                return jsonify(result), 200
            else:
                logger.warning(f"⚠️ Keypad input handling issue: {result.get('error')}")
                return jsonify(result), 200  # Still return 200 for validation errors

        except Exception as e:
            logger.error(f"❌ Error in keypad_input endpoint: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/broadcast-closed-channels", methods=["POST"])
    def broadcast_closed_channels():
        """
        Broadcast donation button to all closed channels.

        Request Body (optional):
            {
                "force_resend": bool
            }

        Returns:
            JSON response with broadcast statistics
        """
        try:
            # Parse request body (optional)
            data = request.get_json() or {}

            force_resend = data.get("force_resend", False)

            logger.info(f"📢 Broadcasting to closed channels (force_resend={force_resend})")

            # Execute broadcast
            result = app.broadcast_manager.broadcast_to_closed_channels(force_resend=force_resend)

            logger.info(f"✅ Broadcast complete: {result['successful']}/{result['total_channels']} successful")

            return jsonify(result), 200

        except Exception as e:
            logger.error(f"❌ Error in broadcast_closed_channels endpoint: {e}")
            return jsonify({"error": str(e)}), 500

    logger.info("🚀 GCDonationHandler service ready")

    return app


# Create app instance at module level for gunicorn
app = create_app()


if __name__ == "__main__":
    # For local development only
    # In production, use gunicorn: gunicorn service:app
    app.run(host="0.0.0.0", port=8080, debug=False)
