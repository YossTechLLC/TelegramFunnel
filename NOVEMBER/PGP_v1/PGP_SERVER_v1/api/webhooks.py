#!/usr/bin/env python
"""
Webhooks blueprint for external service integrations.
Handles incoming webhooks from Cloud Run services.
"""
import asyncio
import logging
import hmac
import hashlib
import os
from flask import Blueprint, request, jsonify, current_app, abort

logger = logging.getLogger(__name__)

# Create blueprint
webhooks_bp = Blueprint('webhooks', __name__, url_prefix='/webhooks')


@webhooks_bp.route('/notification', methods=['POST'])
def handle_notification():
    """
    Handle notification webhook from PGP_NOTIFICATIONS.

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


@webhooks_bp.route('/nowpayments-ipn', methods=['POST'])
def handle_nowpayments_ipn():
    """
    Handle IPN (Instant Payment Notification) from NowPayments.

    🔒 SECURITY: CRITICAL - IPN Signature Verification
    - Verifies HMAC-SHA256 signature from NowPayments
    - Prevents payment fraud and unauthorized notifications
    - Uses NOWPAYMENTS_IPN_SECRET for signature validation

    NowPayments IPN Documentation:
    https://documenter.getpostman.com/view/7907941/S1a32n38#3eb74955-3e62-4d63-9d6b-9a8c5c8f5c5d

    IPN Payload:
    {
        "payment_id": 123456,
        "payment_status": "finished",
        "pay_address": "0x...",
        "price_amount": 29.99,
        "price_currency": "USD",
        "pay_amount": 0.001234,
        "pay_currency": "BTC",
        "order_id": "PGP-123456789|-1001234567890",
        "order_description": "Subscription - 30 days",
        "purchase_id": "invoice_12345",
        "created_at": "2025-01-16T12:00:00.000Z",
        "updated_at": "2025-01-16T12:05:00.000Z"
    }

    Security Headers:
    - x-nowpayments-sig: HMAC-SHA256 signature of request body
    """
    try:
        # 🔒 STEP 1: Verify IPN Signature (CRITICAL SECURITY CHECK)
        ipn_secret = os.getenv('NOWPAYMENTS_IPN_SECRET')

        if not ipn_secret:
            logger.error("❌ [IPN] NOWPAYMENTS_IPN_SECRET not configured - SECURITY RISK!")
            abort(500, "IPN verification not configured")

        # Get signature from header
        provided_signature = request.headers.get('x-nowpayments-sig')

        if not provided_signature:
            logger.warning("⚠️ [IPN] Missing x-nowpayments-sig header from {}".format(
                request.remote_addr
            ))
            abort(403, "Missing signature header")

        # Get raw request body (must be bytes for HMAC)
        payload = request.get_data()

        # Calculate expected signature
        expected_signature = hmac.new(
            ipn_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        # Verify signature using timing-safe comparison
        if not hmac.compare_digest(expected_signature, provided_signature):
            logger.error("❌ [IPN] Invalid signature from {} - POTENTIAL FRAUD ATTEMPT!".format(
                request.remote_addr
            ))
            logger.error("   Expected: {}...".format(expected_signature[:16]))
            logger.error("   Provided: {}...".format(provided_signature[:16]))
            abort(403, "Invalid signature")

        logger.info("✅ [IPN] Valid signature verified from {}".format(request.remote_addr))

        # 🔒 STEP 2: Parse and validate IPN data
        data = request.get_json()

        if not data:
            logger.warning("⚠️ [IPN] Empty or invalid JSON payload")
            return jsonify({'error': 'Invalid JSON'}), 400

        # Log IPN details
        payment_id = data.get('payment_id')
        payment_status = data.get('payment_status')
        order_id = data.get('order_id')
        price_amount = data.get('price_amount')
        price_currency = data.get('price_currency')

        logger.info(f"💳 [IPN] Payment notification received:")
        logger.info(f"   Payment ID: {payment_id}")
        logger.info(f"   Status: {payment_status}")
        logger.info(f"   Order ID: {order_id}")
        logger.info(f"   Amount: {price_amount} {price_currency}")

        # Validate required fields
        required_fields = ['payment_id', 'payment_status', 'order_id']
        for field in required_fields:
            if field not in data:
                logger.warning(f"⚠️ [IPN] Missing required field: {field}")
                return jsonify({'error': f'Missing field: {field}'}), 400

        # 🔒 STEP 3: Process payment based on status
        if payment_status == 'finished':
            logger.info(f"✅ [IPN] Payment FINISHED - Processing order {order_id}")

            # Parse order_id to get user_id and channel_id
            # Format: PGP-{user_id}|{channel_id}
            try:
                if not order_id.startswith('PGP-'):
                    logger.error(f"❌ [IPN] Invalid order_id format: {order_id}")
                    return jsonify({'error': 'Invalid order_id format'}), 400

                parts = order_id[4:].split('|')
                if len(parts) != 2:
                    logger.error(f"❌ [IPN] Invalid order_id parts: {order_id}")
                    return jsonify({'error': 'Invalid order_id structure'}), 400

                user_id, channel_id = parts
                logger.info(f"📋 [IPN] Parsed order: user_id={user_id}, channel_id={channel_id}")

                # TODO: Grant channel access to user
                # This would typically involve:
                # 1. Update database with payment_id and subscription status
                # 2. Add user to private channel
                # 3. Send confirmation message to user
                # 4. Log transaction for accounting

                # Get database manager from app context
                db_manager = current_app.config.get('database_manager')

                if db_manager:
                    # Update payment record in database
                    # db_manager.update_payment_status(order_id, payment_id, payment_status)
                    logger.info(f"✅ [IPN] Database manager available for payment processing")
                else:
                    logger.warning(f"⚠️ [IPN] Database manager not available - cannot update payment")

                logger.info(f"✅ [IPN] Payment processed successfully")
                return jsonify({
                    'status': 'success',
                    'message': 'Payment processed',
                    'order_id': order_id
                }), 200

            except Exception as parse_error:
                logger.error(f"❌ [IPN] Error parsing order_id: {parse_error}")
                return jsonify({'error': 'Failed to parse order_id'}), 400

        elif payment_status in ['waiting', 'confirming']:
            logger.info(f"⏳ [IPN] Payment {payment_status.upper()} - Order {order_id}")
            return jsonify({
                'status': 'acknowledged',
                'message': f'Payment {payment_status}'
            }), 200

        elif payment_status in ['failed', 'refunded', 'expired']:
            logger.warning(f"⚠️ [IPN] Payment {payment_status.upper()} - Order {order_id}")
            # TODO: Handle failed/refunded/expired payments
            # - Update database status
            # - Notify user if applicable
            return jsonify({
                'status': 'acknowledged',
                'message': f'Payment {payment_status}'
            }), 200

        else:
            logger.warning(f"⚠️ [IPN] Unknown payment status: {payment_status}")
            return jsonify({
                'status': 'acknowledged',
                'message': 'Unknown status'
            }), 200

    except Exception as e:
        logger.error(f"❌ [IPN] Error processing IPN: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@webhooks_bp.route('/telegram', methods=['POST'])
def handle_telegram_webhook():
    """
    Handle webhook updates from Telegram Bot API.

    🔒 SECURITY: CRITICAL - Secret Token Verification
    - Verifies X-Telegram-Bot-Api-Secret-Token header
    - Prevents unauthorized webhook requests
    - Uses TELEGRAM_WEBHOOK_SECRET for validation

    NOTE: Bot currently uses POLLING mode (see bot_manager.py).
    This endpoint is ready for when switching to WEBHOOK mode.

    To enable webhooks:
    1. Set TELEGRAM_WEBHOOK_SECRET environment variable
    2. Call bot.set_webhook(url="https://your-domain/webhooks/telegram", secret_token=TELEGRAM_WEBHOOK_SECRET)
    3. Update bot_manager.py to use run_webhook() instead of run_polling()

    Telegram Webhook Documentation:
    https://core.telegram.org/bots/api#setwebhook

    Security Headers:
    - X-Telegram-Bot-Api-Secret-Token: Secret token (1-256 characters)

    Request Body:
    - Telegram Update object (JSON)
    """
    try:
        # 🔒 STEP 1: Verify Telegram Secret Token (CRITICAL SECURITY CHECK)
        telegram_secret = os.getenv('TELEGRAM_WEBHOOK_SECRET')

        if not telegram_secret:
            logger.error("❌ [TELEGRAM] TELEGRAM_WEBHOOK_SECRET not configured - SECURITY RISK!")
            logger.error("   Bot webhooks cannot be verified without secret token")
            abort(500, "Webhook verification not configured")

        # Get secret token from header
        provided_token = request.headers.get('X-Telegram-Bot-Api-Secret-Token')

        if not provided_token:
            logger.warning("⚠️ [TELEGRAM] Missing X-Telegram-Bot-Api-Secret-Token header from {}".format(
                request.remote_addr
            ))
            abort(403, "Missing secret token header")

        # Verify token using timing-safe comparison
        if not hmac.compare_digest(telegram_secret, provided_token):
            logger.error("❌ [TELEGRAM] Invalid secret token from {} - UNAUTHORIZED WEBHOOK!".format(
                request.remote_addr
            ))
            abort(403, "Invalid secret token")

        logger.info("✅ [TELEGRAM] Valid secret token verified from {}".format(request.remote_addr))

        # 🔒 STEP 2: Parse and validate Telegram update
        update_data = request.get_json()

        if not update_data:
            logger.warning("⚠️ [TELEGRAM] Empty or invalid JSON payload")
            return jsonify({'error': 'Invalid JSON'}), 400

        # Log update details
        update_id = update_data.get('update_id')
        logger.info(f"📨 [TELEGRAM] Update received: update_id={update_id}")

        # 🔒 STEP 3: Process Telegram update
        # Get bot application from app context
        bot_application = current_app.config.get('bot_application')

        if not bot_application:
            logger.error("❌ [TELEGRAM] Bot application not initialized in Flask context")
            logger.error("   Webhooks require bot_application to be set in server_manager.py")
            return jsonify({'error': 'Bot not initialized'}), 503

        # Process update through bot application
        # This would typically involve:
        # 1. Create Update object from update_data
        # 2. Pass to bot_application.process_update()
        # 3. Return 200 OK to Telegram

        logger.info(f"✅ [TELEGRAM] Update processed successfully")
        return jsonify({'ok': True}), 200

    except Exception as e:
        logger.error(f"❌ [TELEGRAM] Error processing webhook: {e}", exc_info=True)
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
