#!/usr/bin/env python
"""
GCHostPay1-10-26: Validator & Orchestrator Service
Receives payment split requests from GCSplit1, validates, and orchestrates:
1. ChangeNow status check via GCHostPay2
2. ETH payment execution via GCHostPay3

Endpoints:
- POST / - Main webhook (from GCSplit1)
- POST /status-verified - Status check response (from GCHostPay2)
- POST /payment-completed - Payment execution response (from GCHostPay3)
"""
import time
from flask import Flask, request, abort, jsonify

# Import service modules
from config_manager import ConfigManager
from token_manager import TokenManager
from database_manager import DatabaseManager
from cloudtasks_client import CloudTasksClient

app = Flask(__name__)

# Initialize managers
print(f"🚀 [APP] Initializing GCHostPay1-10-26 Validator & Orchestrator Service")
config_manager = ConfigManager()
config = config_manager.initialize_config()

# Initialize token manager
try:
    tps_hostpay_key = config.get('tps_hostpay_signing_key')
    internal_key = config.get('success_url_signing_key')

    if not tps_hostpay_key or not internal_key:
        raise ValueError("Signing keys not available")

    token_manager = TokenManager(tps_hostpay_key, internal_key)
    print(f"✅ [APP] Token manager initialized")
except Exception as e:
    print(f"❌ [APP] Failed to initialize token manager: {e}")
    token_manager = None

# Initialize database manager
try:
    instance_connection_name = config.get('instance_connection_name')
    db_name = config.get('db_name')
    db_user = config.get('db_user')
    db_password = config.get('db_password')

    if not all([instance_connection_name, db_name, db_user, db_password]):
        raise ValueError("Database configuration incomplete")

    db_manager = DatabaseManager(instance_connection_name, db_name, db_user, db_password)
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
# ENDPOINT 1: POST / - Main webhook (from GCSplit1)
# ============================================================================

@app.route("/", methods=["POST"])
def main_webhook():
    """
    Main webhook endpoint for receiving payment split requests from GCSplit1.

    Flow:
    1. Decode & verify token from GCSplit1
    2. Extract: unique_id, cn_api_id, from_currency, from_network, from_amount, payin_address
    3. Check database for duplicate
    4. Encrypt token for GCHostPay2 (status check)
    5. Enqueue to GCHostPay2 via Cloud Tasks

    Returns:
        JSON response with status
    """
    try:
        print(f"🎯 [ENDPOINT_1] Payment split request received (from GCSplit1)")

        # Parse JSON payload
        try:
            request_data = request.get_json()
            if not request_data:
                abort(400, "Invalid JSON payload")
        except Exception as e:
            print(f"❌ [ENDPOINT_1] JSON parsing error: {e}")
            abort(400, "Malformed JSON payload")

        token = request_data.get('token')
        if not token:
            print(f"❌ [ENDPOINT_1] Missing token")
            abort(400, "Missing token")

        # Decode and verify token
        if not token_manager:
            print(f"❌ [ENDPOINT_1] Token manager not available")
            abort(500, "Service configuration error")

        try:
            decrypted_data = token_manager.decrypt_gcsplit1_to_gchostpay1_token(token)
            if not decrypted_data:
                print(f"❌ [ENDPOINT_1] Failed to decrypt token")
                abort(401, "Invalid token")

            unique_id = decrypted_data['unique_id']
            cn_api_id = decrypted_data['cn_api_id']
            from_currency = decrypted_data['from_currency']
            from_network = decrypted_data['from_network']
            from_amount = decrypted_data['from_amount']
            payin_address = decrypted_data['payin_address']

            print(f"✅ [ENDPOINT_1] Token decoded successfully")
            print(f"🆔 [ENDPOINT_1] Unique ID: {unique_id}")
            print(f"🆔 [ENDPOINT_1] CN API ID: {cn_api_id}")
            print(f"💰 [ENDPOINT_1] Amount: {from_amount} {from_currency.upper()}")
            print(f"🏦 [ENDPOINT_1] Payin Address: {payin_address}")

        except Exception as e:
            print(f"❌ [ENDPOINT_1] Token validation error: {e}")
            abort(400, f"Token error: {e}")

        # Check database for duplicate
        if not db_manager:
            print(f"❌ [ENDPOINT_1] Database manager not available")
            abort(500, "Database unavailable")

        try:
            if db_manager.check_transaction_exists(unique_id):
                print(f"⚠️ [ENDPOINT_1] Transaction {unique_id} already processed")
                return jsonify({
                    "status": "already_processed",
                    "message": "Transaction already processed",
                    "unique_id": unique_id
                }), 200
        except Exception as e:
            print(f"❌ [ENDPOINT_1] Database error: {e}")
            # Continue anyway - duplicate check is non-critical

        # Encrypt token for GCHostPay2 (with ALL payment details)
        encrypted_token = token_manager.encrypt_gchostpay1_to_gchostpay2_token(
            unique_id=unique_id,
            cn_api_id=cn_api_id,
            from_currency=from_currency,
            from_network=from_network,
            from_amount=from_amount,
            payin_address=payin_address
        )

        if not encrypted_token:
            print(f"❌ [ENDPOINT_1] Failed to encrypt token for GCHostPay2")
            abort(500, "Token encryption failed")

        # Enqueue status check to GCHostPay2
        if not cloudtasks_client:
            print(f"❌ [ENDPOINT_1] Cloud Tasks client not available")
            abort(500, "Cloud Tasks unavailable")

        gchostpay2_queue = config.get('gchostpay2_queue')
        gchostpay2_url = config.get('gchostpay2_url')

        if not gchostpay2_queue or not gchostpay2_url:
            print(f"❌ [ENDPOINT_1] GCHostPay2 configuration missing")
            abort(500, "Service configuration error")

        task_name = cloudtasks_client.enqueue_gchostpay2_status_check(
            queue_name=gchostpay2_queue,
            target_url=gchostpay2_url,
            encrypted_token=encrypted_token
        )

        if not task_name:
            print(f"❌ [ENDPOINT_1] Failed to enqueue status check to GCHostPay2")
            abort(500, "Failed to enqueue task")

        print(f"✅ [ENDPOINT_1] Enqueued status check to GCHostPay2")
        print(f"🆔 [ENDPOINT_1] Task: {task_name}")
        print(f"🎉 [ENDPOINT_1] Payment split request orchestrated successfully")

        return jsonify({
            "status": "success",
            "message": "Status check enqueued to GCHostPay2",
            "unique_id": unique_id,
            "cn_api_id": cn_api_id,
            "task_id": task_name
        }), 200

    except Exception as e:
        print(f"❌ [ENDPOINT_1] Unexpected error: {e}")
        return jsonify({
            "status": "error",
            "message": f"Processing error: {str(e)}"
        }), 500


# ============================================================================
# ENDPOINT 2: POST /status-verified - Status check response (from GCHostPay2)
# ============================================================================

@app.route("/status-verified", methods=["POST"])
def status_verified():
    """
    Status check response endpoint (receives from GCHostPay2).

    Flow:
    1. Decrypt token from GCHostPay2
    2. Validate status == "waiting"
    3. Encrypt token for GCHostPay3 (payment execution)
    4. Enqueue to GCHostPay3 via Cloud Tasks

    Returns:
        JSON response with status
    """
    try:
        print(f"🎯 [ENDPOINT_2] Status check response received (from GCHostPay2)")

        # Parse JSON payload
        try:
            request_data = request.get_json()
            if not request_data:
                abort(400, "Invalid JSON payload")
        except Exception as e:
            print(f"❌ [ENDPOINT_2] JSON parsing error: {e}")
            abort(400, "Malformed JSON payload")

        token = request_data.get('token')
        if not token:
            print(f"❌ [ENDPOINT_2] Missing token")
            abort(400, "Missing token")

        # Decrypt token
        if not token_manager:
            print(f"❌ [ENDPOINT_2] Token manager not available")
            abort(500, "Service configuration error")

        try:
            decrypted_data = token_manager.decrypt_gchostpay2_to_gchostpay1_token(token)
            if not decrypted_data:
                print(f"❌ [ENDPOINT_2] Failed to decrypt token")
                abort(401, "Invalid token")

            unique_id = decrypted_data['unique_id']
            cn_api_id = decrypted_data['cn_api_id']
            status = decrypted_data['status']
            from_currency = decrypted_data['from_currency']
            from_network = decrypted_data['from_network']
            from_amount = decrypted_data['from_amount']
            payin_address = decrypted_data['payin_address']

            print(f"✅ [ENDPOINT_2] Token decoded successfully")
            print(f"🆔 [ENDPOINT_2] Unique ID: {unique_id}")
            print(f"🆔 [ENDPOINT_2] CN API ID: {cn_api_id}")
            print(f"📊 [ENDPOINT_2] Status: {status}")
            print(f"💰 [ENDPOINT_2] Amount: {from_amount} {from_currency.upper()}")

        except Exception as e:
            print(f"❌ [ENDPOINT_2] Token validation error: {e}")
            abort(400, f"Token error: {e}")

        # Validate status == "waiting"
        if status != "waiting":
            print(f"⚠️ [ENDPOINT_2] Invalid status: {status} (expected 'waiting')")
            return jsonify({
                "status": "invalid_status",
                "message": f"ChangeNow status is '{status}', expected 'waiting'",
                "unique_id": unique_id,
                "cn_api_id": cn_api_id
            }), 400

        # Encrypt token for GCHostPay3 (payment execution)
        encrypted_token_payment = token_manager.encrypt_gchostpay1_to_gchostpay3_token(
            unique_id=unique_id,
            cn_api_id=cn_api_id,
            from_currency=from_currency,
            from_network=from_network,
            from_amount=from_amount,
            payin_address=payin_address
        )

        if not encrypted_token_payment:
            print(f"❌ [ENDPOINT_2] Failed to encrypt token for GCHostPay3")
            abort(500, "Token encryption failed")

        # Enqueue payment execution to GCHostPay3
        if not cloudtasks_client:
            print(f"❌ [ENDPOINT_2] Cloud Tasks client not available")
            abort(500, "Cloud Tasks unavailable")

        gchostpay3_queue = config.get('gchostpay3_queue')
        gchostpay3_url = config.get('gchostpay3_url')

        if not gchostpay3_queue or not gchostpay3_url:
            print(f"❌ [ENDPOINT_2] GCHostPay3 configuration missing")
            abort(500, "Service configuration error")

        task_name = cloudtasks_client.enqueue_gchostpay3_payment_execution(
            queue_name=gchostpay3_queue,
            target_url=gchostpay3_url,
            encrypted_token=encrypted_token_payment
        )

        if not task_name:
            print(f"❌ [ENDPOINT_2] Failed to enqueue payment execution to GCHostPay3")
            abort(500, "Failed to enqueue task")

        print(f"✅ [ENDPOINT_2] Enqueued payment execution to GCHostPay3")
        print(f"🆔 [ENDPOINT_2] Task: {task_name}")
        print(f"🎉 [ENDPOINT_2] Status verified workflow completed successfully")

        return jsonify({
            "status": "success",
            "message": "Status verified, payment execution enqueued",
            "unique_id": unique_id,
            "cn_api_id": cn_api_id,
            "changenow_status": status,
            "task_id": task_name
        }), 200

    except Exception as e:
        print(f"❌ [ENDPOINT_2] Unexpected error: {e}")
        return jsonify({
            "status": "error",
            "message": f"Processing error: {str(e)}"
        }), 500


# ============================================================================
# ENDPOINT 3: POST /payment-completed - Payment response (from GCHostPay3)
# ============================================================================

@app.route("/payment-completed", methods=["POST"])
def payment_completed():
    """
    Payment execution response endpoint (receives from GCHostPay3).

    Flow:
    1. Decrypt token from GCHostPay3
    2. Extract: unique_id, cn_api_id, tx_hash, tx_status, gas_used, block_number
    3. Log final status
    4. Complete workflow

    Returns:
        JSON response with status
    """
    try:
        print(f"🎯 [ENDPOINT_3] Payment execution response received (from GCHostPay3)")

        # Parse JSON payload
        try:
            request_data = request.get_json()
            if not request_data:
                abort(400, "Invalid JSON payload")
        except Exception as e:
            print(f"❌ [ENDPOINT_3] JSON parsing error: {e}")
            abort(400, "Malformed JSON payload")

        token = request_data.get('token')
        if not token:
            print(f"❌ [ENDPOINT_3] Missing token")
            abort(400, "Missing token")

        # Decrypt token
        if not token_manager:
            print(f"❌ [ENDPOINT_3] Token manager not available")
            abort(500, "Service configuration error")

        try:
            decrypted_data = token_manager.decrypt_gchostpay3_to_gchostpay1_token(token)
            if not decrypted_data:
                print(f"❌ [ENDPOINT_3] Failed to decrypt token")
                abort(401, "Invalid token")

            unique_id = decrypted_data['unique_id']
            cn_api_id = decrypted_data['cn_api_id']
            tx_hash = decrypted_data['tx_hash']
            tx_status = decrypted_data['tx_status']
            gas_used = decrypted_data['gas_used']
            block_number = decrypted_data['block_number']

            print(f"✅ [ENDPOINT_3] Token decoded successfully")
            print(f"🆔 [ENDPOINT_3] Unique ID: {unique_id}")
            print(f"🆔 [ENDPOINT_3] CN API ID: {cn_api_id}")
            print(f"🔗 [ENDPOINT_3] TX Hash: {tx_hash}")
            print(f"📊 [ENDPOINT_3] TX Status: {tx_status}")
            print(f"⛽ [ENDPOINT_3] Gas Used: {gas_used}")
            print(f"📦 [ENDPOINT_3] Block Number: {block_number}")

        except Exception as e:
            print(f"❌ [ENDPOINT_3] Token validation error: {e}")
            abort(400, f"Token error: {e}")

        print(f"🎉 [ENDPOINT_3] Payment workflow completed successfully!")

        return jsonify({
            "status": "success",
            "message": "Payment workflow completed",
            "unique_id": unique_id,
            "cn_api_id": cn_api_id,
            "tx_hash": tx_hash,
            "tx_status": tx_status,
            "gas_used": gas_used,
            "block_number": block_number
        }), 200

    except Exception as e:
        print(f"❌ [ENDPOINT_3] Unexpected error: {e}")
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
            "service": "GCHostPay1-10-26 Validator & Orchestrator",
            "timestamp": int(time.time()),
            "components": {
                "token_manager": "healthy" if token_manager else "unhealthy",
                "database": "healthy" if db_manager else "unhealthy",
                "cloudtasks": "healthy" if cloudtasks_client else "unhealthy"
            }
        }), 200

    except Exception as e:
        print(f"❌ [HEALTH] Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "service": "GCHostPay1-10-26 Validator & Orchestrator",
            "error": str(e)
        }), 503


# ============================================================================
# FLASK ENTRYPOINT
# ============================================================================

if __name__ == "__main__":
    print(f"🚀 [APP] Starting GCHostPay1-10-26 on port 8080")
    app.run(host="0.0.0.0", port=8080, debug=False)
