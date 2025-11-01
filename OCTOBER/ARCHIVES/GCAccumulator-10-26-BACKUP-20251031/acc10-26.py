#!/usr/bin/env python
"""
GCAccumulator-10-26: Payment Accumulation Service
Receives payment data from GCWebhook1, converts to USDT immediately,
and stores in accumulation table to eliminate volatility risk.
"""
import time
from decimal import Decimal
from datetime import datetime
from flask import Flask, request, abort, jsonify

from config_manager import ConfigManager
from database_manager import DatabaseManager
from token_manager import TokenManager
from cloudtasks_client import CloudTasksClient

app = Flask(__name__)

# Initialize managers
print(f"🚀 [APP] Initializing GCAccumulator-10-26 Payment Accumulation Service")
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

# ChangeNow client removed - conversion now handled by GCSplit2 via Cloud Tasks


@app.route("/", methods=["POST"])
def accumulate_payment():
    """
    Main endpoint for accumulating payments.

    Flow:
    1. Receive payment data from GCWebhook1
    2. Calculate adjusted amount (after TP fee)
    3. Store payment with accumulated_eth (pending conversion)
    4. Queue task to GCSplit2 for ETH→USDT conversion
    5. Return success immediately (non-blocking)

    Returns:
        JSON response with status
    """
    try:
        print(f"🎯 [ENDPOINT] Payment accumulation request received")

        # Parse JSON payload
        try:
            request_data = request.get_json()
            if not request_data:
                abort(400, "Invalid JSON payload")
        except Exception as e:
            print(f"❌ [ENDPOINT] JSON parsing error: {e}")
            abort(400, "Malformed JSON payload")

        # Extract payment data
        user_id = request_data.get('user_id')
        client_id = request_data.get('client_id')
        wallet_address = request_data.get('wallet_address')
        payout_currency = request_data.get('payout_currency')
        payout_network = request_data.get('payout_network')
        payment_amount_usd = Decimal(str(request_data.get('payment_amount_usd')))
        subscription_id = request_data.get('subscription_id')
        payment_timestamp = request_data.get('payment_timestamp')

        print(f"👤 [ENDPOINT] User ID: {user_id}")
        print(f"🏢 [ENDPOINT] Client ID: {client_id}")
        print(f"💰 [ENDPOINT] Payment Amount: ${payment_amount_usd}")
        print(f"🎯 [ENDPOINT] Target: {payout_currency.upper()} on {payout_network.upper()}")

        # Calculate adjusted amount (remove TP fee like GCSplit1 does)
        tp_flat_fee = Decimal(config.get('tp_flat_fee', '3'))
        fee_amount = payment_amount_usd * (tp_flat_fee / Decimal('100'))
        adjusted_amount_usd = payment_amount_usd - fee_amount

        print(f"💸 [ENDPOINT] TP fee ({tp_flat_fee}%): ${fee_amount}")
        print(f"✅ [ENDPOINT] Adjusted amount: ${adjusted_amount_usd}")

        # Store accumulated_eth (the adjusted USD amount pending conversion)
        # Conversion will happen asynchronously via GCSplit2
        accumulated_eth = adjusted_amount_usd
        print(f"⏳ [ENDPOINT] Storing payment with accumulated_eth (pending conversion)")
        print(f"💰 [ENDPOINT] Accumulated ETH value: ${accumulated_eth}")

        # Write to payout_accumulation table
        if not db_manager:
            print(f"❌ [ENDPOINT] Database manager not available")
            abort(500, "Database unavailable")

        print(f"💾 [ENDPOINT] Inserting into payout_accumulation (pending conversion)")

        accumulation_id = db_manager.insert_payout_accumulation_pending(
            client_id=client_id,
            user_id=user_id,
            subscription_id=subscription_id,
            payment_amount_usd=payment_amount_usd,
            payment_currency='usd',
            payment_timestamp=payment_timestamp,
            accumulated_eth=accumulated_eth,
            client_wallet_address=wallet_address,
            client_payout_currency=payout_currency,
            client_payout_network=payout_network
        )

        if not accumulation_id:
            print(f"❌ [ENDPOINT] Failed to insert into database")
            abort(500, "Database insertion failed")

        print(f"✅ [ENDPOINT] Database insertion successful")
        print(f"🆔 [ENDPOINT] Accumulation ID: {accumulation_id}")

        # Queue task to GCSplit3 for ACTUAL ETH→USDT swap creation
        if not cloudtasks_client:
            print(f"❌ [ENDPOINT] Cloud Tasks client not available")
            abort(500, "Cloud Tasks unavailable")

        if not token_manager:
            print(f"❌ [ENDPOINT] Token manager not available")
            abort(500, "Token manager unavailable")

        gcsplit3_queue = config.get('gcsplit3_queue')
        gcsplit3_url = config.get('gcsplit3_url')
        host_wallet_usdt = config.get('host_wallet_usdt_address')

        if not gcsplit3_queue or not gcsplit3_url or not host_wallet_usdt:
            print(f"❌ [ENDPOINT] GCSplit3 configuration missing")
            abort(500, "Service configuration error")

        print(f"📤 [ENDPOINT] Queuing ETH→USDT SWAP task to GCSplit3")
        print(f"🏦 [ENDPOINT] Host USDT wallet: {host_wallet_usdt}")

        # Encrypt token for GCSplit3
        encrypted_token = token_manager.encrypt_accumulator_to_gcsplit3_token(
            accumulation_id=accumulation_id,
            client_id=client_id,
            eth_amount=float(accumulated_eth),
            usdt_wallet_address=host_wallet_usdt
        )

        if not encrypted_token:
            print(f"❌ [ENDPOINT] Failed to encrypt token")
            abort(500, "Token encryption failed")

        task_name = cloudtasks_client.enqueue_gcsplit3_eth_to_usdt_swap(
            queue_name=gcsplit3_queue,
            target_url=f"{gcsplit3_url}/eth-to-usdt",
            encrypted_token=encrypted_token
        )

        if not task_name:
            print(f"❌ [ENDPOINT] Failed to create Cloud Task")
            abort(500, "Failed to enqueue swap task")

        print(f"✅ [ENDPOINT] Swap task enqueued successfully")
        print(f"🆔 [ENDPOINT] Task: {task_name}")
        print(f"⏳ [ENDPOINT] Waiting for GCSplit3 to create swap, then GCHostPay will execute")

        print(f"🎉 [ENDPOINT] Payment accumulation completed successfully (swap pending)")

        return jsonify({
            "status": "success",
            "message": "Payment accumulated successfully, ETH→USDT swap pending",
            "accumulation_id": accumulation_id,
            "accumulated_eth": str(accumulated_eth),
            "swap_task": task_name,
            "conversion_status": "pending"
        }), 200

    except Exception as e:
        print(f"❌ [ENDPOINT] Unexpected error: {e}")
        return jsonify({
            "status": "error",
            "message": f"Processing error: {str(e)}"
        }), 500


@app.route("/swap-created", methods=["POST"])
def swap_created():
    """
    Receives response from GCSplit3 after ETH→USDT swap is created.

    Flow:
    1. Decrypt token from GCSplit3
    2. Extract ChangeNow transaction details
    3. Update database with conversion status = 'swapping'
    4. Queue task to GCHostPay1 for swap execution

    Returns:
        JSON response with status
    """
    try:
        print(f"🎯 [ENDPOINT] ETH→USDT swap created notification received")

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

        decrypted_data = token_manager.decrypt_gcsplit3_to_accumulator_token(encrypted_token)
        if not decrypted_data:
            print(f"❌ [ENDPOINT] Failed to decrypt token")
            abort(401, "Invalid token")

        # Extract data
        accumulation_id = decrypted_data['accumulation_id']
        client_id = decrypted_data['client_id']
        cn_api_id = decrypted_data['cn_api_id']
        from_amount = decrypted_data['from_amount']
        to_amount = decrypted_data['to_amount']
        payin_address = decrypted_data['payin_address']

        print(f"✅ [ENDPOINT] Swap created successfully")
        print(f"🆔 [ENDPOINT] Accumulation ID: {accumulation_id}")
        print(f"🆔 [ENDPOINT] CN API ID: {cn_api_id}")
        print(f"💰 [ENDPOINT] From: ${from_amount} ETH")
        print(f"💰 [ENDPOINT] To: ${to_amount} USDT")
        print(f"🏦 [ENDPOINT] Payin Address: {payin_address}")

        # Update database with conversion status
        if not db_manager:
            print(f"❌ [ENDPOINT] Database manager not available")
            abort(500, "Database unavailable")

        db_manager.update_accumulation_conversion_status(
            accumulation_id=accumulation_id,
            conversion_status='swapping',
            cn_api_id=cn_api_id,
            payin_address=payin_address
        )
        print(f"✅ [ENDPOINT] Database updated: conversion_status = 'swapping'")

        # Queue task to GCHostPay1 for swap execution
        print(f"📤 [ENDPOINT] Queuing swap execution to GCHostPay1")

        if not cloudtasks_client:
            print(f"❌ [ENDPOINT] Cloud Tasks client not available")
            abort(500, "Cloud Tasks unavailable")

        gchostpay1_queue = config.get('gchostpay1_queue')
        gchostpay1_url = config.get('gchostpay1_url')

        if not gchostpay1_queue or not gchostpay1_url:
            print(f"❌ [ENDPOINT] GCHostPay1 configuration missing")
            abort(500, "Service configuration error")

        # Encrypt token for GCHostPay1
        hostpay_token = token_manager.encrypt_accumulator_to_gchostpay1_token(
            accumulation_id=accumulation_id,
            cn_api_id=cn_api_id,
            from_currency='eth',
            from_network='eth',
            from_amount=from_amount,
            payin_address=payin_address
        )

        if not hostpay_token:
            print(f"❌ [ENDPOINT] Failed to encrypt token for GCHostPay1")
            abort(500, "Token encryption failed")

        task_name = cloudtasks_client.enqueue_gchostpay1_execution(
            queue_name=gchostpay1_queue,
            target_url=gchostpay1_url,
            encrypted_token=hostpay_token
        )

        if not task_name:
            print(f"❌ [ENDPOINT] Failed to enqueue execution task")
            abort(500, "Failed to enqueue execution task")

        print(f"✅ [ENDPOINT] Execution task enqueued: {task_name}")

        return jsonify({
            "status": "success",
            "message": "Swap created and execution queued",
            "accumulation_id": accumulation_id,
            "cn_api_id": cn_api_id,
            "execution_task": task_name
        }), 200

    except Exception as e:
        print(f"❌ [ENDPOINT] Unexpected error: {e}")
        return jsonify({
            "status": "error",
            "message": f"Processing error: {str(e)}"
        }), 500


@app.route("/swap-executed", methods=["POST"])
def swap_executed():
    """
    Receives response from GCHostPay1 after ETH payment is executed.

    Flow:
    1. Decrypt token from GCHostPay1
    2. Update database with final USDT amount
    3. Update conversion status = 'completed'
    4. Log success

    Returns:
        JSON response with status
    """
    try:
        print(f"🎯 [ENDPOINT] ETH→USDT swap executed notification received")

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

        decrypted_data = token_manager.decrypt_gchostpay1_to_accumulator_token(encrypted_token)
        if not decrypted_data:
            print(f"❌ [ENDPOINT] Failed to decrypt token")
            abort(401, "Invalid token")

        # Extract data
        accumulation_id = decrypted_data['accumulation_id']
        cn_api_id = decrypted_data['cn_api_id']
        tx_hash = decrypted_data['tx_hash']
        to_amount = decrypted_data['to_amount']  # Final USDT amount

        print(f"✅ [ENDPOINT] Swap executed successfully")
        print(f"🆔 [ENDPOINT] Accumulation ID: {accumulation_id}")
        print(f"🔗 [ENDPOINT] TX Hash: {tx_hash}")
        print(f"💰 [ENDPOINT] Final USDT: ${to_amount}")

        # Update database with final conversion
        if not db_manager:
            print(f"❌ [ENDPOINT] Database manager not available")
            abort(500, "Database unavailable")

        db_manager.finalize_accumulation_conversion(
            accumulation_id=accumulation_id,
            accumulated_amount_usdt=Decimal(str(to_amount)),
            conversion_tx_hash=tx_hash,
            conversion_status='completed'
        )

        print(f"✅ [ENDPOINT] Database updated: conversion_status = 'completed'")
        print(f"💰 [ENDPOINT] ${to_amount} USDT locked in value - volatility protection active!")

        return jsonify({
            "status": "success",
            "message": "Swap executed and finalized",
            "accumulation_id": accumulation_id,
            "cn_api_id": cn_api_id,
            "tx_hash": tx_hash,
            "final_usdt": to_amount
        }), 200

    except Exception as e:
        print(f"❌ [ENDPOINT] Unexpected error: {e}")
        return jsonify({
            "status": "error",
            "message": f"Processing error: {str(e)}"
        }), 500


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for monitoring."""
    try:
        return jsonify({
            "status": "healthy",
            "service": "GCAccumulator-10-26 Payment Accumulation",
            "timestamp": int(time.time()),
            "components": {
                "database": "healthy" if db_manager else "unhealthy",
                "token_manager": "healthy" if token_manager else "unhealthy",
                "cloudtasks": "healthy" if cloudtasks_client else "unhealthy"
            }
        }), 200

    except Exception as e:
        print(f"❌ [HEALTH] Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "service": "GCAccumulator-10-26 Payment Accumulation",
            "error": str(e)
        }), 503


if __name__ == "__main__":
    print(f"🚀 [APP] Starting GCAccumulator-10-26 on port 8080")
    app.run(host="0.0.0.0", port=8080, debug=False)
