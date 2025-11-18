#!/usr/bin/env python
"""
PGP_SPLIT3_v1: ETH→ClientCurrency Swapper Service
Receives encrypted tokens from PGP_SPLIT1_v1, creates ChangeNow fixed-rate transactions (ETH→ClientCurrency),
and returns encrypted responses back to PGP_SPLIT1_v1 via Cloud Tasks.
Implements infinite retry logic for resilience against API failures.
"""
import time
from typing import Dict, Any
from flask import Flask, request, abort, jsonify

# Import service modules
from config_manager import ConfigManager
from token_manager import TokenManager
from cloudtasks_client import CloudTasksClient
from PGP_COMMON.utils import ChangeNowClient

app = Flask(__name__)

# Initialize managers
print(f"🚀 [APP] Initializing PGP_SPLIT3_v1 ETH→Client Swapper Service")
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

# Initialize ChangeNow client with config_manager for hot-reload
try:
    changenow_client = ChangeNowClient(config_manager)
    print(f"✅ [APP] ChangeNow client initialized (hot-reload enabled)")
except Exception as e:
    print(f"❌ [APP] Failed to initialize ChangeNow client: {e}")
    changenow_client = None


# ============================================================================
# MAIN ENDPOINT: POST / - Receives request from PGP_SPLIT1_v1
# ============================================================================

@app.route("/", methods=["POST"])
def process_eth_client_swap():
    """
    Main endpoint for processing ETH→ClientCurrency swap requests from PGP_SPLIT1_v1.

    Flow:
    1. Decrypt token from PGP_SPLIT1_v1
    2. Create ChangeNow fixed-rate transaction (ETH→ClientCurrency) with infinite retry
    3. Encrypt response token with full transaction data
    4. Enqueue Cloud Task back to PGP_SPLIT1_v1

    Returns:
        JSON response with status
    """
    try:
        print(f"🎯 [ENDPOINT] ETH→Client swap request received (from PGP_SPLIT1_v1)")

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

        decrypted_data = token_manager.decrypt_pgp_split1_to_pgp_split3_token(encrypted_token)
        if not decrypted_data:
            print(f"❌ [ENDPOINT] Failed to decrypt token")
            abort(401, "Invalid token")

        # Extract data
        unique_id = decrypted_data['unique_id']
        user_id = decrypted_data['user_id']
        closed_channel_id = decrypted_data['closed_channel_id']
        wallet_address = decrypted_data['wallet_address']
        payout_currency = decrypted_data['payout_currency']
        payout_network = decrypted_data['payout_network']
        swap_amount = decrypted_data['eth_amount']  # ✅ UPDATED: Generic (ETH or USDT)
        actual_eth_amount = decrypted_data.get('actual_eth_amount', 0.0)
        swap_currency = decrypted_data.get('swap_currency', 'usdt')  # ✅ NEW: Extract swap_currency
        payout_mode = decrypted_data.get('payout_mode', 'instant')  # ✅ NEW: Extract payout_mode

        print(f"🆔 [ENDPOINT] Unique ID: {unique_id}")
        print(f"👤 [ENDPOINT] User ID: {user_id}")
        print(f"🏦 [ENDPOINT] Wallet: {wallet_address}")
        print(f"💱 [ENDPOINT] Swap Currency: {swap_currency}")  # ✅ NEW LOG
        print(f"🎯 [ENDPOINT] Payout Mode: {payout_mode}")  # ✅ NEW LOG
        print(f"💰 [ENDPOINT] Swap Amount: {swap_amount} {swap_currency.upper()}")  # ✅ UPDATED: Dynamic
        print(f"💎 [ENDPOINT] ACTUAL ETH (from NowPayments): {actual_eth_amount}")
        print(f"🎯 [ENDPOINT] Target: {payout_currency.upper()} on {payout_network.upper()}")

        # Create ChangeNow fixed-rate transaction with infinite retry
        if not changenow_client:
            print(f"❌ [ENDPOINT] ChangeNow client not available")
            abort(500, "ChangeNow client unavailable")

        print(f"🌐 [ENDPOINT] Creating ChangeNow transaction {swap_currency.upper()}→{payout_currency.upper()} (with retry)")

        transaction = changenow_client.create_fixed_rate_transaction_with_retry(
            from_currency=swap_currency,  # ✅ UPDATED: Dynamic (eth or usdt)
            to_currency=payout_currency,
            from_amount=swap_amount,  # ✅ UPDATED: Generic variable name
            address=wallet_address,
            from_network="eth",  # Both ETH and USDT use ETH network
            to_network=payout_network,
            user_id=str(user_id)
        )

        # Note: transaction will always return (or timeout after 24h) due to infinite retry
        if not transaction:
            # This should never happen due to infinite retry, but handle it anyway
            print(f"❌ [ENDPOINT] ChangeNow API returned None (should not happen)")
            abort(500, "ChangeNow API failure")

        # Extract transaction data
        cn_api_id = transaction.get('id', '')
        api_from_amount = float(transaction.get('fromAmount', 0))
        api_to_amount = float(transaction.get('toAmount', 0))
        api_from_currency = transaction.get('fromCurrency', 'eth')
        api_to_currency = transaction.get('toCurrency', payout_currency)
        api_from_network = transaction.get('fromNetwork', 'eth')
        api_to_network = transaction.get('toNetwork', payout_network)
        api_payin_address = transaction.get('payinAddress', '')
        api_payout_address = transaction.get('payoutAddress', wallet_address)
        api_refund_address = transaction.get('refundAddress', '')
        api_flow = transaction.get('flow', 'standard')
        api_type = transaction.get('type', 'direct')

        print(f"✅ [ENDPOINT] ChangeNow transaction created")
        print(f"🆔 [ENDPOINT] ChangeNow API ID: {cn_api_id}")
        print(f"🏦 [ENDPOINT] Payin address: {api_payin_address}")
        print(f"💰 [ENDPOINT] From: {api_from_amount} {api_from_currency.upper()}")  # ✅ UPDATED: Dynamic currency
        print(f"💰 [ENDPOINT] To: {api_to_amount} {api_to_currency.upper()}")

        # Encrypt response token for PGP_SPLIT1_v1
        encrypted_response_token = token_manager.encrypt_pgp_split3_to_pgp_split1_token(
            unique_id=unique_id,
            user_id=user_id,
            closed_channel_id=closed_channel_id,
            cn_api_id=cn_api_id,
            from_currency=api_from_currency,
            to_currency=api_to_currency,
            from_network=api_from_network,
            to_network=api_to_network,
            from_amount=api_from_amount,
            to_amount=api_to_amount,
            payin_address=api_payin_address,
            payout_address=api_payout_address,
            refund_address=api_refund_address,
            flow=api_flow,
            type_=api_type,
            actual_eth_amount=actual_eth_amount  # ✅ ADDED: Pass through ACTUAL ETH to PGP_SPLIT1_v1
        )

        if not encrypted_response_token:
            print(f"❌ [ENDPOINT] Failed to encrypt response token")
            abort(500, "Token encryption failed")

        # Enqueue Cloud Task back to PGP_SPLIT1_v1
        if not cloudtasks_client:
            print(f"❌ [ENDPOINT] Cloud Tasks client not available")
            abort(500, "Cloud Tasks unavailable")

        gcsplit1_response_queue = config.get('gcsplit1_response_queue')
        pgp_split1_url = config.get('pgp_split1_url')

        if not gcsplit1_response_queue or not pgp_split1_url:
            print(f"❌ [ENDPOINT] PGP_SPLIT1_v1 configuration missing")
            abort(500, "Service configuration error")

        task_name = cloudtasks_client.enqueue_pgp_split1_swap_response(
            queue_name=gcsplit1_response_queue,
            target_url=pgp_split1_url,
            encrypted_token=encrypted_response_token
        )

        if not task_name:
            print(f"❌ [ENDPOINT] Failed to create Cloud Task")
            abort(500, "Failed to enqueue task")

        print(f"✅ [ENDPOINT] Successfully enqueued response to PGP_SPLIT1_v1")
        print(f"🆔 [ENDPOINT] Task: {task_name}")

        return jsonify({
            "status": "success",
            "message": "ETH→Client swap completed and response enqueued",
            "unique_id": unique_id,
            "cn_api_id": cn_api_id,
            "task_id": task_name
        }), 200

    except Exception as e:
        print(f"❌ [ENDPOINT] Unexpected error: {e}")
        return jsonify({
            "status": "error",
            "message": f"Processing error: {str(e)}"
        }), 500


# ============================================================================
# NEW ENDPOINT: POST /eth-to-usdt - Create ETH→USDT Swap for Threshold Payouts
# ============================================================================

@app.route("/eth-to-usdt", methods=["POST"])
def process_eth_to_usdt_swap():
    """
    New endpoint for creating ETH→USDT swaps (threshold payout accumulation).

    Flow:
    1. Decrypt token from PGP_ACCUMULATOR
    2. Create ChangeNow fixed-rate transaction (ETH→USDT)
    3. Encrypt response token with transaction details
    4. Enqueue Cloud Task back to PGP_ACCUMULATOR

    This endpoint mirrors the existing `/` endpoint but for USDT target currency.

    Returns:
        JSON response with status
    """
    try:
        print(f"🎯 [ENDPOINT] ETH→USDT swap request received (from PGP_ACCUMULATOR)")

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

        decrypted_data = token_manager.decrypt_accumulator_to_pgp_split3_token(encrypted_token)
        if not decrypted_data:
            print(f"❌ [ENDPOINT] Failed to decrypt token")
            abort(401, "Invalid token")

        # Extract data
        accumulation_id = decrypted_data['accumulation_id']
        client_id = decrypted_data['client_id']
        eth_amount = decrypted_data['eth_amount']
        usdt_wallet_address = decrypted_data.get('usdt_wallet_address', '')

        print(f"🆔 [ENDPOINT] Accumulation ID: {accumulation_id}")
        print(f"🏢 [ENDPOINT] Client ID: {client_id}")
        print(f"💰 [ENDPOINT] ETH Amount: ${eth_amount} (USD equivalent)")
        print(f"🎯 [ENDPOINT] Target: USDT on ETH network")
        print(f"🏦 [ENDPOINT] USDT Wallet: {usdt_wallet_address}")

        # Create ChangeNow fixed-rate transaction (ETH→USDT)
        if not changenow_client:
            print(f"❌ [ENDPOINT] ChangeNow client not available")
            abort(500, "ChangeNow client unavailable")

        print(f"🌐 [ENDPOINT] Creating ChangeNow ETH→USDT transaction (with retry)")

        transaction = changenow_client.create_fixed_rate_transaction_with_retry(
            from_currency="eth",
            to_currency="usdt",
            from_amount=str(eth_amount),
            address=usdt_wallet_address,  # Platform's USDT receiving address
            from_network="eth",
            to_network="eth",
            user_id=f"accumulation_{accumulation_id}"
        )

        if not transaction:
            print(f"❌ [ENDPOINT] ChangeNow API returned None (should not happen)")
            abort(500, "ChangeNow API failure")

        # Extract transaction data
        cn_api_id = transaction.get('id', '')
        api_from_amount = float(transaction.get('fromAmount', 0))
        api_to_amount = float(transaction.get('toAmount', 0))
        api_payin_address = transaction.get('payinAddress', '')
        api_payout_address = transaction.get('payoutAddress', usdt_wallet_address)

        print(f"✅ [ENDPOINT] ChangeNow transaction created")
        print(f"🆔 [ENDPOINT] ChangeNow API ID: {cn_api_id}")
        print(f"🏦 [ENDPOINT] Payin address: {api_payin_address}")
        print(f"💰 [ENDPOINT] From: ${api_from_amount} ETH (USD equivalent)")
        print(f"💰 [ENDPOINT] To: ${api_to_amount} USDT")

        # Encrypt response token for PGP_ACCUMULATOR
        encrypted_response_token = token_manager.encrypt_pgp_split3_to_accumulator_token(
            accumulation_id=accumulation_id,
            client_id=client_id,
            cn_api_id=cn_api_id,
            from_amount=api_from_amount,
            to_amount=api_to_amount,
            payin_address=api_payin_address,
            payout_address=api_payout_address
        )

        if not encrypted_response_token:
            print(f"❌ [ENDPOINT] Failed to encrypt response token")
            abort(500, "Token encryption failed")

        # Enqueue Cloud Task back to PGP_ACCUMULATOR
        if not cloudtasks_client:
            print(f"❌ [ENDPOINT] Cloud Tasks client not available")
            abort(500, "Cloud Tasks unavailable")

        pgp_accumulator_response_queue = config.get('pgp_accumulator_response_queue')
        pgp_accumulator_url = config.get('pgp_accumulator_url')

        if not pgp_accumulator_response_queue or not pgp_accumulator_url:
            print(f"❌ [ENDPOINT] PGP_ACCUMULATOR configuration missing")
            abort(500, "Service configuration error")

        task_name = cloudtasks_client.enqueue_accumulator_swap_response(
            queue_name=pgp_accumulator_response_queue,
            target_url=f"{pgp_accumulator_url}/swap-created",
            encrypted_token=encrypted_response_token
        )

        if not task_name:
            print(f"❌ [ENDPOINT] Failed to create Cloud Task")
            abort(500, "Failed to enqueue task")

        print(f"✅ [ENDPOINT] Successfully enqueued response to PGP_ACCUMULATOR")
        print(f"🆔 [ENDPOINT] Task: {task_name}")

        return jsonify({
            "status": "success",
            "message": "ETH→USDT swap created and response enqueued",
            "accumulation_id": accumulation_id,
            "cn_api_id": cn_api_id,
            "from_amount": api_from_amount,
            "to_amount": api_to_amount,
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
            "service": "PGP_SPLIT3_v1 ETH→Client Swapper",
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
            "service": "PGP_SPLIT3_v1 ETH→Client Swapper",
            "error": str(e)
        }), 503


# ============================================================================
# FLASK ENTRYPOINT
# ============================================================================

if __name__ == "__main__":
    print(f"🚀 [APP] Starting PGP_SPLIT3_v1 on port 8080")
    app.run(host="0.0.0.0", port=8080, debug=False)
