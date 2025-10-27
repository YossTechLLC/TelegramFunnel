#!/usr/bin/env python
"""
GCHostPay3-10-26: ETH Payment Executor Service
Receives payment execution requests from GCHostPay1, executes ETH payments
with INFINITE RETRY logic, and returns response back to GCHostPay1.

Implements infinite retry via Cloud Tasks (60s fixed backoff, 24h max duration).
"""
import time
from flask import Flask, request, abort, jsonify

# Import service modules
from config_manager import ConfigManager
from token_manager import TokenManager
from database_manager import DatabaseManager
from cloudtasks_client import CloudTasksClient
from wallet_manager import WalletManager

app = Flask(__name__)

# Initialize managers
print(f"🚀 [APP] Initializing GCHostPay3-10-26 ETH Payment Executor Service")
config_manager = ConfigManager()
config = config_manager.initialize_config()

# Initialize token manager
try:
    # Note: GCHostPay3 only needs internal signing key
    tps_hostpay_key = config.get('success_url_signing_key')  # Use same key for both
    internal_key = config.get('success_url_signing_key')

    if not internal_key:
        raise ValueError("SUCCESS_URL_SIGNING_KEY not available")

    token_manager = TokenManager(tps_hostpay_key, internal_key)
    print(f"✅ [APP] Token manager initialized")
except Exception as e:
    print(f"❌ [APP] Failed to initialize token manager: {e}")
    token_manager = None

# Initialize wallet manager
try:
    wallet_address = config.get('host_wallet_address')
    private_key = config.get('host_wallet_private_key')
    rpc_url = config.get('ethereum_rpc_url')
    alchemy_api_key = config.get('ethereum_rpc_url_api')

    if not wallet_address or not private_key or not rpc_url:
        raise ValueError("Wallet configuration incomplete")

    wallet_manager = WalletManager(wallet_address, private_key, rpc_url, alchemy_api_key)
    print(f"✅ [APP] Wallet manager initialized")
except Exception as e:
    print(f"❌ [APP] Failed to initialize wallet manager: {e}")
    wallet_manager = None

# Initialize database manager
try:
    instance_connection_name = config.get('instance_connection_name')
    db_name = config.get('db_name')
    db_user = config.get('db_user')
    db_password = config.get('db_password')

    if not all([instance_connection_name, db_name, db_user, db_password]):
        raise ValueError("Database configuration incomplete")

    db_manager = DatabaseManager()
    print(f"✅ [APP] Database manager initialized")
except Exception as e:
    print(f"❌ [APP] Failed to initialize database manager: {e}")
    db_manager = None

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


# ============================================================================
# MAIN ENDPOINT: POST / - Receives request from GCHostPay1
# ============================================================================

@app.route("/", methods=["POST"])
def execute_eth_payment():
    """
    Main endpoint for executing ETH payments with infinite retry.

    Flow:
    1. Decrypt token from GCHostPay1
    2. Extract payment details
    3. Execute ETH payment with INFINITE RETRY (60s backoff, 24h max)
    4. Log to database (ONLY after success)
    5. Encrypt response token
    6. Enqueue back to GCHostPay1 /payment-completed

    Returns:
        JSON response with status (or 500 to trigger Cloud Tasks retry)
    """
    try:
        print(f"🎯 [ENDPOINT] Payment execution request received (from GCHostPay1)")

        # Parse JSON payload
        try:
            request_data = request.get_json()
            if not request_data:
                abort(400, "Invalid JSON payload")
        except Exception as e:
            print(f"❌ [ENDPOINT] JSON parsing error: {e}")
            abort(400, "Malformed JSON payload")

        token = request_data.get('token')
        if not token:
            print(f"❌ [ENDPOINT] Missing token")
            abort(400, "Missing token")

        # Decrypt token
        if not token_manager:
            print(f"❌ [ENDPOINT] Token manager not available")
            abort(500, "Service configuration error")

        try:
            decrypted_data = token_manager.decrypt_gchostpay1_to_gchostpay3_token(token)
            if not decrypted_data:
                print(f"❌ [ENDPOINT] Failed to decrypt token")
                abort(401, "Invalid token")

            unique_id = decrypted_data['unique_id']
            cn_api_id = decrypted_data['cn_api_id']
            from_currency = decrypted_data['from_currency']
            from_network = decrypted_data['from_network']
            from_amount = decrypted_data['from_amount']
            payin_address = decrypted_data['payin_address']

            print(f"✅ [ENDPOINT] Token decoded successfully")
            print(f"🆔 [ENDPOINT] Unique ID: {unique_id}")
            print(f"🆔 [ENDPOINT] CN API ID: {cn_api_id}")
            print(f"💰 [ENDPOINT] Amount: {from_amount} {from_currency.upper()}")
            print(f"🏦 [ENDPOINT] Payin Address: {payin_address}")

        except Exception as e:
            print(f"❌ [ENDPOINT] Token validation error: {e}")
            abort(400, f"Token error: {e}")

        # Execute ETH payment with INFINITE RETRY
        if not wallet_manager:
            print(f"❌ [ENDPOINT] Wallet manager not available")
            abort(500, "Wallet manager unavailable")

        print(f"💰 [ENDPOINT] Executing ETH payment with infinite retry")

        tx_result = wallet_manager.send_eth_payment_with_infinite_retry(
            to_address=payin_address,
            amount=from_amount,
            unique_id=unique_id
        )

        # Note: tx_result will always return (or timeout after 24h) due to infinite retry
        if not tx_result:
            # This should never happen due to infinite retry, but handle it anyway
            print(f"❌ [ENDPOINT] ETH payment returned None (should not happen)")
            abort(500, "ETH payment failure")

        print(f"✅ [ENDPOINT] ETH payment executed successfully")
        print(f"🔗 [ENDPOINT] TX Hash: {tx_result['tx_hash']}")
        print(f"📊 [ENDPOINT] TX Status: {tx_result['status']}")
        print(f"⛽ [ENDPOINT] Gas Used: {tx_result['gas_used']}")
        print(f"📦 [ENDPOINT] Block Number: {tx_result['block_number']}")

        # Log to database (ONLY after successful payment)
        if not db_manager:
            print(f"⚠️ [ENDPOINT] Database manager not available - skipping database log")
        else:
            try:
                db_success = db_manager.insert_hostpay_transaction(
                    unique_id=unique_id,
                    cn_api_id=cn_api_id,
                    from_currency=from_currency,
                    from_network=from_network,
                    from_amount=from_amount,
                    payin_address=payin_address,
                    is_complete=True,
                    tx_hash=tx_result['tx_hash'],
                    tx_status=tx_result['status'],
                    gas_used=tx_result['gas_used'],
                    block_number=tx_result['block_number']
                )

                if db_success:
                    print(f"✅ [ENDPOINT] Database: Successfully logged payment")
                else:
                    print(f"⚠️ [ENDPOINT] Database: Failed to log payment (non-fatal)")

            except Exception as e:
                print(f"❌ [ENDPOINT] Database error: {e} (non-fatal)")

        # Encrypt response token
        encrypted_response_token = token_manager.encrypt_gchostpay3_to_gchostpay1_token(
            unique_id=unique_id,
            cn_api_id=cn_api_id,
            tx_hash=tx_result['tx_hash'],
            tx_status=tx_result['status'],
            gas_used=tx_result['gas_used'],
            block_number=tx_result['block_number']
        )

        if not encrypted_response_token:
            print(f"❌ [ENDPOINT] Failed to encrypt response token")
            abort(500, "Token encryption failed")

        # Enqueue response back to GCHostPay1
        if not cloudtasks_client:
            print(f"❌ [ENDPOINT] Cloud Tasks client not available")
            abort(500, "Cloud Tasks unavailable")

        gchostpay1_response_queue = config.get('gchostpay1_response_queue')
        gchostpay1_url = config.get('gchostpay1_url')

        if not gchostpay1_response_queue or not gchostpay1_url:
            print(f"❌ [ENDPOINT] GCHostPay1 configuration missing")
            abort(500, "Service configuration error")

        # Target the /payment-completed endpoint
        target_url = f"{gchostpay1_url}/payment-completed"

        task_name = cloudtasks_client.enqueue_gchostpay1_payment_response(
            queue_name=gchostpay1_response_queue,
            target_url=target_url,
            encrypted_token=encrypted_response_token
        )

        if not task_name:
            print(f"❌ [ENDPOINT] Failed to create Cloud Task")
            abort(500, "Failed to enqueue task")

        print(f"✅ [ENDPOINT] Successfully enqueued response to GCHostPay1")
        print(f"🆔 [ENDPOINT] Task: {task_name}")

        return jsonify({
            "status": "success",
            "message": "Payment executed and response enqueued",
            "unique_id": unique_id,
            "cn_api_id": cn_api_id,
            "tx_hash": tx_result['tx_hash'],
            "tx_status": tx_result['status'],
            "gas_used": tx_result['gas_used'],
            "block_number": tx_result['block_number'],
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
            "service": "GCHostPay3-10-26 ETH Payment Executor",
            "timestamp": int(time.time()),
            "components": {
                "token_manager": "healthy" if token_manager else "unhealthy",
                "wallet": "healthy" if wallet_manager else "unhealthy",
                "database": "healthy" if db_manager else "unhealthy",
                "cloudtasks": "healthy" if cloudtasks_client else "unhealthy"
            }
        }), 200

    except Exception as e:
        print(f"❌ [HEALTH] Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "service": "GCHostPay3-10-26 ETH Payment Executor",
            "error": str(e)
        }), 503


# ============================================================================
# FLASK ENTRYPOINT
# ============================================================================

if __name__ == "__main__":
    print(f"🚀 [APP] Starting GCHostPay3-10-26 on port 8080")
    app.run(host="0.0.0.0", port=8080, debug=False)
