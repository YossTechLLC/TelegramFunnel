#!/usr/bin/env python
"""
Webhooks blueprint for external service integrations.
Handles incoming webhooks from Cloud Run services.
"""
import asyncio
import logging
from flask import Blueprint, request, jsonify, current_app

logger = logging.getLogger(__name__)

# Create blueprint
webhooks_bp = Blueprint('webhooks', __name__, url_prefix='/webhooks')


@webhooks_bp.route('/notification', methods=['POST'])
def handle_notification():
    """
    Handle notification webhook from GCNotificationService.

    Security: Applied by server_manager middleware
    - HMAC signature verification
    - IP whitelist
    - Rate limiting

    Request Body:
    {
        "open_channel_id": "-1003268562225",
        "payment_type": "subscription",
        "payment_data": {...}
    }
    """
    try:
        data = request.get_json()

        logger.info(f"📬 [WEBHOOK] Notification received for channel {data.get('open_channel_id')}")

        # Validate required fields
        required_fields = ['open_channel_id', 'payment_type', 'payment_data']
        for field in required_fields:
            if field not in data:
                logger.warning(f"⚠️ [WEBHOOK] Missing field: {field}")
                return jsonify({'error': f'Missing field: {field}'}), 400

        # Get notification service from app context
        notification_service = current_app.config.get('notification_service')

        if not notification_service:
            logger.error("❌ [WEBHOOK] Notification service not initialized")
            return jsonify({'error': 'Notification service not available'}), 503

        # Send notification asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        success = loop.run_until_complete(
            notification_service.send_payment_notification(
                open_channel_id=data['open_channel_id'],
                payment_type=data['payment_type'],
                payment_data=data['payment_data']
            )
        )

        loop.close()

        if success:
            logger.info(f"✅ [WEBHOOK] Notification sent successfully")
            return jsonify({
                'status': 'success',
                'message': 'Notification sent'
            }), 200
        else:
            logger.warning(f"⚠️ [WEBHOOK] Notification failed")
            return jsonify({
                'status': 'failed',
                'message': 'Notification not sent'
            }), 200

    except Exception as e:
        logger.error(f"❌ [WEBHOOK] Error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@webhooks_bp.route('/broadcast-trigger', methods=['POST'])
def handle_broadcast_trigger():
    """
    Handle broadcast trigger from GCBroadcastService (future).

    This endpoint can be used to trigger broadcast actions
    directly on the bot instance.
    """
    # Future implementation
    return jsonify({'status': 'not_implemented'}), 501
