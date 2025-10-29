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


@app.route("/", methods=["POST"])
def accumulate_payment():
    """
    Main endpoint for accumulating payments.

    Flow:
    1. Receive payment data from GCWebhook1
    2. Calculate adjusted amount (after TP fee)
    3. Convert to USDT (locks USD value - eliminates volatility)
    4. Write to payout_accumulation table
    5. Return success

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

        # For now, we'll use a 1:1 ETH→USDT mock conversion
        # In production, this would call GCSplit2 for actual ChangeNow estimate
        # CRITICAL: This locks the USD value in USDT to eliminate volatility
        accumulated_usdt = adjusted_amount_usd
        eth_to_usdt_rate = Decimal('1.0')  # Mock rate for now
        conversion_tx_hash = f"mock_cn_tx_{int(time.time())}"

        print(f"🌐 [ENDPOINT] USDT Conversion (MOCK)")
        print(f"💰 [ENDPOINT] USDT amount: {accumulated_usdt}")
        print(f"📊 [ENDPOINT] Rate: {eth_to_usdt_rate}")
        print(f"🆔 [ENDPOINT] TX Hash: {conversion_tx_hash}")

        # Write to payout_accumulation table
        if not db_manager:
            print(f"❌ [ENDPOINT] Database manager not available")
            abort(500, "Database unavailable")

        print(f"💾 [ENDPOINT] Inserting into payout_accumulation")

        accumulation_id = db_manager.insert_payout_accumulation(
            client_id=client_id,
            user_id=user_id,
            subscription_id=subscription_id,
            payment_amount_usd=payment_amount_usd,
            payment_currency='usd',
            payment_timestamp=payment_timestamp,
            accumulated_amount_usdt=accumulated_usdt,
            eth_to_usdt_rate=eth_to_usdt_rate,
            conversion_timestamp=datetime.now().isoformat(),
            conversion_tx_hash=conversion_tx_hash,
            client_wallet_address=wallet_address,
            client_payout_currency=payout_currency,
            client_payout_network=payout_network
        )

        if not accumulation_id:
            print(f"❌ [ENDPOINT] Failed to insert into database")
            abort(500, "Database insertion failed")

        print(f"✅ [ENDPOINT] Database insertion successful")
        print(f"🆔 [ENDPOINT] Accumulation ID: {accumulation_id}")

        # Check current accumulation total (informational)
        total_accumulated = db_manager.get_client_accumulation_total(client_id)
        threshold = db_manager.get_client_threshold(client_id)

        print(f"📊 [ENDPOINT] Client total accumulated: ${total_accumulated}")
        print(f"🎯 [ENDPOINT] Client threshold: ${threshold}")

        if total_accumulated >= threshold:
            print(f"🎉 [ENDPOINT] Threshold reached! GCBatchProcessor will process on next run")
        else:
            remaining = threshold - total_accumulated
            print(f"⏳ [ENDPOINT] ${remaining} remaining to reach threshold")

        print(f"🎉 [ENDPOINT] Payment accumulation completed successfully")

        return jsonify({
            "status": "success",
            "message": "Payment accumulated successfully",
            "accumulation_id": accumulation_id,
            "accumulated_usdt": str(accumulated_usdt),
            "total_accumulated": str(total_accumulated),
            "threshold": str(threshold),
            "threshold_reached": total_accumulated >= threshold
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
