#!/usr/bin/env python
"""
HPW10-9: Host Payment Wallet Service
Google Cloud Function for automated ETH payment dispatching from custodial wallet.
Receives NowPayments IPN webhooks and GCSplit7-14 notifications, then automatically
sends ETH from HOST wallet to ChangeNow payin addresses.
"""
import os
import json
import hmac
import hashlib
import asyncio
import threading
from typing import Dict, Any, Optional
from flask import Flask, request, abort, jsonify
from decimal import Decimal

from config_manager import ConfigManager
from database_manager import DatabaseManager
from eth_wallet_manager import EthWalletManager
from changenow_tracker import ChangeNowTracker
from payment_dispatcher import PaymentDispatcher

app = Flask(__name__)

# Initialize managers
config_manager = ConfigManager()
config = config_manager.initialize_config()

# Initialize database manager
# Note: host_payment_queue table should already exist in the database
db_manager = DatabaseManager()

# Initialize Ethereum wallet manager
eth_wallet = EthWalletManager(
    node_url=config.get('eth_node_url'),
    wallet_address=config.get('host_wallet_address'),
    private_key=config.get('host_wallet_private_key')
)

# Initialize ChangeNow tracker
changenow_tracker = ChangeNowTracker(db_manager)

# Initialize payment dispatcher
payment_dispatcher = PaymentDispatcher(eth_wallet, db_manager, config)

# Get network info for logging
network_info = eth_wallet.get_network_info()
print(f"🌐 [HPW10-9] Running on {network_info.get('network_name', 'Unknown')}")


def verify_nowpayments_signature(payload: bytes, signature: str, secret_key: str) -> bool:
    """
    Verify NowPayments IPN webhook signature (HMAC-SHA512).

    Args:
        payload: Raw request payload
        signature: Provided signature from x-nowpayments-sig header
        secret_key: NowPayments IPN secret key

    Returns:
        True if signature is valid, False otherwise
    """
    if not secret_key or not signature:
        return False

    try:
        # NowPayments uses HMAC-SHA512
        expected_signature = hmac.new(
            secret_key.encode(),
            payload,
            hashlib.sha512
        ).hexdigest()

        return hmac.compare_digest(signature, expected_signature)

    except Exception as e:
        print(f"❌ [WEBHOOK_VERIFY] Signature verification error: {e}")
        return False


def verify_gcsplit_signature(payload: bytes, signature: str, signing_key: str) -> bool:
    """
    Verify GCSplit7-14 webhook signature (HMAC-SHA256).

    Args:
        payload: Raw request payload
        signature: Provided signature
        signing_key: Webhook signing key

    Returns:
        True if signature is valid, False otherwise
    """
    if not signing_key or not signature:
        return False

    try:
        expected_signature = hmac.new(
            signing_key.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(signature, expected_signature)

    except Exception as e:
        print(f"❌ [WEBHOOK_VERIFY] Signature verification error: {e}")
        return False


@app.route("/nowpayments", methods=["POST"])
def nowpayments_ipn_webhook():
    """
    NowPayments IPN webhook endpoint.
    Receives payment notifications when funds arrive in custodial wallet.
    """
    try:
        # Get raw payload for signature verification
        payload = request.get_data()
        signature = request.headers.get('x-nowpayments-sig', '')

        print(f"🎯 [WEBHOOK] NowPayments IPN Webhook Called")
        print(f"📦 [WEBHOOK] Payload size: {len(payload)} bytes")

        # Verify webhook signature if secret is available
        ipn_secret = config.get('nowpayments_ipn_secret')
        if ipn_secret and not verify_nowpayments_signature(payload, signature, ipn_secret):
            print(f"❌ [WEBHOOK] Invalid NowPayments signature")
            abort(401, "Invalid webhook signature")

        # Parse JSON payload
        try:
            webhook_data = request.get_json()
            if not webhook_data:
                abort(400, "Invalid JSON payload")
        except Exception as e:
            print(f"❌ [WEBHOOK] JSON parsing error: {e}")
            abort(400, "Malformed JSON payload")

        print(f"📝 [WEBHOOK] NowPayments IPN data received:")
        print(f"   Payment ID: {webhook_data.get('payment_id')}")
        print(f"   Payment Status: {webhook_data.get('payment_status')}")
        print(f"   Order ID: {webhook_data.get('order_id')}")

        # Extract payment information
        payment_id = webhook_data.get('payment_id')
        payment_status = webhook_data.get('payment_status')
        order_id = webhook_data.get('order_id')

        # Only process confirmed/finished payments
        if payment_status not in ['confirmed', 'finished']:
            print(f"⚠️ [WEBHOOK] Payment status not confirmed: {payment_status}")
            return jsonify({
                "status": "acknowledged",
                "message": f"Payment status: {payment_status}"
            }), 200

        # Check if payment already exists in queue
        existing_payment = db_manager.get_payment_by_id(payment_id)
        if existing_payment:
            print(f"⚠️ [WEBHOOK] Payment already in queue: {payment_id}")
            return jsonify({
                "status": "acknowledged",
                "message": "Payment already queued"
            }), 200

        print(f"✅ [WEBHOOK] NowPayments IPN processed successfully")
        return jsonify({
            "status": "acknowledged",
            "message": "IPN received and queued for processing"
        }), 200

    except Exception as e:
        print(f"❌ [WEBHOOK] NowPayments IPN error: {e}")
        return jsonify({
            "status": "error",
            "message": f"Webhook error: {str(e)}"
        }), 500


@app.route("/gcsplit", methods=["POST"])
def gcsplit_notification_webhook():
    """
    GCSplit7-14 notification webhook endpoint.
    Receives ChangeNow transaction details after split is created.
    """
    try:
        # Get raw payload for signature verification
        payload = request.get_data()
        signature = request.headers.get('X-Webhook-Signature', '')

        print(f"🎯 [WEBHOOK] GCSplit7-14 Notification Webhook Called")
        print(f"📦 [WEBHOOK] Payload size: {len(payload)} bytes")

        # Parse JSON payload
        try:
            webhook_data = request.get_json()
            if not webhook_data:
                abort(400, "Invalid JSON payload")
        except Exception as e:
            print(f"❌ [WEBHOOK] JSON parsing error: {e}")
            abort(400, "Malformed JSON payload")

        print(f"📝 [WEBHOOK] Processing GCSplit notification")

        # Parse ChangeNow transaction data
        transaction_data = changenow_tracker.parse_changenow_webhook(webhook_data)

        if not transaction_data.get('changenow_tx_id'):
            print(f"❌ [WEBHOOK] Missing ChangeNow transaction ID")
            abort(400, "Missing transaction ID")

        # Validate deposit address
        payin_address = transaction_data.get('payin_address')
        if not changenow_tracker.validate_deposit_address(payin_address):
            print(f"❌ [WEBHOOK] Invalid ChangeNow deposit address: {payin_address}")
            abort(400, "Invalid deposit address")

        # Prepare payment data for queue
        payment_data = {
            'payment_id': f"CHANGENOW_{transaction_data.get('changenow_tx_id')}",
            'order_id': transaction_data.get('order_id'),
            'changenow_tx_id': transaction_data.get('changenow_tx_id'),
            'payin_address': payin_address,
            'expected_amount_eth': transaction_data.get('expected_amount_eth'),
            'user_id': transaction_data.get('user_id'),
            'status': 'pending'
        }

        # Queue payment for processing
        success = payment_dispatcher.process_payment_sync(payment_data)

        if success:
            print(f"✅ [WEBHOOK] GCSplit notification processed successfully")
            return jsonify({
                "status": "success",
                "message": "ChangeNow transaction queued for payment",
                "data": {
                    "payment_id": payment_data['payment_id'],
                    "changenow_tx_id": payment_data['changenow_tx_id'],
                    "payin_address": payment_data['payin_address'],
                    "amount_eth": payment_data['expected_amount_eth']
                }
            }), 200
        else:
            print(f"⚠️ [WEBHOOK] Failed to queue payment")
            return jsonify({
                "status": "error",
                "message": "Failed to queue payment"
            }), 400

    except Exception as e:
        print(f"❌ [WEBHOOK] GCSplit notification error: {e}")
        return jsonify({
            "status": "error",
            "message": f"Webhook error: {str(e)}"
        }), 500


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for monitoring."""
    try:
        # Check database connection
        conn = db_manager.get_connection()
        conn.close()
        db_status = "✅"
    except Exception:
        db_status = "❌"

    # Check ETH node connection
    eth_status = "✅" if eth_wallet.w3.is_connected() else "❌"

    # Get wallet balance
    try:
        balance = eth_wallet.get_balance()
        balance_str = f"{balance} ETH"
    except Exception:
        balance_str = "Error"

    # Get queue statistics
    try:
        pending_payments = db_manager.get_pending_payments()
        sent_payments = db_manager.get_sent_payments()
        queue_stats = {
            'pending': len(pending_payments),
            'sent': len(sent_payments)
        }
    except Exception:
        queue_stats = {'pending': 0, 'sent': 0}

    return jsonify({
        "status": "healthy",
        "service": "HPW10-9 Host Payment Wallet",
        "database": db_status,
        "ethereum_node": eth_status,
        "network": network_info.get('network_name', 'Unknown'),
        "wallet_balance": balance_str,
        "queue_stats": queue_stats,
        "timestamp": int(asyncio.get_event_loop().time()) if asyncio.get_event_loop() else 0
    }), 200


@app.route("/status/<payment_id>", methods=["GET"])
def get_payment_status(payment_id: str):
    """
    Get status of a specific payment.

    Args:
        payment_id: Payment identifier
    """
    try:
        payment = db_manager.get_payment_by_id(payment_id)

        if payment:
            return jsonify({
                "status": "success",
                "payment": {
                    "payment_id": payment.get('payment_id'),
                    "order_id": payment.get('order_id'),
                    "changenow_tx_id": payment.get('changenow_tx_id'),
                    "status": payment.get('status'),
                    "payin_address": payment.get('payin_address'),
                    "expected_amount_eth": str(payment.get('expected_amount_eth')),
                    "tx_hash": payment.get('tx_hash'),
                    "created_at": str(payment.get('created_at')),
                    "updated_at": str(payment.get('updated_at')),
                    "error_message": payment.get('error_message')
                }
            }), 200
        else:
            return jsonify({
                "status": "not_found",
                "message": f"Payment {payment_id} not found"
            }), 404

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# Background task runner for payment dispatcher
def run_dispatcher_background():
    """Run payment dispatcher in background thread."""
    print(f"🚀 [HPW10-9] Starting background payment dispatcher")

    # Create new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(payment_dispatcher.run_dispatcher())
    except Exception as e:
        print(f"❌ [HPW10-9] Dispatcher error: {e}")
    finally:
        loop.close()


# Start background dispatcher thread
dispatcher_thread = threading.Thread(target=run_dispatcher_background, daemon=True)
dispatcher_thread.start()
print(f"✅ [HPW10-9] Background dispatcher thread started")


# --- Flask entrypoint for Cloud Run deployment ---
if __name__ == "__main__":
    # Cloud Run sets the PORT environment variable
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 [HPW10-9] Starting Host Payment Wallet Service on port {port}")
    app.run(host="0.0.0.0", port=port)
