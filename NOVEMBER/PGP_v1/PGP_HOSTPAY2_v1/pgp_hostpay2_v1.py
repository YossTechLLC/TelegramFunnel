#!/usr/bin/env python
"""
PGP_HOSTPAY2_v1: ChangeNow Status Checker Service
Receives status check requests from PGP_HOSTPAY1_v1, checks ChangeNow API status
with INFINITE RETRY logic, and returns response back to PGP_HOSTPAY1_v1.

Implements infinite retry via Cloud Tasks (60s fixed backoff, 24h max duration).
"""
import time
from flask import Flask, request, abort, jsonify

# Import service modules
from config_manager import ConfigManager
from token_manager import TokenManager
from cloudtasks_client import CloudTasksClient
from changenow_client import ChangeNowClient

app = Flask(__name__)

# Initialize managers
print(f"🚀 [APP] Initializing PGP_HOSTPAY2_v1 ChangeNow Status Checker Service")
config_manager = ConfigManager()
config = config_manager.initialize_config()

# Initialize token manager
try:
    # Note: PGP_HOSTPAY2_v1 only needs internal signing key
    tps_hostpay_key = config.get('success_url_signing_key')  # Use same key for both
    internal_key = config.get('success_url_signing_key')

    if not internal_key:
        raise ValueError("SUCCESS_URL_SIGNING_KEY not available")

    token_manager = TokenManager(tps_hostpay_key, internal_key)
    print(f"✅ [APP] Token manager initialized")
except Exception as e:
    print(f"❌ [APP] Failed to initialize token manager: {e}")
    token_manager = None

# Initialize ChangeNow client
try:
    changenow_api_key = config.get('changenow_api_key')
    if not changenow_api_key:
        raise ValueError("CHANGENOW_API_KEY not available")

    changenow_client = ChangeNowClient(changenow_api_key)
    print(f"✅ [APP] ChangeNow client initialized")
except Exception as e:
    print(f"❌ [APP] Failed to initialize ChangeNow client: {e}")
    changenow_client = None

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
# MAIN ENDPOINT: POST / - Receives request from PGP_HOSTPAY1_v1
# ============================================================================

@app.route("/", methods=["POST"])
def check_changenow_status():
    """
    Main endpoint for checking ChangeNow status with infinite retry.

    Flow:
    1. Decrypt token from PGP_HOSTPAY1_v1
    2. Extract unique_id and cn_api_id
    3. Call ChangeNow API with INFINITE RETRY (60s backoff, 24h max)
    4. Extract status field
    5. Encrypt response token
    6. Enqueue back to PGP_HOSTPAY1_v1 /status-verified

    Returns:
        JSON response with status (or 500 to trigger Cloud Tasks retry)
    """
    try:
        print(f"🎯 [ENDPOINT] Status check request received (from PGP_HOSTPAY1_v1)")

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
            decrypted_data = token_manager.decrypt_pgp_hostpay1_to_pgp_hostpay2_token(token)
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

        except Exception as e:
            print(f"❌ [ENDPOINT] Token validation error: {e}")
            abort(400, f"Token error: {e}")

        # Check ChangeNow status with INFINITE RETRY
        if not changenow_client:
            print(f"❌ [ENDPOINT] ChangeNow client not available")
            abort(500, "ChangeNow client unavailable")

        print(f"🌐 [ENDPOINT] Checking ChangeNow status with infinite retry")

        status = changenow_client.check_transaction_status_with_retry(cn_api_id)

        # Note: status will always return (or timeout after 24h) due to infinite retry
        if not status:
            # This should never happen due to infinite retry, but handle it anyway
            print(f"❌ [ENDPOINT] ChangeNow API returned None (should not happen)")
            abort(500, "ChangeNow API failure")

        print(f"✅ [ENDPOINT] ChangeNow status retrieved: {status}")

        # Encrypt response token (with ALL payment details)
        encrypted_response_token = token_manager.encrypt_pgp_hostpay2_to_pgp_hostpay1_token(
            unique_id=unique_id,
            cn_api_id=cn_api_id,
            status=status,
            from_currency=from_currency,
            from_network=from_network,
            from_amount=from_amount,
            payin_address=payin_address
        )

        if not encrypted_response_token:
            print(f"❌ [ENDPOINT] Failed to encrypt response token")
            abort(500, "Token encryption failed")

        # Enqueue response back to PGP_HOSTPAY1_v1
        if not cloudtasks_client:
            print(f"❌ [ENDPOINT] Cloud Tasks client not available")
            abort(500, "Cloud Tasks unavailable")

        pgp_hostpay1_response_queue = config.get('pgp_hostpay1_response_queue')
        pgp_hostpay1_url = config.get('pgp_hostpay1_url')

        if not pgp_hostpay1_response_queue or not pgp_hostpay1_url:
            print(f"❌ [ENDPOINT] PGP_HOSTPAY1_v1 configuration missing")
            abort(500, "Service configuration error")

        # Target the /status-verified endpoint
        target_url = f"{pgp_hostpay1_url}/status-verified"

        task_name = cloudtasks_client.enqueue_pgp_hostpay1_status_response(
            queue_name=pgp_hostpay1_response_queue,
            target_url=target_url,
            encrypted_token=encrypted_response_token
        )

        if not task_name:
            print(f"❌ [ENDPOINT] Failed to create Cloud Task")
            abort(500, "Failed to enqueue task")

        print(f"✅ [ENDPOINT] Successfully enqueued response to PGP_HOSTPAY1_v1")
        print(f"🆔 [ENDPOINT] Task: {task_name}")

        return jsonify({
            "status": "success",
            "message": "Status check completed and response enqueued",
            "unique_id": unique_id,
            "cn_api_id": cn_api_id,
            "changenow_status": status,
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
            "service": "PGP_HOSTPAY2_v1 ChangeNow Status Checker",
            "timestamp": int(time.time()),
            "components": {
                "token_manager": "healthy" if token_manager else "unhealthy",
                "changenow": "healthy" if changenow_client else "unhealthy",
                "cloudtasks": "healthy" if cloudtasks_client else "unhealthy"
            }
        }), 200

    except Exception as e:
        print(f"❌ [HEALTH] Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "service": "PGP_HOSTPAY2_v1 ChangeNow Status Checker",
            "error": str(e)
        }), 503


# ============================================================================
# FLASK ENTRYPOINT
# ============================================================================

if __name__ == "__main__":
    print(f"🚀 [APP] Starting PGP_HOSTPAY2_v1 on port 8080")
    app.run(host="0.0.0.0", port=8080, debug=False)
