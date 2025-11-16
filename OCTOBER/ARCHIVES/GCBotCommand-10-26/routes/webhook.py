#!/usr/bin/env python
"""
Webhook routes for GCBotCommand
Handles Telegram update webhooks and health checks
"""
from flask import Blueprint, request, jsonify, current_app
import logging

logger = logging.getLogger(__name__)

webhook_bp = Blueprint('webhook', __name__)

@webhook_bp.route('/webhook', methods=['POST'])
def handle_webhook():
    """
    Receive Telegram updates via webhook

    Expected format from Telegram:
    {
        "update_id": 123456789,
        "message": {...} or "callback_query": {...}
    }
    """
    try:
        data = request.get_json()

        if not data:
            logger.warning("⚠️ Received empty webhook payload")
            return jsonify({"status": "error", "message": "Empty payload"}), 400

        logger.info(f"📨 Received update_id: {data.get('update_id')}")

        # Import handlers here to avoid circular imports
        from handlers.command_handler import CommandHandler
        from handlers.callback_handler import CallbackHandler

        # Get handlers
        command_handler = CommandHandler(current_app.db, current_app.config)
        callback_handler = CallbackHandler(current_app.db, current_app.config)

        # Route based on update type
        if 'message' in data:
            # Handle text messages and commands
            message = data['message']

            # Check if message has text
            if 'text' in message:
                text = message['text']

                # Handle commands
                if text.startswith('/start'):
                    result = command_handler.handle_start_command(data)
                    return jsonify(result), 200

                elif text.startswith('/database'):
                    result = command_handler.handle_database_command(data)
                    return jsonify(result), 200

                else:
                    # Handle conversation input (ongoing database editing, etc.)
                    result = command_handler.handle_text_input(data)
                    return jsonify(result), 200
            else:
                logger.info("ℹ️ Non-text message received (photo, document, etc.)")
                return jsonify({"status": "ok", "message": "Non-text message"}), 200

        elif 'callback_query' in data:
            # Handle button callback queries
            result = callback_handler.handle_callback(data)
            return jsonify(result), 200

        else:
            logger.warning("⚠️ Unknown update type")
            return jsonify({"status": "ok", "message": "Unknown update type"}), 200

    except Exception as e:
        logger.error(f"❌ Error handling webhook: {e}")
        import traceback
        traceback.print_exc()
        # Return 200 to prevent Telegram from retrying
        return jsonify({"status": "error", "message": str(e)}), 200

@webhook_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Cloud Run"""
    try:
        # Test database connection
        with current_app.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()

        return jsonify({
            "status": "healthy",
            "service": "GCBotCommand-10-26",
            "database": "connected"
        }), 200
    except Exception as e:
        logger.error(f"❌ Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "service": "GCBotCommand-10-26",
            "error": str(e)
        }), 503

@webhook_bp.route('/set-webhook', methods=['POST'])
def set_webhook():
    """
    Helper endpoint to set Telegram webhook
    Only call this once during initial deployment
    """
    try:
        bot_token = current_app.config['bot_token']

        # Get webhook URL from request or construct from service URL
        data = request.get_json() or {}
        webhook_url = data.get('webhook_url')

        if not webhook_url:
            return jsonify({"error": "webhook_url required"}), 400

        # Call Telegram setWebhook API
        import requests
        response = requests.post(
            f"https://api.telegram.org/bot{bot_token}/setWebhook",
            json={"url": webhook_url}
        )

        result = response.json()
        logger.info(f"✅ Webhook set: {result}")

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"❌ Error setting webhook: {e}")
        return jsonify({"error": str(e)}), 500
