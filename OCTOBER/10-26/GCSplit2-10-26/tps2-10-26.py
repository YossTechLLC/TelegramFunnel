#!/usr/bin/env python
"""
GCSplit2-10-26: USDT→ETH Estimator Service
Receives encrypted tokens from GCSplit1, calls ChangeNow API for USDT→ETH estimates,
and returns encrypted responses back to GCSplit1 via Cloud Tasks.
Implements infinite retry logic for resilience against API failures.
"""
import time
from decimal import Decimal
from datetime import datetime
from typing import Dict, Any
from flask import Flask, request, abort, jsonify

# Import service modules
from config_manager import ConfigManager
from token_manager import TokenManager
from cloudtasks_client import CloudTasksClient
from changenow_client import ChangeNowClient

app = Flask(__name__)

# Initialize managers
print(f"🚀 [APP] Initializing GCSplit2-10-26 USDT→ETH Estimator Service")
config_manager = ConfigManager()
config = config_manager.initialize_config()

# Initialize token manager
try:
    signing_key = config.get('success_url_signing_key')
    if not signing_key:
        raise ValueError("SUCCESS_URL_SIGNING_KEY not available")
    token_manager = TokenManager(signing_key)
    print(f"✅ [APP] Token manager initialized")
except Exception as e:
    print(f"❌ [APP] Failed to initialize token manager: {e}")
    token_manager = None

# Initialize Cloud Tasks client
try:
    project_id = config.get('cloud_tasks_project_id')
    location = config.get('cloud_tasks_location')
    if not project_id or not location:
        raise ValueError("Cloud Tasks configuration incomplete")
    cloudtasks_client = CloudTasksClient(project_id, location)
    print(f"✅ [APP] Cloud Tasks client initialized")
except Exception as e:
    print(f"❌ [APP] Failed to initialize Cloud Tasks client: {e}")
    cloudtasks_client = None

# Initialize ChangeNow client
try:
    api_key = config.get('changenow_api_key')
    if not api_key:
        raise ValueError("CHANGENOW_API_KEY not available")
    changenow_client = ChangeNowClient(api_key)
    print(f"✅ [APP] ChangeNow client initialized")
except Exception as e:
    print(f"❌ [APP] Failed to initialize ChangeNow client: {e}")
    changenow_client = None


# ============================================================================
# MAIN ENDPOINT: POST / - Receives request from GCSplit1
# ============================================================================

@app.route("/", methods=["POST"])
def process_usdt_eth_estimate():
    """
    Main endpoint for processing USDT→ETH estimate requests from GCSplit1.

    Flow:
    1. Decrypt token from GCSplit1
    2. Call ChangeNow API v2 for USDT→ETH estimate (with infinite retry)
    3. Encrypt response token
    4. Enqueue Cloud Task back to GCSplit1

    Returns:
        JSON response with status
    """
    try:
        print(f"🎯 [ENDPOINT] USDT→ETH estimate request received (from GCSplit1)")

        # Parse JSON payload
        try:
            request_data = request.get_json()
            if not request_data:
                abort(400, "Invalid JSON payload")
        except Exception as e:
            print(f"❌ [ENDPOINT] JSON parsing error: {e}")
            abort(400, "Malformed JSON payload")

        encrypted_token = request_data.get('token')
        if not encrypted_token:
            print(f"❌ [ENDPOINT] Missing token")
            abort(400, "Missing token")

        # Decrypt token
        if not token_manager:
            print(f"❌ [ENDPOINT] Token manager not available")
            abort(500, "Service configuration error")

        decrypted_data = token_manager.decrypt_gcsplit1_to_gcsplit2_token(encrypted_token)
        if not decrypted_data:
            print(f"❌ [ENDPOINT] Failed to decrypt token")
            abort(401, "Invalid token")

        # Extract data
        user_id = decrypted_data['user_id']
        closed_channel_id = decrypted_data['closed_channel_id']
        wallet_address = decrypted_data['wallet_address']
        payout_currency = decrypted_data['payout_currency']
        payout_network = decrypted_data['payout_network']
        adjusted_amount_usdt = decrypted_data['adjusted_amount_usdt']

        print(f"👤 [ENDPOINT] User ID: {user_id}")
        print(f"🏦 [ENDPOINT] Wallet: {wallet_address}")
        print(f"💰 [ENDPOINT] Amount: {adjusted_amount_usdt} USDT")
        print(f"🎯 [ENDPOINT] Target: {payout_currency.upper()} on {payout_network.upper()}")

        # Call ChangeNow API with infinite retry
        if not changenow_client:
            print(f"❌ [ENDPOINT] ChangeNow client not available")
            abort(500, "ChangeNow client unavailable")

        print(f"🌐 [ENDPOINT] Calling ChangeNow API for USDT→ETH estimate (with retry)")

        estimate_response = changenow_client.get_estimated_amount_v2_with_retry(
            from_currency="usdt",
            to_currency="eth",
            from_network="eth",
            to_network="eth",
            from_amount=str(adjusted_amount_usdt),
            flow="standard",
            type_="direct"
        )

        # Note: estimate_response will always return (or timeout after 24h)
        # due to infinite retry in ChangeNowClient
        if not estimate_response:
            # This should never happen due to infinite retry, but handle it anyway
            print(f"❌ [ENDPOINT] ChangeNow API returned None (should not happen)")
            abort(500, "ChangeNow API failure")

        # Extract estimate data
        from_amount = estimate_response.get('fromAmount')
        to_amount = estimate_response.get('toAmount')
        deposit_fee = estimate_response.get('depositFee', 0)
        withdrawal_fee = estimate_response.get('withdrawalFee', 0)

        print(f"✅ [ENDPOINT] ChangeNow estimate received")
        print(f"💰 [ENDPOINT] From: {from_amount} USDT")
        print(f"💰 [ENDPOINT] To: {to_amount} ETH (post-fee)")
        print(f"📊 [ENDPOINT] Deposit fee: {deposit_fee}")
        print(f"📊 [ENDPOINT] Withdrawal fee: {withdrawal_fee}")

        # Encrypt response token for GCSplit1
        encrypted_response_token = token_manager.encrypt_gcsplit2_to_gcsplit1_token(
            user_id=user_id,
            closed_channel_id=closed_channel_id,
            wallet_address=wallet_address,
            payout_currency=payout_currency,
            payout_network=payout_network,
            from_amount_usdt=float(from_amount),
            to_amount_eth_post_fee=float(to_amount),
            deposit_fee=float(deposit_fee),
            withdrawal_fee=float(withdrawal_fee)
        )

        if not encrypted_response_token:
            print(f"❌ [ENDPOINT] Failed to encrypt response token")
            abort(500, "Token encryption failed")

        # Enqueue Cloud Task back to GCSplit1
        if not cloudtasks_client:
            print(f"❌ [ENDPOINT] Cloud Tasks client not available")
            abort(500, "Cloud Tasks unavailable")

        gcsplit1_response_queue = config.get('gcsplit1_response_queue')
        gcsplit1_url = config.get('gcsplit1_url')

        if not gcsplit1_response_queue or not gcsplit1_url:
            print(f"❌ [ENDPOINT] GCSplit1 configuration missing")
            abort(500, "Service configuration error")

        task_name = cloudtasks_client.enqueue_gcsplit1_estimate_response(
            queue_name=gcsplit1_response_queue,
            target_url=gcsplit1_url,
            encrypted_token=encrypted_response_token
        )

        if not task_name:
            print(f"❌ [ENDPOINT] Failed to create Cloud Task")
            abort(500, "Failed to enqueue task")

        print(f"✅ [ENDPOINT] Successfully enqueued response to GCSplit1")
        print(f"🆔 [ENDPOINT] Task: {task_name}")

        return jsonify({
            "status": "success",
            "message": "USDT→ETH estimate completed and response enqueued",
            "task_id": task_name
        }), 200

    except Exception as e:
        print(f"❌ [ENDPOINT] Unexpected error: {e}")
        return jsonify({
            "status": "error",
            "message": f"Processing error: {str(e)}"
        }), 500


# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for monitoring."""
    try:
        return jsonify({
            "status": "healthy",
            "service": "GCSplit2-10-26 USDT→ETH Estimator",
            "timestamp": int(time.time()),
            "components": {
                "token_manager": "healthy" if token_manager else "unhealthy",
                "cloudtasks": "healthy" if cloudtasks_client else "unhealthy",
                "changenow": "healthy" if changenow_client else "unhealthy"
            }
        }), 200

    except Exception as e:
        print(f"❌ [HEALTH] Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "service": "GCSplit2-10-26 USDT→ETH Estimator",
            "error": str(e)
        }), 503


# ============================================================================
# FLASK ENTRYPOINT
# ============================================================================

if __name__ == "__main__":
    print(f"🚀 [APP] Starting GCSplit2-10-26 on port 8080")
    app.run(host="0.0.0.0", port=8080, debug=False)
