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
from changenow_client import ChangeNowClient

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

# Initialize ChangeNow client
try:
    changenow_api_key = config.get('changenow_api_key')

    if not changenow_api_key:
        raise ValueError("ChangeNow API key not available")

    changenow_client = ChangeNowClient(changenow_api_key)
    print(f"✅ [APP] ChangeNow client initialized")
except Exception as e:
    print(f"❌ [APP] Failed to initialize ChangeNow client: {e}")
    changenow_client = None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _route_batch_callback(
    batch_conversion_id: str,
    cn_api_id: str,
    tx_hash: str,
    actual_usdt_received: float
) -> bool:
    """
    Route batch conversion callback to GCMicroBatchProcessor.

    This function:
    1. Encrypts response token with batch data
    2. Enqueues callback task to MicroBatchProcessor via Cloud Tasks

    Args:
        batch_conversion_id: UUID of the batch conversion
        cn_api_id: ChangeNow API transaction ID
        tx_hash: Ethereum transaction hash
        actual_usdt_received: Actual USDT received from ChangeNow

    Returns:
        True if callback enqueued successfully, False otherwise
    """
    try:
        print(f"📤 [BATCH_CALLBACK] Preparing callback to GCMicroBatchProcessor")
        print(f"🆔 [BATCH_CALLBACK] Batch ID: {batch_conversion_id}")
        print(f"💰 [BATCH_CALLBACK] Actual USDT: ${actual_usdt_received}")

        # Validate token manager
        if not token_manager:
            print(f"❌ [BATCH_CALLBACK] Token manager not available")
            return False

        # Encrypt response token for MicroBatchProcessor
        response_token = token_manager.encrypt_gchostpay1_to_microbatch_response_token(
            batch_conversion_id=batch_conversion_id,
            cn_api_id=cn_api_id,
            tx_hash=tx_hash,
            actual_usdt_received=actual_usdt_received
        )

        if not response_token:
            print(f"❌ [BATCH_CALLBACK] Failed to encrypt response token")
            return False

        print(f"✅ [BATCH_CALLBACK] Response token encrypted")

        # Validate Cloud Tasks client and config
        if not cloudtasks_client:
            print(f"❌ [BATCH_CALLBACK] Cloud Tasks client not available")
            return False

        microbatch_response_queue = config.get('microbatch_response_queue')
        microbatch_url = config.get('microbatch_url')

        if not microbatch_response_queue or not microbatch_url:
            print(f"❌ [BATCH_CALLBACK] MicroBatchProcessor config incomplete")
            return False

        # Prepare callback payload
        payload = {
            'token': response_token
        }

        # Append endpoint path to base URL
        callback_url = f"{microbatch_url}/swap-executed"
        print(f"📡 [BATCH_CALLBACK] Enqueueing callback to: {callback_url}")

        # Enqueue callback task using create_task()
        task_name = cloudtasks_client.create_task(
            queue_name=microbatch_response_queue,
            target_url=callback_url,
            payload=payload
        )

        if task_name:
            print(f"✅ [BATCH_CALLBACK] Callback enqueued successfully")
            print(f"🆔 [BATCH_CALLBACK] Task name: {task_name}")
            return True
        else:
            print(f"❌ [BATCH_CALLBACK] Failed to enqueue callback")
            return False

    except Exception as e:
        print(f"❌ [BATCH_CALLBACK] Unexpected error: {e}")
        return False


def _enqueue_delayed_callback_check(
    unique_id: str,
    cn_api_id: str,
    tx_hash: str,
    context: str,
    retry_count: int = 0,
    retry_after_seconds: int = 300
) -> bool:
    """
    Enqueue delayed callback check to retry ChangeNow query after swap completes.

    This handles the timing issue where ETH payment completes before ChangeNow
    swap finishes. We retry after 5 minutes to check if amountTo is available.

    Args:
        unique_id: Unique transaction ID (e.g., batch_xxx)
        cn_api_id: ChangeNow API transaction ID
        tx_hash: Ethereum transaction hash
        context: 'batch' or 'threshold'
        retry_count: Current retry attempt (max 3)
        retry_after_seconds: Delay before retry (default 300 = 5 minutes)

    Returns:
        True if retry enqueued successfully, False otherwise
    """
    try:
        # Check max retries
        if retry_count >= 3:
            print(f"❌ [RETRY_ENQUEUE] Max retries reached ({retry_count}/3) for {unique_id}")
            print(f"⚠️ [RETRY_ENQUEUE] Manual intervention required - ChangeNow swap not finishing")
            return False

        print(f"🔄 [RETRY_ENQUEUE] Scheduling retry #{retry_count + 1} in {retry_after_seconds}s")
        print(f"🆔 [RETRY_ENQUEUE] Unique ID: {unique_id}")
        print(f"🆔 [RETRY_ENQUEUE] CN API ID: {cn_api_id}")

        # Validate Cloud Tasks client
        if not cloudtasks_client:
            print(f"❌ [RETRY_ENQUEUE] Cloud Tasks client not available")
            return False

        # Get queue configuration
        gchostpay1_response_queue = config.get('gchostpay1_response_queue')
        gchostpay1_url = config.get('gchostpay1_url')

        if not gchostpay1_response_queue or not gchostpay1_url:
            print(f"❌ [RETRY_ENQUEUE] GCHostPay1 response queue config missing")
            return False

        # Encrypt retry token
        if not token_manager:
            print(f"❌ [RETRY_ENQUEUE] Token manager not available")
            return False

        retry_token = token_manager.encrypt_gchostpay1_retry_token(
            unique_id=unique_id,
            cn_api_id=cn_api_id,
            tx_hash=tx_hash,
            context=context,
            retry_count=retry_count + 1
        )

        if not retry_token:
            print(f"❌ [RETRY_ENQUEUE] Failed to encrypt retry token")
            return False

        # Prepare retry URL
        retry_url = f"{gchostpay1_url}/retry-callback-check"
        print(f"📡 [RETRY_ENQUEUE] Enqueueing retry to: {retry_url}")

        # Enqueue retry task with delay
        task_name = cloudtasks_client.enqueue_gchostpay1_retry_callback(
            queue_name=gchostpay1_response_queue,
            target_url=retry_url,
            encrypted_token=retry_token,
            delay_seconds=retry_after_seconds
        )

        if task_name:
            print(f"✅ [RETRY_ENQUEUE] Retry task enqueued (will execute in {retry_after_seconds}s)")
            return True
        else:
            print(f"❌ [RETRY_ENQUEUE] Failed to enqueue retry task")
            return False

    except Exception as e:
        print(f"❌ [RETRY_ENQUEUE] Unexpected error: {e}")
        import traceback
        print(f"❌ [RETRY_ENQUEUE] Traceback: {traceback.format_exc()}")
        return False


# ============================================================================
# ENDPOINT 1: POST / - Main webhook (from GCSplit1)
# ============================================================================

@app.route("/", methods=["POST"])
def main_webhook():
    """
    Main webhook endpoint for receiving payment split requests.

    Supports TWO token types:
    1. GCSplit1 → GCHostPay1 (instant payouts with unique_id)
    2. GCAccumulator → GCHostPay1 (threshold payouts with accumulation_id and context)

    Flow:
    1. Decode & verify token (try GCSplit1, fallback to GCAccumulator)
    2. Extract: unique_id/accumulation_id, cn_api_id, from_currency, from_network, from_amount, payin_address, context
    3. Check database for duplicate
    4. Encrypt token for GCHostPay2 (status check)
    5. Enqueue to GCHostPay2 via Cloud Tasks

    Returns:
        JSON response with status
    """
    try:
        print(f"🎯 [ENDPOINT_1] Payment request received")

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

        # Try decrypting as GCSplit1 token first (instant payouts)
        decrypted_data = None
        token_source = None
        unique_id = None
        accumulation_id = None
        batch_conversion_id = None
        context = 'instant'  # Default context

        try:
            decrypted_data = token_manager.decrypt_gcsplit1_to_gchostpay1_token(token)
            if decrypted_data:
                token_source = 'gcsplit1'
                unique_id = decrypted_data['unique_id']
                context = 'instant'
                print(f"✅ [ENDPOINT_1] GCSplit1 token decoded (instant payout)")
        except Exception as e:
            print(f"⚠️ [ENDPOINT_1] Not a GCSplit1 token: {e}")

        # If GCSplit1 decryption failed, try GCAccumulator token (threshold payouts)
        if not decrypted_data:
            try:
                decrypted_data = token_manager.decrypt_accumulator_to_gchostpay1_token(token)
                if decrypted_data:
                    token_source = 'gcaccumulator'
                    accumulation_id = decrypted_data['accumulation_id']
                    context = decrypted_data.get('context', 'threshold')
                    # Create a unique_id for database tracking (use accumulation_id)
                    unique_id = f"acc_{accumulation_id}"
                    print(f"✅ [ENDPOINT_1] GCAccumulator token decoded (threshold payout)")
            except Exception as e:
                print(f"⚠️ [ENDPOINT_1] Not a GCAccumulator token: {e}")

        # If still no match, try GCMicroBatchProcessor token (batch conversions)
        if not decrypted_data:
            try:
                decrypted_data = token_manager.decrypt_microbatch_to_gchostpay1_token(token)
                if decrypted_data:
                    token_source = 'gcmicrobatchprocessor'
                    batch_conversion_id = decrypted_data['batch_conversion_id']
                    context = decrypted_data.get('context', 'batch')
                    # Create a unique_id for database tracking (use batch_conversion_id)
                    unique_id = f"batch_{batch_conversion_id}"
                    print(f"✅ [ENDPOINT_1] GCMicroBatchProcessor token decoded (batch conversion)")
            except Exception as e:
                print(f"❌ [ENDPOINT_1] Not a GCMicroBatchProcessor token either: {e}")
                abort(401, f"Invalid token: could not decrypt as GCSplit1, GCAccumulator, or GCMicroBatchProcessor token")

        # At this point, decrypted_data must be valid
        if not decrypted_data:
            print(f"❌ [ENDPOINT_1] Failed to decrypt token")
            abort(401, "Invalid token")

        # Extract common fields
        cn_api_id = decrypted_data['cn_api_id']
        from_currency = decrypted_data['from_currency']
        from_network = decrypted_data['from_network']
        from_amount = decrypted_data['from_amount']
        payin_address = decrypted_data['payin_address']

        # Extract actual/estimated amounts if available (for proper auditing)
        actual_eth_amount = decrypted_data.get('actual_eth_amount', 0.0)
        estimated_eth_amount = decrypted_data.get('estimated_eth_amount', 0.0)

        print(f"📋 [ENDPOINT_1] Token source: {token_source}")
        print(f"📋 [ENDPOINT_1] Context: {context}")
        print(f"🆔 [ENDPOINT_1] Unique ID: {unique_id}")
        if accumulation_id:
            print(f"🆔 [ENDPOINT_1] Accumulation ID: {accumulation_id}")
        if batch_conversion_id:
            print(f"🆔 [ENDPOINT_1] Batch Conversion ID: {batch_conversion_id}")
        print(f"🆔 [ENDPOINT_1] CN API ID: {cn_api_id}")
        print(f"💰 [ENDPOINT_1] Amount: {from_amount} {from_currency.upper()}")
        print(f"🏦 [ENDPOINT_1] Payin Address: {payin_address}")

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

        # Determine context based on unique_id
        # If unique_id starts with "acc_", it's from GCAccumulator (threshold payout)
        # Otherwise, it's from GCSplit1 (instant payout)
        context = 'threshold' if unique_id.startswith('acc_') else 'instant'
        print(f"📋 [ENDPOINT_2] Detected context: {context}")

        # Encrypt token for GCHostPay3 (payment execution) with context
        encrypted_token_payment = token_manager.encrypt_gchostpay1_to_gchostpay3_token(
            unique_id=unique_id,
            cn_api_id=cn_api_id,
            from_currency=from_currency,
            from_network=from_network,
            from_amount=from_amount,
            payin_address=payin_address,
            context=context
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

        # Detect context from unique_id prefix
        # - batch_* = Micro-batch conversion context
        # - acc_* = Accumulator threshold payout context
        # - regular = Instant conversion context (no callback needed)
        context = None
        if unique_id.startswith('batch_'):
            context = 'batch'
            print(f"🔀 [ENDPOINT_3] Detected batch conversion context")
        elif unique_id.startswith('acc_'):
            context = 'threshold'
            print(f"🔀 [ENDPOINT_3] Detected threshold payout context")
        else:
            context = 'instant'
            print(f"🔀 [ENDPOINT_3] Detected instant conversion context (no callback needed)")

        # Query ChangeNow API for actual USDT received (critical for batch conversions)
        actual_usdt_received = None
        if context in ['batch', 'threshold']:
            if not changenow_client:
                print(f"❌ [ENDPOINT_3] ChangeNow client not available, cannot query transaction status")
            else:
                try:
                    print(f"🔍 [ENDPOINT_3] Querying ChangeNow for actual USDT received...")
                    cn_status = changenow_client.get_transaction_status(cn_api_id)

                    if cn_status:
                        status = cn_status.get('status')
                        amount_to_decimal = cn_status.get('amountTo')  # This is a Decimal now

                        print(f"📊 [ENDPOINT_3] ChangeNow status: {status}")

                        # Check if swap is finished AND has actual amounts
                        if status == 'finished' and amount_to_decimal and float(amount_to_decimal) > 0:
                            actual_usdt_received = float(amount_to_decimal)
                            print(f"✅ [ENDPOINT_3] Actual USDT received: ${actual_usdt_received}")

                        elif status in ['waiting', 'confirming', 'exchanging', 'sending']:
                            # Swap still in progress - ENQUEUE RETRY
                            print(f"⏳ [ENDPOINT_3] ChangeNow swap not finished yet: {status}")
                            print(f"⚠️ [ENDPOINT_3] amountTo not available yet")
                            print(f"🔄 [ENDPOINT_3] Enqueueing delayed retry to check when swap completes")

                            # Enqueue retry task to check again after 5 minutes
                            _enqueue_delayed_callback_check(
                                unique_id=unique_id,
                                cn_api_id=cn_api_id,
                                tx_hash=tx_hash,
                                context=context,
                                retry_count=0,  # First retry
                                retry_after_seconds=300  # 5 minutes
                            )

                        elif status == 'finished' and float(amount_to_decimal) == 0:
                            # Finished but zero amount - unexpected
                            print(f"⚠️ [ENDPOINT_3] ChangeNow status=finished but amountTo=0 (UNEXPECTED)")
                            print(f"⚠️ [ENDPOINT_3] This may indicate a ChangeNow API issue")

                        else:
                            # Failed, refunded, or unknown status
                            print(f"❌ [ENDPOINT_3] ChangeNow transaction in unexpected state: {status}")

                    else:
                        print(f"❌ [ENDPOINT_3] ChangeNow query returned no data")

                except Exception as e:
                    print(f"❌ [ENDPOINT_3] ChangeNow query error: {e}")
                    import traceback
                    print(f"❌ [ENDPOINT_3] Traceback: {traceback.format_exc()}")

        # Route callback based on context
        if context == 'batch' and actual_usdt_received is not None:
            # Extract batch_conversion_id from unique_id (format: batch_{uuid})
            batch_conversion_id = unique_id.replace('batch_', '')
            print(f"🎯 [ENDPOINT_3] Routing batch callback to GCMicroBatchProcessor")
            print(f"🆔 [ENDPOINT_3] Batch conversion ID: {batch_conversion_id}")

            # Route batch callback
            _route_batch_callback(
                batch_conversion_id=batch_conversion_id,
                cn_api_id=cn_api_id,
                tx_hash=tx_hash,
                actual_usdt_received=actual_usdt_received
            )

        elif context == 'threshold' and actual_usdt_received is not None:
            print(f"🎯 [ENDPOINT_3] Routing threshold callback to GCAccumulator")
            # TODO: Implement threshold callback routing when needed
            print(f"⚠️ [ENDPOINT_3] Threshold callback not yet implemented")

        elif context == 'instant':
            print(f"✅ [ENDPOINT_3] Instant conversion complete, no callback needed")
        else:
            print(f"⚠️ [ENDPOINT_3] No callback sent (context={context}, actual_usdt_received={actual_usdt_received})")

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
# ENDPOINT 4: POST /retry-callback-check - Retry ChangeNow query (internal)
# ============================================================================

@app.route("/retry-callback-check", methods=["POST"])
def retry_callback_check():
    """
    Retry endpoint to re-query ChangeNow for actual USDT received.

    This endpoint is called by Cloud Tasks after a delay (5 minutes) to check
    if the ChangeNow swap has completed and amountTo is now available.

    Flow:
    1. Decrypt retry token
    2. Extract: unique_id, cn_api_id, tx_hash, context, retry_count
    3. Query ChangeNow API again
    4. If finished: Send callback to MicroBatchProcessor
    5. If still in progress: Enqueue another retry (max 3 total)

    Returns:
        JSON response with status
    """
    try:
        print(f"🔄 [ENDPOINT_4] Retry callback check received")

        # Parse JSON payload
        try:
            request_data = request.get_json()
            if not request_data:
                abort(400, "Invalid JSON payload")
        except Exception as e:
            print(f"❌ [ENDPOINT_4] JSON parsing error: {e}")
            abort(400, "Malformed JSON payload")

        token = request_data.get('token')
        if not token:
            print(f"❌ [ENDPOINT_4] Missing token")
            abort(400, "Missing token")

        # Decrypt retry token
        if not token_manager:
            print(f"❌ [ENDPOINT_4] Token manager not available")
            abort(500, "Service configuration error")

        try:
            decrypted_data = token_manager.decrypt_gchostpay1_retry_token(token)
            if not decrypted_data:
                print(f"❌ [ENDPOINT_4] Failed to decrypt retry token")
                abort(401, "Invalid token")

            unique_id = decrypted_data['unique_id']
            cn_api_id = decrypted_data['cn_api_id']
            tx_hash = decrypted_data['tx_hash']
            context = decrypted_data['context']
            retry_count = decrypted_data['retry_count']

            print(f"✅ [ENDPOINT_4] Retry token decoded successfully")
            print(f"🆔 [ENDPOINT_4] Unique ID: {unique_id}")
            print(f"🆔 [ENDPOINT_4] CN API ID: {cn_api_id}")
            print(f"🔁 [ENDPOINT_4] Retry attempt: {retry_count}/3")

        except Exception as e:
            print(f"❌ [ENDPOINT_4] Token validation error: {e}")
            abort(400, f"Token error: {e}")

        # Query ChangeNow API again
        actual_usdt_received = None
        if not changenow_client:
            print(f"❌ [ENDPOINT_4] ChangeNow client not available")
            abort(500, "ChangeNow client unavailable")

        try:
            print(f"🔍 [ENDPOINT_4] Re-querying ChangeNow for actual USDT received...")
            cn_status = changenow_client.get_transaction_status(cn_api_id)

            if cn_status:
                status = cn_status.get('status')
                amount_to_decimal = cn_status.get('amountTo')

                print(f"📊 [ENDPOINT_4] ChangeNow status: {status}")

                if status == 'finished' and amount_to_decimal and float(amount_to_decimal) > 0:
                    # ✅ Swap finally complete!
                    actual_usdt_received = float(amount_to_decimal)
                    print(f"✅ [ENDPOINT_4] Actual USDT received: ${actual_usdt_received}")
                    print(f"🎉 [ENDPOINT_4] ChangeNow swap completed after retry!")

                elif status in ['waiting', 'confirming', 'exchanging', 'sending']:
                    # ⏳ Still in progress - retry again if under limit
                    print(f"⏳ [ENDPOINT_4] ChangeNow swap still in progress: {status}")

                    if retry_count < 3:
                        print(f"🔄 [ENDPOINT_4] Enqueueing another retry (attempt {retry_count + 1})")
                        _enqueue_delayed_callback_check(
                            unique_id=unique_id,
                            cn_api_id=cn_api_id,
                            tx_hash=tx_hash,
                            context=context,
                            retry_count=retry_count,
                            retry_after_seconds=300  # 5 minutes
                        )

                        return jsonify({
                            "status": "retry_scheduled",
                            "message": f"Swap still in progress, retry #{retry_count + 1} scheduled",
                            "unique_id": unique_id,
                            "cn_api_id": cn_api_id,
                            "changenow_status": status
                        }), 200
                    else:
                        print(f"❌ [ENDPOINT_4] Max retries exceeded - swap still not finished")
                        print(f"⚠️ [ENDPOINT_4] Manual intervention required")

                        return jsonify({
                            "status": "max_retries_exceeded",
                            "message": "ChangeNow swap not finished after 3 retries",
                            "unique_id": unique_id,
                            "cn_api_id": cn_api_id,
                            "changenow_status": status
                        }), 500

                else:
                    # ❌ Failed or unexpected status
                    print(f"❌ [ENDPOINT_4] ChangeNow transaction in unexpected state: {status}")

                    return jsonify({
                        "status": "failed",
                        "message": f"ChangeNow transaction failed: {status}",
                        "unique_id": unique_id,
                        "cn_api_id": cn_api_id,
                        "changenow_status": status
                    }), 500

        except Exception as e:
            print(f"❌ [ENDPOINT_4] ChangeNow query error: {e}")
            import traceback
            print(f"❌ [ENDPOINT_4] Traceback: {traceback.format_exc()}")
            abort(500, f"ChangeNow query failed: {e}")

        # If we have actual_usdt_received, send callback
        if actual_usdt_received is not None and actual_usdt_received > 0:
            if context == 'batch':
                # Extract batch_conversion_id from unique_id
                batch_conversion_id = unique_id.replace('batch_', '')
                print(f"🎯 [ENDPOINT_4] Routing batch callback to GCMicroBatchProcessor")

                callback_success = _route_batch_callback(
                    batch_conversion_id=batch_conversion_id,
                    cn_api_id=cn_api_id,
                    tx_hash=tx_hash,
                    actual_usdt_received=actual_usdt_received
                )

                if callback_success:
                    print(f"✅ [ENDPOINT_4] Batch callback sent successfully")
                    return jsonify({
                        "status": "success",
                        "message": "Callback sent to MicroBatchProcessor",
                        "unique_id": unique_id,
                        "actual_usdt_received": actual_usdt_received
                    }), 200
                else:
                    print(f"❌ [ENDPOINT_4] Failed to send batch callback")
                    return jsonify({
                        "status": "callback_failed",
                        "message": "Could not send callback to MicroBatchProcessor"
                    }), 500

            elif context == 'threshold':
                print(f"🎯 [ENDPOINT_4] Routing threshold callback to GCAccumulator")
                # TODO: Implement threshold callback
                print(f"⚠️ [ENDPOINT_4] Threshold callback not yet implemented")
                return jsonify({
                    "status": "not_implemented",
                    "message": "Threshold callback not yet implemented"
                }), 501
        else:
            print(f"⚠️ [ENDPOINT_4] No callback sent - actual_usdt_received unavailable")
            return jsonify({
                "status": "no_callback",
                "message": "Actual USDT received not available"
            }), 200

    except Exception as e:
        print(f"❌ [ENDPOINT_4] Unexpected error: {e}")
        import traceback
        print(f"❌ [ENDPOINT_4] Traceback: {traceback.format_exc()}")
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
