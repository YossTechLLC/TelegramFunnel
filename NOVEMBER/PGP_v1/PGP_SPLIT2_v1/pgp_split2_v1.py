#!/usr/bin/env python
"""
PGP_SPLIT2_v1: USDT→ETH Estimator Service
Receives encrypted tokens from PGP_SPLIT1_v1, calls ChangeNow API for USDT→ETH estimates,
and returns encrypted responses back to PGP_SPLIT1_v1 via Cloud Tasks.
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
from PGP_COMMON.utils import ChangeNowClient

from PGP_COMMON.logging import setup_logger
logger = setup_logger(__name__)

app = Flask(__name__)

# Initialize managers
logger.info(f"🚀 [APP] Initializing PGP_SPLIT2_v1 USDT→ETH Estimator Service")
config_manager = ConfigManager()
config = config_manager.initialize_config()

# Initialize token manager
try:
    signing_key = config.get('success_url_signing_key')
    if not signing_key:
        raise ValueError("SUCCESS_URL_SIGNING_KEY not available")
    token_manager = TokenManager(signing_key)
    logger.info(f"✅ [APP] Token manager initialized")
except Exception as e:
    logger.error(f"❌ [APP] Failed to initialize token manager: {e}", exc_info=True)
    token_manager = None

# Initialize Cloud Tasks client
try:
    project_id = config.get('cloud_tasks_project_id')
    location = config.get('cloud_tasks_location')
    if not project_id or not location:
        raise ValueError("Cloud Tasks configuration incomplete")
    cloudtasks_client = CloudTasksClient(project_id, location)
    logger.info(f"✅ [APP] Cloud Tasks client initialized")
except Exception as e:
    logger.error(f"❌ [APP] Failed to initialize Cloud Tasks client: {e}", exc_info=True)
    cloudtasks_client = None

# Initialize ChangeNow client with config_manager for hot-reload
try:
    changenow_client = ChangeNowClient(config_manager)
    logger.info(f"✅ [APP] ChangeNow client initialized (hot-reload enabled)")
except Exception as e:
    logger.error(f"❌ [APP] Failed to initialize ChangeNow client: {e}", exc_info=True)
    changenow_client = None


# ============================================================================
# MAIN ENDPOINT: POST / - Receives request from PGP_SPLIT1_v1
# ============================================================================

@app.route("/", methods=["POST"])
def process_usdt_eth_estimate():
    """
    Main endpoint for processing USDT→ETH estimate requests from PGP_SPLIT1_v1.

    Flow:
    1. Decrypt token from PGP_SPLIT1_v1
    2. Call ChangeNow API v2 for USDT→ETH estimate (with infinite retry)
    3. Encrypt response token
    4. Enqueue Cloud Task back to PGP_SPLIT1_v1

    Returns:
        JSON response with status
    """
    try:
        logger.info(f"🎯 [ENDPOINT] USDT→ETH estimate request received (from PGP_SPLIT1_v1)")

        # Parse JSON payload
        try:
            request_data = request.get_json()
            if not request_data:
                abort(400, "Invalid JSON payload")
        except Exception as e:
            logger.error(f"❌ [ENDPOINT] JSON parsing error: {e}", exc_info=True)
            abort(400, "Malformed JSON payload")

        encrypted_token = request_data.get('token')
        if not encrypted_token:
            logger.error(f"❌ [ENDPOINT] Missing token", exc_info=True)
            abort(400, "Missing token")

        # Decrypt token
        if not token_manager:
            logger.error(f"❌ [ENDPOINT] Token manager not available")
            abort(500, "Service configuration error")

        decrypted_data = token_manager.decrypt_pgp_split1_to_pgp_split2_token(encrypted_token)
        if not decrypted_data:
            logger.error(f"❌ [ENDPOINT] Failed to decrypt token")
            abort(401, "Invalid token")

        # Extract data
        user_id = decrypted_data['user_id']
        closed_channel_id = decrypted_data['closed_channel_id']
        wallet_address = decrypted_data['wallet_address']
        payout_currency = decrypted_data['payout_currency']
        payout_network = decrypted_data['payout_network']
        adjusted_amount = decrypted_data['adjusted_amount']  # ✅ UPDATED: Generic (ETH or USDT)
        actual_eth_amount = decrypted_data.get('actual_eth_amount', 0.0)
        swap_currency = decrypted_data.get('swap_currency', 'usdt')  # ✅ NEW: Extract swap_currency
        payout_mode = decrypted_data.get('payout_mode', 'instant')  # ✅ NEW: Extract payout_mode

        logger.info(f"👤 [ENDPOINT] User ID: {user_id}")
        logger.info(f"🏦 [ENDPOINT] Wallet: {wallet_address}")
        logger.info(f"💱 [ENDPOINT] Swap Currency: {swap_currency}")  # ✅ NEW LOG
        logger.info(f"🎯 [ENDPOINT] Payout Mode: {payout_mode}")  # ✅ NEW LOG
        logger.info(f"💰 [ENDPOINT] Amount: {adjusted_amount} {swap_currency.upper()}")  # ✅ UPDATED: Dynamic
        logger.info(f"💎 [ENDPOINT] ACTUAL ETH (from NowPayments): {actual_eth_amount}")
        logger.info(f"🎯 [ENDPOINT] Target: {payout_currency.upper()} on {payout_network.upper()}")

        # Call ChangeNow API with infinite retry
        if not changenow_client:
            logger.error(f"❌ [ENDPOINT] ChangeNow client not available")
            abort(500, "ChangeNow client unavailable")

        logger.info(f"🌐 [ENDPOINT] Calling ChangeNow API for {swap_currency.upper()}→{payout_currency.upper()} estimate (with retry)")

        estimate_response = changenow_client.get_estimated_amount_v2_with_retry(
            from_currency=swap_currency,  # ✅ UPDATED: Dynamic (eth or usdt)
            to_currency=payout_currency,
            from_network="eth",  # Both ETH and USDT use ETH network
            to_network=payout_network,
            from_amount=str(adjusted_amount),  # ✅ UPDATED: Generic variable name
            flow="standard",
            type_="direct"
        )

        # Note: estimate_response will always return (or timeout after 24h)
        # due to infinite retry in ChangeNowClient
        if not estimate_response:
            # This should never happen due to infinite retry, but handle it anyway
            logger.error(f"❌ [ENDPOINT] ChangeNow API returned None (should not happen)")
            abort(500, "ChangeNow API failure")

        # Extract estimate data
        from_amount = estimate_response.get('fromAmount')
        to_amount = estimate_response.get('toAmount')
        deposit_fee = estimate_response.get('depositFee', 0)
        withdrawal_fee = estimate_response.get('withdrawalFee', 0)

        logger.info(f"✅ [ENDPOINT] ChangeNow estimate received")
        logger.info(f"💰 [ENDPOINT] From: {from_amount} {swap_currency.upper()}")  # ✅ UPDATED: Dynamic currency
        logger.info(f"💰 [ENDPOINT] To: {to_amount} {payout_currency.upper()} (post-fee)")
        logger.debug(f"📊 [ENDPOINT] Deposit fee: {deposit_fee}")
        logger.debug(f"📊 [ENDPOINT] Withdrawal fee: {withdrawal_fee}")

        # Encrypt response token for PGP_SPLIT1_v1
        encrypted_response_token = token_manager.encrypt_pgp_split2_to_pgp_split1_token(
            user_id=user_id,
            closed_channel_id=closed_channel_id,
            wallet_address=wallet_address,
            payout_currency=payout_currency,
            payout_network=payout_network,
            from_amount=float(from_amount),  # ✅ UPDATED: Generic name
            to_amount_eth_post_fee=float(to_amount),
            deposit_fee=float(deposit_fee),
            withdrawal_fee=float(withdrawal_fee),
            swap_currency=swap_currency,  # ✅ NEW: Pass swap_currency
            payout_mode=payout_mode,  # ✅ NEW: Pass payout_mode
            actual_eth_amount=actual_eth_amount
        )

        if not encrypted_response_token:
            logger.error(f"❌ [ENDPOINT] Failed to encrypt response token")
            abort(500, "Token encryption failed")

        # Enqueue Cloud Task back to PGP_SPLIT1_v1
        if not cloudtasks_client:
            logger.error(f"❌ [ENDPOINT] Cloud Tasks client not available")
            abort(500, "Cloud Tasks unavailable")

        # Fetch hot-reloadable secrets dynamically
        split1_response_queue = config_manager.get_split1_response_queue()
        split1_url = config_manager.get_split1_url()

        if not split1_response_queue or not split1_url:
            logger.error(f"❌ [ENDPOINT] PGP_SPLIT1_v1 configuration missing")
            abort(500, "Service configuration error")

        task_name = cloudtasks_client.enqueue_pgp_split1_estimate_response(
            queue_name=split1_response_queue,
            target_url=split1_url,
            encrypted_token=encrypted_response_token
        )

        if not task_name:
            logger.error(f"❌ [ENDPOINT] Failed to create Cloud Task")
            abort(500, "Failed to enqueue task")

        logger.info(f"✅ [ENDPOINT] Successfully enqueued response to PGP_SPLIT1_v1")
        logger.debug(f"🆔 [ENDPOINT] Task: {task_name}")

        return jsonify({
            "status": "success",
            "message": "USDT→ETH estimate completed and response enqueued",
            "task_id": task_name
        }), 200

    except Exception as e:
        logger.error(f"❌ [ENDPOINT] Unexpected error: {e}", exc_info=True)
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
            "service": "PGP_SPLIT2_v1 USDT→ETH Estimator",
            "timestamp": int(time.time()),
            "components": {
                "token_manager": "healthy" if token_manager else "unhealthy",
                "cloudtasks": "healthy" if cloudtasks_client else "unhealthy",
                "changenow": "healthy" if changenow_client else "unhealthy"
            }
        }), 200

    except Exception as e:
        logger.error(f"❌ [HEALTH] Health check failed: {e}", exc_info=True)
        return jsonify({
            "status": "unhealthy",
            "service": "PGP_SPLIT2_v1 USDT→ETH Estimator",
            "error": str(e)
        }), 503


# ============================================================================
# FLASK ENTRYPOINT
# ============================================================================

if __name__ == "__main__":
    logger.info(f"🚀 [APP] Starting PGP_SPLIT2_v1 on port 8080")
    app.run(host="0.0.0.0", port=8080, debug=False)
