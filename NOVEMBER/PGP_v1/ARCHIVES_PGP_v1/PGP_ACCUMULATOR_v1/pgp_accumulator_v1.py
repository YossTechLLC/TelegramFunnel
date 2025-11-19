#!/usr/bin/env python
"""
PGP_ACCUMULATOR_v1: Payment Accumulation Service
Receives payment data from PGP_ORCHESTRATOR_v1, converts to USDT immediately,
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

from PGP_COMMON.logging import setup_logger
logger = setup_logger(__name__)

app = Flask(__name__)

# Initialize managers
logger.info(f"🚀 [APP] Initializing PGP_ACCUMULATOR_v1 Payment Accumulation Service")
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
    logger.info(f"✅ [APP] Database manager initialized")
except Exception as e:
    logger.error(f"❌ [APP] Failed to initialize database manager: {e}", exc_info=True)
    db_manager = None

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

# ChangeNow client removed - conversion now handled by PGP_SPLIT2_v1 via Cloud Tasks


@app.route("/", methods=["POST"])
def accumulate_payment():
    """
    Main endpoint for accumulating payments.

    Flow:
    1. Receive payment data from PGP_ORCHESTRATOR_v1
    2. Calculate adjusted amount (after TP fee)
    3. Store payment with accumulated_eth (pending conversion)
    4. Queue task to PGP_SPLIT2_v1 for ETH→USDT conversion
    5. Return success immediately (non-blocking)

    Returns:
        JSON response with status
    """
    try:
        logger.info(f"🎯 [ENDPOINT] Payment accumulation request received")

        # Parse JSON payload
        try:
            request_data = request.get_json()
            if not request_data:
                abort(400, "Invalid JSON payload")
        except Exception as e:
            logger.error(f"❌ [ENDPOINT] JSON parsing error: {e}", exc_info=True)
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

        # NEW: Extract NowPayments fields (optional)
        nowpayments_payment_id = request_data.get('nowpayments_payment_id')
        nowpayments_pay_address = request_data.get('nowpayments_pay_address')
        nowpayments_outcome_amount = request_data.get('nowpayments_outcome_amount')

        logger.info(f"👤 [ENDPOINT] User ID: {user_id}")
        logger.info(f"🏢 [ENDPOINT] Client ID: {client_id}")
        logger.info(f"💰 [ENDPOINT] Payment Amount: ${payment_amount_usd}")
        logger.info(f"🎯 [ENDPOINT] Target: {payout_currency.upper()} on {payout_network.upper()}")

        if nowpayments_payment_id:
            logger.info(f"💳 [ENDPOINT] NowPayments Payment ID: {nowpayments_payment_id}")
            logger.info(f"📬 [ENDPOINT] Pay Address: {nowpayments_pay_address}")
            logger.info(f"💰 [ENDPOINT] Outcome Amount: {nowpayments_outcome_amount}")
        else:
            logger.warning(f"⚠️ [ENDPOINT] NowPayments payment_id not available (may arrive via IPN later)")

        # Calculate adjusted amount (remove TP fee like PGP_SPLIT1_v1 does)
        tp_flat_fee = Decimal(config.get('tp_flat_fee', '3'))
        fee_amount = payment_amount_usd * (tp_flat_fee / Decimal('100'))
        adjusted_amount_usd = payment_amount_usd - fee_amount

        logger.info(f"💸 [ENDPOINT] TP fee ({tp_flat_fee}%): ${fee_amount}")
        logger.info(f"✅ [ENDPOINT] Adjusted amount: ${adjusted_amount_usd}")

        # Store accumulated_eth (the adjusted USD amount pending conversion)
        # Conversion will happen asynchronously via PGP_SPLIT2_v1
        accumulated_eth = adjusted_amount_usd
        logger.info(f"⏳ [ENDPOINT] Storing payment with accumulated_eth (pending conversion)")
        logger.info(f"💰 [ENDPOINT] Accumulated ETH value: ${accumulated_eth}")

        # Write to payout_accumulation table
        if not db_manager:
            logger.error(f"❌ [ENDPOINT] Database manager not available")
            abort(500, "Database unavailable")

        logger.info(f"💾 [ENDPOINT] Inserting into payout_accumulation (pending conversion)")

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
            client_payout_network=payout_network,
            nowpayments_payment_id=nowpayments_payment_id,
            nowpayments_pay_address=nowpayments_pay_address,
            nowpayments_outcome_amount=nowpayments_outcome_amount
        )

        if not accumulation_id:
            logger.error(f"❌ [ENDPOINT] Failed to insert into database")
            abort(500, "Database insertion failed")

        logger.info(f"✅ [ENDPOINT] Database insertion successful")
        logger.debug(f"🆔 [ENDPOINT] Accumulation ID: {accumulation_id}")

        logger.info(f"✅ [ENDPOINT] Payment accumulated (awaiting micro-batch conversion)")
        logger.info(f"⏳ [ENDPOINT] Conversion will occur when batch threshold reached")

        return jsonify({
            "status": "success",
            "message": "Payment accumulated successfully (micro-batch pending)",
            "accumulation_id": accumulation_id,
            "accumulated_eth": str(accumulated_eth),
            "conversion_status": "pending"
        }), 200

    except Exception as e:
        logger.error(f"❌ [ENDPOINT] Unexpected error: {e}", exc_info=True)
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
            "service": "PGP_ACCUMULATOR_v1 Payment Accumulation",
            "timestamp": int(time.time()),
            "components": {
                "database": "healthy" if db_manager else "unhealthy",
                "token_manager": "healthy" if token_manager else "unhealthy",
                "cloudtasks": "healthy" if cloudtasks_client else "unhealthy"
            }
        }), 200

    except Exception as e:
        logger.error(f"❌ [HEALTH] Health check failed: {e}", exc_info=True)
        return jsonify({
            "status": "unhealthy",
            "service": "PGP_ACCUMULATOR_v1 Payment Accumulation",
            "error": str(e)
        }), 503


if __name__ == "__main__":
    logger.info(f"🚀 [APP] Starting PGP_ACCUMULATOR_v1 on port 8080")
    app.run(host="0.0.0.0", port=8080, debug=False)
