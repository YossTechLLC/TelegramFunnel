#!/usr/bin/env python
"""
PGP_MICROBATCHPROCESSOR_v1: Micro-Batch Conversion Service
Triggered by Cloud Scheduler every 15 minutes.
Checks if total pending USD >= threshold, then creates batch ETH→USDT swap.
"""
import sys
import time
import uuid
from decimal import Decimal
from flask import Flask, request, abort, jsonify

from config_manager import ConfigManager
from database_manager import DatabaseManager
from token_manager import TokenManager
from cloudtasks_client import CloudTasksClient
from changenow_client import ChangeNowClient

app = Flask(__name__)

# Initialize managers
print(f"🚀 [APP] Initializing PGP_MICROBATCHPROCESSOR_v1 Micro-Batch Conversion Service")
config_manager = ConfigManager()
config = config_manager.initialize_config()

# Initialize database manager
try:
    db_manager = DatabaseManager(
        instance_connection_name=config['instance_connection_name'],
        db_name=config['db_name'],
        db_user=config['db_user'],
        db_password=config['db_password']
    )
    print(f"✅ [APP] Database manager initialized")
except Exception as e:
    print(f"❌ [APP] Failed to initialize database manager: {e}")
    db_manager = None

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
    changenow_api_key = config.get('changenow_api_key')
    if not changenow_api_key:
        raise ValueError("CHANGENOW_API_KEY not available")
    changenow_client = ChangeNowClient(changenow_api_key)
    print(f"✅ [APP] ChangeNow client initialized")
except Exception as e:
    print(f"❌ [APP] Failed to initialize ChangeNow client: {e}")
    changenow_client = None


@app.route("/check-threshold", methods=["POST"])
def check_threshold():
    """
    Main endpoint for threshold checking (triggered by Cloud Scheduler every 15 minutes).

    Flow:
    1. Fetch threshold from Google Cloud Secret
    2. Query total pending USD
    3. If total >= threshold:
       a. Create ChangeNow ETH→USDT swap
       b. Update all pending records to 'swapping'
       c. Enqueue to PGP_HOSTPAY1_v1 for execution
    4. Return summary

    Returns:
        JSON response with processing summary
    """
    try:
        print(f"🎯 [ENDPOINT] Threshold check triggered")
        print(f"⏰ [ENDPOINT] Timestamp: {int(time.time())}")
        sys.stdout.flush()  # Force immediate log output

        # Validate managers
        if not db_manager or not token_manager or not cloudtasks_client or not changenow_client:
            print(f"❌ [ENDPOINT] Required managers not available")
            sys.stdout.flush()
            return jsonify({
                "status": "error",
                "message": "Service not properly initialized"
            }), 500

        # Get threshold from config (already fetched at startup)
        threshold = config.get('micro_batch_threshold')
        if not threshold:
            print(f"❌ [ENDPOINT] Threshold not available in config")
            sys.stdout.flush()
            return jsonify({
                "status": "error",
                "message": "Threshold configuration missing"
            }), 500
        print(f"💰 [ENDPOINT] Using threshold: ${threshold}")

        # Query total pending USD and ACTUAL ETH
        print(f"🔍 [ENDPOINT] Querying total pending USD")
        total_pending = db_manager.get_total_pending_usd()
        print(f"📊 [ENDPOINT] Total pending: ${total_pending}")

        print(f"🔍 [ENDPOINT] Querying total pending ACTUAL ETH")
        total_actual_eth = db_manager.get_total_pending_actual_eth()
        print(f"💎 [ENDPOINT] Total ACTUAL ETH: {total_actual_eth} ETH")

        # Check if threshold reached
        if total_pending < threshold:
            print(f"⏳ [ENDPOINT] Total pending (${total_pending}) < Threshold (${threshold}) - no action")
            return jsonify({
                "status": "success",
                "message": "Below threshold, no batch conversion needed",
                "total_pending": str(total_pending),
                "threshold": str(threshold),
                "batch_created": False
            }), 200

        print(f"✅ [ENDPOINT] Threshold reached! Creating batch conversion")
        print(f"📊 [ENDPOINT] Total pending: ${total_pending} >= Threshold: ${threshold}")

        # Fetch all pending records
        print(f"🔍 [ENDPOINT] Fetching all pending payment records")
        pending_records = db_manager.get_all_pending_records()

        if not pending_records:
            print(f"⚠️ [ENDPOINT] No pending records found (race condition?)")
            return jsonify({
                "status": "success",
                "message": "No pending records to process",
                "batch_created": False
            }), 200

        print(f"📊 [ENDPOINT] Found {len(pending_records)} pending record(s)")

        # Generate batch conversion ID
        batch_conversion_id = str(uuid.uuid4())
        print(f"🆔 [ENDPOINT] Generated batch conversion ID: {batch_conversion_id}")

        # Get host wallet address
        host_wallet_usdt = config.get('host_wallet_usdt_address')
        if not host_wallet_usdt:
            print(f"❌ [ENDPOINT] Host USDT wallet address not configured")
            sys.stdout.flush()
            return jsonify({
                "status": "error",
                "message": "Host wallet configuration missing"
            }), 500

        print(f"🏦 [ENDPOINT] Host USDT wallet: {host_wallet_usdt}")

        # Determine ETH amount to use for swap
        # Priority: ACTUAL ETH > USD estimate fallback
        if total_actual_eth > 0:
            eth_for_swap = total_actual_eth
            print(f"✅ [ENDPOINT] Using ACTUAL ETH from NowPayments: {eth_for_swap} ETH")
            print(f"📊 [ENDPOINT] This represents ${total_pending} USD in accumulated payments")
        else:
            print(f"⚠️ [ENDPOINT] WARNING: No actual ETH found, falling back to USD→ETH estimation")
            print(f"📊 [ENDPOINT] Step 1: Converting USD to ETH equivalent")
            print(f"💰 [ENDPOINT] Total pending: ${total_pending} USD")
            print(f"🔄 [ENDPOINT] Calling ChangeNow estimate API: USDT → ETH")

            # Fallback: Use USDT→ETH estimate to find ETH equivalent of USD amount
            estimate_response = changenow_client.get_estimated_amount_v2_with_retry(
                from_currency='usdt',
                to_currency='eth',
                from_network='eth',
                to_network='eth',
                from_amount=str(total_pending),
                flow='standard',
                type_='direct'
            )

            if not estimate_response or 'toAmount' not in estimate_response:
                print(f"❌ [ENDPOINT] Failed to get ETH estimate from ChangeNow")
                sys.stdout.flush()
                return jsonify({
                    "status": "error",
                    "message": "Failed to calculate ETH equivalent"
                }), 500

            eth_for_swap = estimate_response['toAmount']
            print(f"✅ [ENDPOINT] USD→ETH conversion estimate received")
            print(f"💰 [ENDPOINT] ${total_pending} USD ≈ {eth_for_swap} ETH")

        # Create ETH→USDT swap with determined ETH amount
        print(f"📊 [ENDPOINT] Creating ChangeNow swap: ETH → USDT")
        print(f"💰 [ENDPOINT] Swap amount: {eth_for_swap} ETH → ~${total_pending} USDT")

        swap_result = changenow_client.create_fixed_rate_transaction_with_retry(
            from_currency='eth',
            to_currency='usdt',
            from_amount=float(eth_for_swap),  # ✅ Use ACTUAL ETH or fallback estimate
            address=host_wallet_usdt,
            from_network='eth',
            to_network='eth'  # USDT on Ethereum network (ERC-20)
        )

        if not swap_result or 'id' not in swap_result:
            print(f"❌ [ENDPOINT] Failed to create ChangeNow swap")
            sys.stdout.flush()
            return jsonify({
                "status": "error",
                "message": "ChangeNow swap creation failed"
            }), 500

        cn_api_id = swap_result['id']
        payin_address = swap_result.get('payinAddress')

        print(f"✅ [ENDPOINT] ChangeNow swap created successfully")
        print(f"🆔 [ENDPOINT] ChangeNow ID: {cn_api_id}")
        print(f"📬 [ENDPOINT] Payin address: {payin_address}")

        # Create batch_conversions record
        print(f"💾 [ENDPOINT] Creating batch_conversions record")
        batch_created = db_manager.create_batch_conversion(
            batch_conversion_id=batch_conversion_id,
            total_eth_usd=total_pending,
            threshold=threshold,
            cn_api_id=cn_api_id,
            payin_address=payin_address
        )

        if not batch_created:
            print(f"❌ [ENDPOINT] Failed to create batch_conversions record")
            sys.stdout.flush()
            return jsonify({
                "status": "error",
                "message": "Database insertion failed"
            }), 500

        # Update all pending records to 'swapping'
        print(f"💾 [ENDPOINT] Updating all pending records to 'swapping' status")
        records_updated = db_manager.update_records_to_swapping(batch_conversion_id)

        if not records_updated:
            print(f"❌ [ENDPOINT] Failed to update records to swapping")
            sys.stdout.flush()
            return jsonify({
                "status": "error",
                "message": "Failed to update records"
            }), 500

        print(f"✅ [ENDPOINT] Updated {len(pending_records)} record(s) to 'swapping' status")

        # Enqueue to PGP_HOSTPAY1_v1 for execution
        print(f"📤 [ENDPOINT] Enqueueing batch execution task to PGP_HOSTPAY1_v1")

        pgp_hostpay1_batch_queue = config.get('pgp_hostpay1_batch_queue')
        pgp_hostpay1_url = config.get('pgp_hostpay1_url')

        if not pgp_hostpay1_batch_queue or not pgp_hostpay1_url:
            print(f"❌ [ENDPOINT] PGP_HOSTPAY1_v1 batch configuration missing")
            sys.stdout.flush()
            return jsonify({
                "status": "error",
                "message": "Service configuration error"
            }), 500

        # Encrypt token for PGP_HOSTPAY1_v1
        print(f"🔐 [ENDPOINT] Encrypting token for PGP_HOSTPAY1_v1")
        print(f"💰 [ENDPOINT] Passing ACTUAL ETH amount: {eth_for_swap} ETH")

        encrypted_token = token_manager.encrypt_microbatch_to_pgp_hostpay1_token(
            batch_conversion_id=batch_conversion_id,
            cn_api_id=cn_api_id,
            from_currency='eth',
            from_network='eth',
            from_amount=float(eth_for_swap),  # ✅ Use ACTUAL ETH, not USD!
            payin_address=payin_address
        )

        if not encrypted_token:
            print(f"❌ [ENDPOINT] Failed to encrypt token")
            sys.stdout.flush()
            return jsonify({
                "status": "error",
                "message": "Token encryption failed"
            }), 500

        task_name = cloudtasks_client.enqueue_pgp_hostpay1_batch_execution(
            queue_name=pgp_hostpay1_batch_queue,
            target_url=f"{pgp_hostpay1_url}/",
            encrypted_token=encrypted_token
        )

        if not task_name:
            print(f"❌ [ENDPOINT] Failed to create Cloud Task")
            sys.stdout.flush()
            return jsonify({
                "status": "error",
                "message": "Failed to enqueue execution task"
            }), 500

        print(f"✅ [ENDPOINT] Batch execution task enqueued successfully")
        print(f"🆔 [ENDPOINT] Task: {task_name}")
        print(f"🎉 [ENDPOINT] Batch conversion process initiated successfully")

        return jsonify({
            "status": "success",
            "message": "Batch conversion created successfully",
            "total_pending": str(total_pending),
            "threshold": str(threshold),
            "batch_conversion_id": batch_conversion_id,
            "cn_api_id": cn_api_id,
            "payment_count": len(pending_records),
            "task_name": task_name,
            "batch_created": True
        }), 200

    except Exception as e:
        print(f"❌ [ENDPOINT] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        return jsonify({
            "status": "error",
            "message": f"Internal server error: {str(e)}"
        }), 500


@app.route("/swap-executed", methods=["POST"])
def swap_executed():
    """
    Callback endpoint from PGP_HOSTPAY1_v1 after ETH payment executed.

    Flow:
    1. Decrypt token from PGP_HOSTPAY1_v1
    2. Fetch all pending records for batch_conversion_id
    3. Calculate proportional USDT distribution
    4. Update each record with usdt_share
    5. Mark batch as completed

    Returns:
        JSON response with distribution summary
    """
    try:
        print(f"🎯 [ENDPOINT] Swap execution callback received")
        print(f"⏰ [ENDPOINT] Timestamp: {int(time.time())}")

        # Validate managers
        if not db_manager or not token_manager:
            print(f"❌ [ENDPOINT] Required managers not available")
            sys.stdout.flush()
            return jsonify({
                "status": "error",
                "message": "Service not properly initialized"
            }), 500

        # Parse request data
        try:
            request_data = request.get_json()
            if not request_data:
                sys.stdout.flush()
                return jsonify({
                    "status": "error",
                    "message": "Invalid JSON payload"
                }), 400
        except Exception as e:
            print(f"❌ [ENDPOINT] JSON parsing error: {e}")
            sys.stdout.flush()
            return jsonify({
                "status": "error",
                "message": "Malformed JSON payload"
            }), 400

        encrypted_token = request_data.get('token')
        if not encrypted_token:
            print(f"❌ [ENDPOINT] Missing encrypted token")
            sys.stdout.flush()
            return jsonify({
                "status": "error",
                "message": "Missing token"
            }), 400

        print(f"🔐 [ENDPOINT] Decrypting token from PGP_HOSTPAY1_v1")
        decrypted_data = token_manager.decrypt_pgp_hostpay1_to_microbatch_token(encrypted_token)

        if not decrypted_data:
            print(f"❌ [ENDPOINT] Token decryption failed")
            sys.stdout.flush()
            return jsonify({
                "status": "error",
                "message": "Invalid token"
            }), 401

        batch_conversion_id = decrypted_data.get('batch_conversion_id')
        cn_api_id = decrypted_data.get('cn_api_id')
        tx_hash = decrypted_data.get('tx_hash')
        actual_usdt_received = Decimal(str(decrypted_data.get('actual_usdt_received')))

        print(f"✅ [ENDPOINT] Token decrypted successfully")
        print(f"🆔 [ENDPOINT] Batch Conversion ID: {batch_conversion_id}")
        print(f"🆔 [ENDPOINT] ChangeNow ID: {cn_api_id}")
        print(f"💰 [ENDPOINT] Actual USDT received: ${actual_usdt_received}")
        print(f"🔗 [ENDPOINT] TX Hash: {tx_hash}")

        # Fetch all records for this batch
        print(f"🔍 [ENDPOINT] Fetching records for batch conversion")
        batch_records = db_manager.get_records_by_batch(batch_conversion_id)

        if not batch_records:
            print(f"❌ [ENDPOINT] No records found for batch {batch_conversion_id}")
            sys.stdout.flush()
            return jsonify({
                "status": "error",
                "message": "Batch records not found"
            }), 404

        print(f"📊 [ENDPOINT] Found {len(batch_records)} record(s) in batch")

        # Distribute USDT proportionally
        print(f"💰 [ENDPOINT] Calculating proportional USDT distribution")
        distributions = db_manager.distribute_usdt_proportionally(
            pending_records=batch_records,
            actual_usdt_received=actual_usdt_received
        )

        if not distributions:
            print(f"❌ [ENDPOINT] Failed to calculate distributions")
            sys.stdout.flush()
            return jsonify({
                "status": "error",
                "message": "Distribution calculation failed"
            }), 500

        # Update each record with usdt_share
        print(f"💾 [ENDPOINT] Updating records with USDT shares")
        for distribution in distributions:
            record_id = distribution['id']
            usdt_share = distribution['usdt_share']

            success = db_manager.update_record_usdt_share(
                record_id=record_id,
                usdt_share=usdt_share,
                tx_hash=tx_hash
            )

            if success:
                print(f"✅ [ENDPOINT] Record {record_id}: ${usdt_share} USDT")
            else:
                print(f"❌ [ENDPOINT] Failed to update record {record_id}")

        # Finalize batch conversion
        print(f"💾 [ENDPOINT] Finalizing batch conversion")
        batch_finalized = db_manager.finalize_batch_conversion(
            batch_conversion_id=batch_conversion_id,
            actual_usdt_received=actual_usdt_received,
            tx_hash=tx_hash
        )

        if not batch_finalized:
            print(f"❌ [ENDPOINT] Failed to finalize batch conversion")
            sys.stdout.flush()
            return jsonify({
                "status": "error",
                "message": "Failed to finalize batch"
            }), 500

        print(f"✅ [ENDPOINT] Batch conversion finalized successfully")
        print(f"🎉 [ENDPOINT] Proportional distribution completed")

        return jsonify({
            "status": "success",
            "message": "Swap executed and USDT distributed successfully",
            "batch_conversion_id": batch_conversion_id,
            "actual_usdt_received": str(actual_usdt_received),
            "records_updated": len(distributions),
            "tx_hash": tx_hash
        }), 200

    except Exception as e:
        print(f"❌ [ENDPOINT] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        return jsonify({
            "status": "error",
            "message": f"Internal server error: {str(e)}"
        }), 500


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for monitoring."""
    return jsonify({
        "status": "healthy",
        "service": "PGP_MICROBATCHPROCESSOR_v1",
        "timestamp": int(time.time())
    }), 200


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
