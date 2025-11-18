#!/usr/bin/env python
"""
PGP_NP_IPN_v1: NowPayments IPN Webhook Handler
Receives Instant Payment Notification (IPN) callbacks from NowPayments.
Verifies signature and updates database with payment_id and payment metadata.
"""
import os
import json
import requests
from flask import Flask, request, jsonify, abort
from flask_cors import CORS
from google.cloud.sql.connector import Connector
from typing import Optional
from PGP_COMMON.utils import (
    CryptoPricingClient,
    verify_sha512_signature,
    sanitize_error_for_user,
    create_error_response
)

from PGP_COMMON.logging import setup_logger
logger = setup_logger(__name__)
# Initialize logger

app = Flask(__name__)

# ============================================================================
# CORS CONFIGURATION
# ============================================================================
# NOTE: CORS is now only for backward compatibility with cached URLs.
# The payment-processing.html is served from this same service (GET /payment-processing)
# so it uses same-origin requests which don't need CORS.
# CORS is kept here in case old Cloud Storage URLs are still cached somewhere.

# Configure CORS to allow requests from Cloud Storage and custom domain
CORS(app, resources={
    r"/api/*": {
        "origins": [
            "https://storage.googleapis.com",  # Backward compatibility
            "https://www.paygateprime.com",
            "http://localhost:3000",  # For local testing
            "http://localhost:*"
        ],
        "methods": ["GET", "OPTIONS"],
        "allow_headers": ["Content-Type", "Accept"],
        "expose_headers": ["Content-Type"],
        "supports_credentials": False,
        "max_age": 3600
    }
})

logger.info(f"✅ [CORS] Configured for /api/* routes (backward compatibility)")
logger.info(f"   NOTE: Main flow (GET /payment-processing) uses same-origin, no CORS needed")
logger.info(f"   Allowed origins: storage.googleapis.com, www.paygateprime.com, localhost")
logger.info(f"   IPN endpoint (POST /) remains protected (no CORS)")

# ============================================================================
# CONFIGURATION AND INITIALIZATION
# ============================================================================

logger.info(f"🚀 [APP] Initializing PGP_NP_IPN_v1 - NowPayments IPN Handler")
logger.info(f"📋 [APP] This service processes IPN callbacks from NowPayments")
logger.info(f"🔐 [APP] Verifies signatures and updates database with payment_id")

# Fetch required secrets from environment (mounted by Cloud Run)
logger.info(f"⚙️ [CONFIG] Loading configuration from Secret Manager...")

# IPN Secret for signature verification
NOWPAYMENTS_IPN_SECRET = (os.getenv('NOWPAYMENTS_IPN_SECRET') or '').strip() or None
if NOWPAYMENTS_IPN_SECRET:
    logger.info(f"✅ [CONFIG] NOWPAYMENTS_IPN_SECRET loaded")
else:
    logger.error(f"❌ [CONFIG] NOWPAYMENTS_IPN_SECRET not found")
    logger.warning(f"⚠️ [CONFIG] IPN signature verification will fail!")

# Database credentials
CLOUD_SQL_CONNECTION_NAME = (os.getenv('CLOUD_SQL_CONNECTION_NAME') or '').strip() or None
DATABASE_NAME = (os.getenv('DATABASE_NAME_SECRET') or '').strip() or None
DATABASE_USER = (os.getenv('DATABASE_USER_SECRET') or '').strip() or None
DATABASE_PASSWORD = (os.getenv('DATABASE_PASSWORD_SECRET') or '').strip() or None

logger.debug(f"📊 [CONFIG] Database Configuration Status:")
logger.error(f"   CLOUD_SQL_CONNECTION_NAME: {'✅ Loaded' if CLOUD_SQL_CONNECTION_NAME else '❌ Missing'}")
logger.error(f"   DATABASE_NAME_SECRET: {'✅ Loaded' if DATABASE_NAME else '❌ Missing'}")
logger.error(f"   DATABASE_USER_SECRET: {'✅ Loaded' if DATABASE_USER else '❌ Missing'}")
logger.error(f"   DATABASE_PASSWORD_SECRET: {'✅ Loaded' if DATABASE_PASSWORD else '❌ Missing'}")

if not all([CLOUD_SQL_CONNECTION_NAME, DATABASE_NAME, DATABASE_USER, DATABASE_PASSWORD]):
    logger.error(f"❌ [CONFIG] CRITICAL: Missing database credentials!")
    logger.warning(f"⚠️ [CONFIG] Service will not be able to update payment_id in database")
    logger.warning(f"⚠️ [CONFIG] Required secrets:")
    logger.info(f"   - CLOUD_SQL_CONNECTION_NAME")
    logger.info(f"   - DATABASE_NAME_SECRET")
    logger.info(f"   - DATABASE_USER_SECRET")
    logger.info(f"   - DATABASE_PASSWORD_SECRET")
else:
    logger.info(f"✅ [CONFIG] All database credentials loaded successfully")
    logger.info(f"🗄️ [CONFIG] Database: {DATABASE_NAME}")
    logger.info(f"🔗 [CONFIG] Instance: {CLOUD_SQL_CONNECTION_NAME}")

logger.info(f"🎯 [APP] Initialization complete - Ready to process IPN callbacks")

# Initialize Cloud SQL Connector
connector = None
if all([CLOUD_SQL_CONNECTION_NAME, DATABASE_NAME, DATABASE_USER, DATABASE_PASSWORD]):
    try:
        connector = Connector()
        logger.info(f"✅ [DATABASE] Cloud SQL Connector initialized")
    except Exception as e:
        logger.error(f"❌ [DATABASE] Failed to initialize Cloud SQL Connector: {e}", exc_info=True)
else:
    logger.warning(f"⚠️ [DATABASE] Skipping connector initialization - missing credentials")

# ============================================================================
# CLOUD TASKS INITIALIZATION
# ============================================================================

logger.info(f"⚙️ [CONFIG] Loading Cloud Tasks configuration...")

# Cloud Tasks configuration for triggering PGP Orchestrator
CLOUD_TASKS_PROJECT_ID = (os.getenv('CLOUD_TASKS_PROJECT_ID') or '').strip() or None
CLOUD_TASKS_LOCATION = (os.getenv('CLOUD_TASKS_LOCATION') or '').strip() or None
PGP_ORCHESTRATOR_QUEUE = (os.getenv('PGP_ORCHESTRATOR_QUEUE') or '').strip() or None
PGP_ORCHESTRATOR_URL = (os.getenv('PGP_ORCHESTRATOR_URL') or '').strip() or None

# 🆕 PGP_NOTIFICATIONS URL for payment notifications (PGP_NOTIFICATIONS_REFACTORING_ARCHITECTURE)
GCNOTIFICATIONSERVICE_URL = (os.getenv('GCNOTIFICATIONSERVICE_URL') or '').strip() or None

logger.error(f"   CLOUD_TASKS_PROJECT_ID: {'✅ Loaded' if CLOUD_TASKS_PROJECT_ID else '❌ Missing'}")
logger.error(f"   CLOUD_TASKS_LOCATION: {'✅ Loaded' if CLOUD_TASKS_LOCATION else '❌ Missing'}")
logger.error(f"   PGP_ORCHESTRATOR_QUEUE: {'✅ Loaded' if PGP_ORCHESTRATOR_QUEUE else '❌ Missing'}")
logger.error(f"   PGP_ORCHESTRATOR_URL: {'✅ Loaded' if PGP_ORCHESTRATOR_URL else '❌ Missing'}")
logger.error(f"   🆕 GCNOTIFICATIONSERVICE_URL: {'✅ Loaded' if GCNOTIFICATIONSERVICE_URL else '❌ Missing (notifications disabled)'}")

# Initialize Cloud Tasks client
cloudtasks_client = None
if all([CLOUD_TASKS_PROJECT_ID, CLOUD_TASKS_LOCATION]):
    try:
        from cloudtasks_client import CloudTasksClient
        cloudtasks_client = CloudTasksClient(CLOUD_TASKS_PROJECT_ID, CLOUD_TASKS_LOCATION)
        logger.info(f"✅ [CLOUDTASKS] Client initialized successfully")
    except Exception as e:
        logger.error(f"❌ [CLOUDTASKS] Failed to initialize client: {e}", exc_info=True)
        logger.warning(f"⚠️ [CLOUDTASKS] PGP_ORCHESTRATOR_v1 triggering will not work!")
else:
    logger.warning(f"⚠️ [CLOUDTASKS] Skipping initialization - missing configuration")
    logger.warning(f"⚠️ [CLOUDTASKS] PGP_ORCHESTRATOR_v1 will NOT be triggered after IPN validation!")


# ============================================================================
# CRYPTO PRICING CLIENT INITIALIZATION
# ============================================================================
# Initialize shared crypto pricing client (consolidated from inline function)
pricing_client = CryptoPricingClient()
logger.info(f"✅ [PRICING] CryptoPricingClient initialized")
logger.info(f"💰 [PRICING] Supports both uppercase and lowercase crypto symbols")

# ============================================================================
# DATABASE MANAGER INITIALIZATION
# ============================================================================
# Initialize database manager (moved from inline functions)
db_manager = None
if all([CLOUD_SQL_CONNECTION_NAME, DATABASE_NAME, DATABASE_USER, DATABASE_PASSWORD]):
    try:
        from database_manager import DatabaseManager
        db_manager = DatabaseManager(
            instance_connection_name=CLOUD_SQL_CONNECTION_NAME,
            db_name=DATABASE_NAME,
            db_user=DATABASE_USER,
            db_password=DATABASE_PASSWORD
        )
        logger.info(f"✅ [DATABASE] DatabaseManager initialized")
    except Exception as e:
        logger.error(f"❌ [DATABASE] Failed to initialize DatabaseManager: {e}", exc_info=True)
        logger.warning(f"⚠️ [DATABASE] Database operations will not work!")
else:
    logger.warning(f"⚠️ [DATABASE] Skipping DatabaseManager initialization - missing credentials")


# ============================================================================
# DATABASE FUNCTIONS - MOVED TO database_manager.py
# ============================================================================
# The following functions have been moved to PGP_NP_IPN_v1/database_manager.py:
#   - parse_order_id() → db_manager.parse_order_id()
#   - update_payment_data() → db_manager.update_payment_data()
#   - get_db_connection() → db_manager.get_connection()
#
# This refactoring improves separation of concerns and reduces main file size.
# (~270 lines moved to database_manager.py)
# ============================================================================


# ============================================================================
# IPN SIGNATURE VERIFICATION
# ============================================================================

# ============================================================================
# IPN SIGNATURE VERIFICATION - Moved to PGP_COMMON/utils/webhook_auth.py
# ============================================================================
# The verify_ipn_signature() function has been replaced with:
#   verify_sha512_signature() from PGP_COMMON.utils
#
# This consolidates duplicate signature verification logic across services.
# (~36 lines moved to shared utility)
# ============================================================================


# ============================================================================
# IPN ENDPOINT
# ============================================================================

@app.route('/', methods=['POST'])
def handle_ipn():
    """
    Handle IPN callback from NowPayments.
    Verifies signature and updates database with payment_id.
    """
    logger.info(f"📬 [IPN] Received callback from NowPayments")
    logger.info(f"🌐 [IPN] Source IP: {request.remote_addr}")
    logger.info(f"⏰ [IPN] Timestamp: {request.headers.get('Date', 'N/A')}")

    # Get signature from header
    signature = request.headers.get('x-nowpayments-sig')
    if not signature:
        logger.error(f"❌ [IPN] Missing x-nowpayments-sig header")
        logger.warning(f"🚫 [IPN] Rejecting request - no signature")
        abort(403, "Missing signature header")

    logger.info(f"🔐 [IPN] Signature header present: {signature[:20]}...")

    # Get raw request body for signature verification
    payload = request.get_data()
    logger.info(f"📦 [IPN] Payload size: {len(payload)} bytes")

    # Verify signature using shared utility (HMAC-SHA512 for NowPayments)
    if not NOWPAYMENTS_IPN_SECRET:
        logger.error(f"❌ [IPN] Cannot verify signature - NOWPAYMENTS_IPN_SECRET not configured")
        abort(500, "IPN secret not configured")

    if not verify_sha512_signature(payload, signature, NOWPAYMENTS_IPN_SECRET):
        logger.error(f"❌ [IPN] Signature verification failed - rejecting request")
        abort(403, "Invalid signature")

    logger.info(f"✅ [IPN] Signature verified successfully")

    # Parse JSON payload
    try:
        ipn_data = request.get_json()
        logger.info(f"📋 [IPN] Payment Data Received:")
        logger.info(f"   Payment ID: {ipn_data.get('payment_id', 'N/A')}")
        logger.info(f"   Order ID: {ipn_data.get('order_id', 'N/A')}")
        logger.info(f"   Payment Status: {ipn_data.get('payment_status', 'N/A')}")
        logger.info(f"   Pay Amount: {ipn_data.get('pay_amount', 'N/A')} {ipn_data.get('pay_currency', 'N/A')}")
        logger.info(f"   Outcome Amount: {ipn_data.get('outcome_amount', 'N/A')} {ipn_data.get('outcome_currency', ipn_data.get('pay_currency', 'N/A'))}")
        logger.info(f"   Price Amount: {ipn_data.get('price_amount', 'N/A')} {ipn_data.get('price_currency', 'N/A')}")
        logger.info(f"   Pay Address: {ipn_data.get('pay_address', 'N/A')}")

    except Exception as e:
        logger.error(f"❌ [IPN] Failed to parse JSON payload: {e}", exc_info=True)
        abort(400, "Invalid JSON payload")

    # ============================================================================
    # CRITICAL: Validate payment_status before processing
    # ============================================================================
    payment_status = ipn_data.get('payment_status', '').lower()

    # Define allowed statuses (only process finished payments)
    ALLOWED_PAYMENT_STATUSES = ['finished']

    logger.debug(f"🔍 [IPN] Payment status received: '{payment_status}'")
    logger.info(f"✅ [IPN] Allowed statuses: {ALLOWED_PAYMENT_STATUSES}")

    if payment_status not in ALLOWED_PAYMENT_STATUSES:
        logger.info(f"⏸️ [IPN] PAYMENT STATUS NOT READY FOR PROCESSING")
        logger.debug(f"📊 [IPN] Current status: '{payment_status}'")
        logger.info(f"⏳ [IPN] Waiting for status: 'finished'")
        logger.info(f"💳 [IPN] Payment ID: {ipn_data.get('payment_id')}")
        logger.info(f"💰 [IPN] Amount: {ipn_data.get('price_amount')} {ipn_data.get('price_currency')}")
        logger.info(f"📝 [IPN] Action: Acknowledged but not processed")
        logger.info(f"🔄 [IPN] NowPayments will send another IPN when status becomes 'finished'")

        # Return 200 OK to acknowledge receipt to NowPayments
        # But DO NOT trigger PGP_ORCHESTRATOR_v1 or any downstream processing
        return jsonify({
            "status": "acknowledged",
            "message": f"IPN received but not processed. Waiting for status 'finished' (current: {payment_status})",
            "payment_id": ipn_data.get('payment_id'),
            "current_status": payment_status,
            "required_status": "finished"
        }), 200

    # If we reach here, payment_status is 'finished' - proceed with processing
    logger.info(f"✅ [IPN] PAYMENT STATUS VALIDATED: '{payment_status}'")
    logger.info(f"✅ [IPN] Proceeding with payment processing")

    # Extract required fields
    order_id = ipn_data.get('order_id')
    if not order_id:
        logger.error(f"❌ [IPN] Missing order_id in payload")
        abort(400, "Missing order_id")

    # Update database with payment data
    logger.info(f"🗄️ [DATABASE] Updating database with payment data...")

    payment_data = {
        'payment_id': ipn_data.get('payment_id'),
        'invoice_id': ipn_data.get('invoice_id'),
        'order_id': ipn_data.get('order_id'),
        'pay_address': ipn_data.get('pay_address'),
        'payment_status': ipn_data.get('payment_status'),
        'pay_amount': ipn_data.get('pay_amount'),
        'pay_currency': ipn_data.get('pay_currency'),
        'outcome_amount': ipn_data.get('outcome_amount'),
        'price_amount': ipn_data.get('price_amount'),           # NEW: Original USD amount
        'price_currency': ipn_data.get('price_currency'),       # NEW: Original currency
        'outcome_currency': ipn_data.get('outcome_currency')    # NEW: Outcome currency
    }

    # If outcome_currency not provided, infer from pay_currency
    # (NowPayments might not always include outcome_currency)
    if not payment_data.get('outcome_currency'):
        # Assume outcome is in same currency as payment
        payment_data['outcome_currency'] = payment_data.get('pay_currency')
        logger.info(f"💡 [IPN] outcome_currency not provided, inferring from pay_currency: {payment_data['outcome_currency']}")

    success = db_manager.update_payment_data(order_id, payment_data) if db_manager else False

    if not success:
        logger.warning(f"⚠️ [IPN] Database update failed")
        logger.info(f"🔄 [IPN] Returning 500 - NowPayments will retry")
        abort(500, "Database update failed")

    # ============================================================================
    # NEW: Calculate Outcome Amount in USD using CoinGecko
    # ============================================================================
    logger.info(f"💱 [CONVERSION] Calculating USD value of outcome amount...")

    outcome_amount = payment_data.get('outcome_amount')
    outcome_currency = payment_data.get('outcome_currency', payment_data.get('pay_currency'))
    outcome_amount_usd = None

    # Check if outcome is already in USD/stablecoin
    if outcome_currency and outcome_currency.upper() in ['USDT', 'USDC', 'USD', 'BUSD', 'DAI']:
        # Already in USD equivalent - no conversion needed
        outcome_amount_usd = float(outcome_amount) if outcome_amount else None
        if outcome_amount_usd:
            logger.info(f"✅ [CONVERSION] Already in USD equivalent: ${outcome_amount_usd:.2f}")
    elif outcome_currency and outcome_amount:
        # Fetch current market price from CoinGecko using shared pricing client
        crypto_usd_price = pricing_client.get_crypto_usd_price(outcome_currency)

        if crypto_usd_price:
            # Calculate USD value
            outcome_amount_usd = float(outcome_amount) * crypto_usd_price
            logger.info(f"💰 [CONVERT] {outcome_amount} {outcome_currency} × ${crypto_usd_price:,.2f}")
            logger.info(f"💰 [CONVERT] = ${outcome_amount_usd:.2f} USD")
        else:
            logger.error(f"❌ [CONVERT] Failed to fetch {outcome_currency} price from CoinGecko")
            logger.warning(f"⚠️ [CONVERT] Will not calculate outcome_amount_usd")
    else:
        logger.warning(f"⚠️ [CONVERT] Missing outcome_amount or outcome_currency")
        logger.info(f"   outcome_amount: {outcome_amount}")
        logger.info(f"   outcome_currency: {outcome_currency}")

    if outcome_amount_usd:
        logger.info(f"💰 [VALIDATION] Final Outcome in USD: ${outcome_amount_usd:.2f}")

        # Update database with outcome_amount_usd
        try:
            # Need to get user_id and closed_channel_id again
            user_id, open_channel_id = db_manager.parse_order_id(order_id) if db_manager else (None, None)
            if user_id and open_channel_id and db_manager:
                conn = db_manager.get_connection()
                if conn:
                    cur = conn.cursor()

                    # Get closed_channel_id
                    cur.execute(
                        "SELECT closed_channel_id FROM main_clients_database WHERE open_channel_id = %s",
                        (str(open_channel_id),)
                    )
                    result = cur.fetchone()

                    if result:
                        closed_channel_id = result[0]

                        # Update outcome_amount_usd
                        cur.execute("""
                            UPDATE private_channel_users_database
                            SET nowpayments_outcome_amount_usd = %s
                            WHERE user_id = %s AND private_channel_id = %s
                            AND id = (
                                SELECT id FROM private_channel_users_database
                                WHERE user_id = %s AND private_channel_id = %s
                                ORDER BY id DESC LIMIT 1
                            )
                        """, (outcome_amount_usd, user_id, closed_channel_id, user_id, closed_channel_id))

                        conn.commit()
                        logger.info(f"✅ [DATABASE] Updated nowpayments_outcome_amount_usd: ${outcome_amount_usd:.2f}")

                        # Now fetch subscription details for PGP_ORCHESTRATOR_v1 triggering
                        # JOIN with main_clients_database to get wallet/payout info
                        cur.execute("""
                            SELECT
                                c.client_wallet_address,
                                c.client_payout_currency::text,
                                c.client_payout_network::text,
                                u.sub_time,
                                u.sub_price
                            FROM private_channel_users_database u
                            JOIN main_clients_database c ON u.private_channel_id = c.closed_channel_id
                            WHERE u.user_id = %s AND u.private_channel_id = %s
                            ORDER BY u.id DESC LIMIT 1
                        """, (user_id, closed_channel_id))

                        sub_data = cur.fetchone()

                        cur.close()
                        conn.close()

                        # ============================================================================
                        # IDEMPOTENCY CHECK: Prevent duplicate payment processing
                        # ============================================================================

                        nowpayments_payment_id = payment_data['payment_id']

                        logger.debug(f"🔍 [IDEMPOTENCY] Checking if payment {nowpayments_payment_id} already processed...")

                        try:
                            # Query database to check if payment already processed
                            conn_check = get_db_connection()
                            if conn_check:
                                cur_check = conn_check.cursor()

                                cur_check.execute("""
                                    SELECT
                                        pgp_orchestrator_processed,
                                        telegram_invite_sent,
                                        telegram_invite_sent_at
                                    FROM processed_payments
                                    WHERE payment_id = %s
                                """, (nowpayments_payment_id,))

                                existing_payment = cur_check.fetchone()

                                cur_check.close()
                                conn_check.close()

                                if existing_payment and existing_payment[0]:  # pgp_orchestrator_processed = TRUE
                                    logger.info(f"✅ [IDEMPOTENCY] Payment {nowpayments_payment_id} already processed")
                                    logger.info(f"   PGP_ORCHESTRATOR_v1 processed: TRUE")
                                    logger.info(f"   Telegram invite sent: {existing_payment[1]}")
                                    if existing_payment[2]:
                                        logger.info(f"   Invite sent at: {existing_payment[2]}")

                                    # Already processed - return success without re-enqueueing
                                    logger.info(f"✅ [IPN] IPN acknowledged (payment already handled)")
                                    return jsonify({
                                        "status": "success",
                                        "message": "IPN processed (already handled)",
                                        "payment_id": nowpayments_payment_id
                                    }), 200

                                elif existing_payment:
                                    # Record exists but not fully processed
                                    logger.warning(f"⚠️ [IDEMPOTENCY] Payment {nowpayments_payment_id} record exists but processing incomplete")
                                    logger.info(f"   PGP_ORCHESTRATOR_v1 processed: {existing_payment[0]}")
                                    logger.info(f"   Will allow re-processing to complete")
                                else:
                                    # No existing record - first time processing
                                    logger.debug(f"🆕 [IDEMPOTENCY] Payment {nowpayments_payment_id} is new - creating processing record")

                                    # Insert initial record (prevents race conditions)
                                    conn_insert = get_db_connection()
                                    if conn_insert:
                                        cur_insert = conn_insert.cursor()

                                        cur_insert.execute("""
                                            INSERT INTO processed_payments (payment_id, user_id, channel_id)
                                            VALUES (%s, %s, %s)
                                            ON CONFLICT (payment_id) DO NOTHING
                                        """, (nowpayments_payment_id, user_id, closed_channel_id))

                                        conn_insert.commit()
                                        cur_insert.close()
                                        conn_insert.close()

                                        logger.info(f"✅ [IDEMPOTENCY] Created processing record for payment {nowpayments_payment_id}")
                                    else:
                                        logger.warning(f"⚠️ [IDEMPOTENCY] Failed to create processing record (DB connection failed)")
                                        logger.warning(f"⚠️ [IDEMPOTENCY] Proceeding with processing (fail-open mode)")
                            else:
                                logger.warning(f"⚠️ [IDEMPOTENCY] Database connection failed - cannot check idempotency")
                                logger.warning(f"⚠️ [IDEMPOTENCY] Proceeding with processing (fail-open mode)")

                        except Exception as e:
                            logger.error(f"❌ [IDEMPOTENCY] Error during idempotency check: {e}", exc_info=True)
                            import traceback
                            traceback.print_exc()
                            logger.warning(f"⚠️ [IDEMPOTENCY] Proceeding with processing (fail-open mode)")

                        logger.info(f"🚀 [ORCHESTRATION] Proceeding to enqueue payment to PGP_ORCHESTRATOR_v1...")

                        # ============================================================================
                        # NEW: Trigger PGP_ORCHESTRATOR_v1 for Payment Orchestration
                        # ============================================================================
                        if sub_data:
                            wallet_address = sub_data[0]
                            payout_currency = sub_data[1]
                            payout_network = sub_data[2]
                            subscription_time_days = sub_data[3]
                            subscription_price = str(sub_data[4])  # Ensure string type

                            logger.info(f"🚀 [ORCHESTRATION] Triggering PGP Orchestrator for payment processing...")

                            if not cloudtasks_client:
                                logger.error(f"❌ [ORCHESTRATION] Cloud Tasks client not initialized")
                                logger.warning(f"⚠️ [ORCHESTRATION] Cannot trigger PGP Orchestrator - payment will not be processed!")
                            elif not PGP_ORCHESTRATOR_QUEUE or not PGP_ORCHESTRATOR_URL:
                                logger.error(f"❌ [ORCHESTRATION] PGP Orchestrator configuration missing")
                                logger.warning(f"⚠️ [ORCHESTRATION] Cannot trigger PGP Orchestrator - payment will not be processed!")
                            else:
                                try:
                                    task_name = cloudtasks_client.enqueue_pgp_orchestrator_validated_payment(
                                        queue_name=PGP_ORCHESTRATOR_QUEUE,
                                        target_url=f"{PGP_ORCHESTRATOR_URL}/process-validated-payment",
                                        user_id=user_id,
                                        closed_channel_id=closed_channel_id,
                                        wallet_address=wallet_address,
                                        payout_currency=payout_currency,
                                        payout_network=payout_network,
                                        subscription_time_days=subscription_time_days,
                                        subscription_price=subscription_price,
                                        outcome_amount_usd=outcome_amount_usd,  # CRITICAL: Real amount
                                        nowpayments_payment_id=payment_data['payment_id'],
                                        nowpayments_pay_address=ipn_data.get('pay_address'),
                                        nowpayments_outcome_amount=outcome_amount,
                                        payment_status=payment_status  # ✅ NEW: Pass validated status to PGP_ORCHESTRATOR_v1
                                    )

                                    if task_name:
                                        logger.info(f"✅ [ORCHESTRATION] Successfully enqueued to PGP_ORCHESTRATOR_v1")
                                        logger.debug(f"🆔 [ORCHESTRATION] Task: {task_name}")

                                        # 🆕 Trigger notification service via PGP_NOTIFICATIONS (PGP_NOTIFICATIONS_REFACTORING_ARCHITECTURE)
                                        try:
                                            logger.info(f"📬 [NOTIFICATION] Triggering payment notification...")

                                            if GCNOTIFICATIONSERVICE_URL:
                                                # Determine payment type
                                                payment_type = 'donation' if subscription_time_days == 0 else 'subscription'

                                                # Prepare notification payload
                                                notification_payload = {
                                                    'open_channel_id': str(open_channel_id),
                                                    'payment_type': payment_type,
                                                    'payment_data': {
                                                        'user_id': user_id,
                                                        'username': None,  # Could fetch from Telegram API if needed
                                                        'amount_crypto': str(outcome_amount),
                                                        'amount_usd': str(outcome_amount_usd),
                                                        'crypto_currency': str(outcome_currency),
                                                        'timestamp': payment_data.get('created_at', 'N/A')
                                                    }
                                                }

                                                # Add payment-type-specific data
                                                if payment_type == 'subscription':
                                                    # Query tier prices from main_clients_database to determine tier
                                                    tier = 1  # Default
                                                    try:
                                                        conn_tiers = get_db_connection()
                                                        if conn_tiers:
                                                            cur_tiers = conn_tiers.cursor()
                                                            cur_tiers.execute("""
                                                                SELECT sub_1_price, sub_2_price, sub_3_price
                                                                FROM main_clients_database
                                                                WHERE open_channel_id = %s
                                                            """, (str(open_channel_id),))
                                                            tier_prices = cur_tiers.fetchone()
                                                            cur_tiers.close()
                                                            conn_tiers.close()

                                                            if tier_prices:
                                                                # Convert subscription_price to Decimal for comparison
                                                                from decimal import Decimal
                                                                subscription_price_decimal = Decimal(subscription_price)

                                                                # Match price to determine tier
                                                                if tier_prices[1] and subscription_price_decimal == tier_prices[1]:
                                                                    tier = 2
                                                                elif tier_prices[2] and subscription_price_decimal == tier_prices[2]:
                                                                    tier = 3
                                                                # else tier = 1 (already set)

                                                                logger.info(f"🎯 [NOTIFICATION] Determined tier: {tier} (price: ${subscription_price})")
                                                            else:
                                                                logger.warning(f"⚠️ [NOTIFICATION] Could not fetch tier prices, defaulting to tier 1")
                                                    except Exception as e:
                                                        logger.error(f"❌ [NOTIFICATION] Error determining tier: {e}", exc_info=True)
                                                        logger.warning(f"⚠️ [NOTIFICATION] Defaulting to tier 1")

                                                    notification_payload['payment_data'].update({
                                                        'tier': tier,
                                                        'tier_price': str(subscription_price),
                                                        'duration_days': subscription_time_days
                                                    })

                                                # Send HTTP POST to PGP_NOTIFICATIONS
                                                logger.info(f"📤 [NOTIFICATION] Calling PGP_NOTIFICATIONS...")
                                                logger.info(f"   URL: {GCNOTIFICATIONSERVICE_URL}/send-notification")
                                                logger.info(f"   Channel ID: {open_channel_id}")
                                                logger.info(f"   Payment Type: {payment_type}")

                                                try:
                                                    response = requests.post(
                                                        f"{GCNOTIFICATIONSERVICE_URL}/send-notification",
                                                        json=notification_payload,
                                                        timeout=10
                                                    )

                                                    if response.status_code == 200:
                                                        result = response.json()
                                                        if result.get('status') == 'success':
                                                            logger.info(f"✅ [NOTIFICATION] Notification sent successfully")
                                                            logger.info(f"📤 [NOTIFICATION] Response: {result.get('message')}")
                                                        else:
                                                            logger.warning(f"⚠️ [NOTIFICATION] Notification not sent: {result.get('message')}")
                                                            logger.info(f"   Status: {result.get('status')}")
                                                    else:
                                                        logger.warning(f"⚠️ [NOTIFICATION] HTTP {response.status_code}")
                                                        logger.info(f"📄 [NOTIFICATION] Response: {response.text}")

                                                except requests.exceptions.Timeout:
                                                    logger.info(f"⏱️ [NOTIFICATION] Request timeout (10s) - notification may still be processed")
                                                except requests.exceptions.ConnectionError as e:
                                                    logger.info(f"🔌 [NOTIFICATION] Connection error: {e}")
                                                except Exception as e:
                                                    logger.error(f"❌ [NOTIFICATION] Request error: {e}", exc_info=True)

                                            else:
                                                logger.info(f"⏭️ [NOTIFICATION] GCNOTIFICATIONSERVICE_URL not configured, skipping notification")

                                        except Exception as e:
                                            logger.error(f"❌ [NOTIFICATION] Error in notification flow: {e}", exc_info=True)
                                            logger.warning(f"⚠️ [NOTIFICATION] Payment processing continues despite notification failure")
                                            import traceback
                                            traceback.print_exc()


                                    else:
                                        logger.error(f"❌ [ORCHESTRATION] Failed to enqueue to PGP_ORCHESTRATOR_v1", exc_info=True)
                                        logger.warning(f"⚠️ [ORCHESTRATION] Payment validated but not queued for processing!")

                                except Exception as e:
                                    logger.error(f"❌ [ORCHESTRATION] Error queuing to PGP_ORCHESTRATOR_v1: {e}", exc_info=True)
                                    import traceback
                                    traceback.print_exc()
                        else:
                            logger.warning(f"⚠️ [ORCHESTRATION] Could not fetch subscription data for PGP_ORCHESTRATOR_v1 triggering")

        except Exception as e:
            logger.error(f"❌ [DATABASE] Failed to update outcome_amount_usd: {e}", exc_info=True)
            import traceback
            traceback.print_exc()

    logger.info(f"✅ [IPN] IPN processed successfully")
    logger.info(f"🎯 [IPN] payment_id {payment_data['payment_id']} stored in database")
    return jsonify({"status": "success", "message": "IPN processed"}), 200


# ============================================================================
# PAYMENT STATUS API ENDPOINT (FOR LANDING PAGE POLLING)
# ============================================================================

@app.route('/api/payment-status', methods=['GET'])
def payment_status_api():
    """
    API endpoint for landing page to poll payment confirmation status.

    Query Parameters:
        order_id (str): NowPayments order_id (format: PGP-{user_id}|{open_channel_id})

    Returns:
        JSON: {
            "status": "pending" | "confirmed" | "error",
            "message": "descriptive message",
            "data": {
                "order_id": str,
                "payment_status": str,
                "confirmed": bool
            }
        }
    """
    logger.info(f"📡 [API] Payment Status Request Received")

    # Get order_id from query parameters
    order_id = request.args.get('order_id')

    if not order_id:
        logger.error(f"❌ [API] Missing order_id parameter")
        return jsonify({
            "status": "error",
            "message": "Missing order_id parameter",
            "data": None
        }), 400

    logger.debug(f"🔍 [API] Looking up payment status for order_id: {order_id}")

    try:
        # Parse order_id to get user_id and open_channel_id
        user_id, open_channel_id = db_manager.parse_order_id(order_id) if db_manager else (None, None)

        if not user_id or not open_channel_id:
            logger.error(f"❌ [API] Invalid order_id format: {order_id}")
            return jsonify({
                "status": "error",
                "message": "Invalid order_id format",
                "data": None
            }), 400

        logger.info(f"✅ [API] Parsed order_id:")
        logger.info(f"   User ID: {user_id}")
        logger.info(f"   Open Channel ID: {open_channel_id}")

        # Connect to database
        conn = db_manager.get_connection() if db_manager else None
        if not conn:
            logger.error(f"❌ [API] Failed to connect to database")
            return jsonify({
                "status": "error",
                "message": "Database connection failed",
                "data": None
            }), 500

        cur = conn.cursor()

        # Look up closed_channel_id from main_clients_database
        cur.execute("""
            SELECT closed_channel_id
            FROM main_clients_database
            WHERE open_channel_id = %s
        """, (open_channel_id,))

        result = cur.fetchone()

        if not result:
            logger.error(f"❌ [API] No channel mapping found for open_channel_id: {open_channel_id}")
            cur.close()
            conn.close()
            return jsonify({
                "status": "error",
                "message": "Channel not found",
                "data": None
            }), 404

        closed_channel_id = result[0]
        logger.info(f"✅ [API] Found closed_channel_id: {closed_channel_id}")

        # Query payment_status from private_channel_users_database
        cur.execute("""
            SELECT payment_status, nowpayments_payment_id, nowpayments_payment_status
            FROM private_channel_users_database
            WHERE user_id = %s AND private_channel_id = %s
            ORDER BY id DESC LIMIT 1
        """, (user_id, closed_channel_id))

        payment_record = cur.fetchone()

        cur.close()
        conn.close()

        if not payment_record:
            logger.warning(f"⚠️ [API] No payment record found")
            logger.info(f"   User ID: {user_id}")
            logger.info(f"   Private Channel ID: {closed_channel_id}")
            return jsonify({
                "status": "pending",
                "message": "Payment record not found - still pending",
                "data": {
                    "order_id": order_id,
                    "payment_status": "pending",
                    "confirmed": False
                }
            }), 200

        payment_status = payment_record[0] or 'pending'
        nowpayments_payment_id = payment_record[1]
        nowpayments_payment_status = payment_record[2]

        logger.info(f"✅ [API] Found payment record:")
        logger.info(f"   Payment Status: {payment_status}")
        logger.info(f"   NowPayments Payment ID: {nowpayments_payment_id}")
        logger.info(f"   NowPayments Status: {nowpayments_payment_status}")

        # Determine response based on payment_status
        if payment_status == 'confirmed':
            logger.info(f"✅ [API] Payment CONFIRMED - IPN validated")
            return jsonify({
                "status": "confirmed",
                "message": "Payment confirmed - redirecting to Telegram",
                "data": {
                    "order_id": order_id,
                    "payment_status": payment_status,
                    "confirmed": True,
                    "payment_id": nowpayments_payment_id
                }
            }), 200
        elif payment_status == 'failed':
            logger.error(f"❌ [API] Payment FAILED")
            return jsonify({
                "status": "failed",
                "message": "Payment failed",
                "data": {
                    "order_id": order_id,
                    "payment_status": payment_status,
                    "confirmed": False
                }
            }), 200
        else:
            logger.info(f"⏳ [API] Payment PENDING - IPN not yet received")
            return jsonify({
                "status": "pending",
                "message": "Payment pending - waiting for confirmation",
                "data": {
                    "order_id": order_id,
                    "payment_status": payment_status,
                    "confirmed": False
                }
            }), 200

    except Exception as e:
        logger.error(f"❌ [API] Error: {e}", exc_info=True)
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": f"Internal server error: {str(e)}",
            "data": None
        }), 500


# ============================================================================
# PAYMENT PROCESSING PAGE - Serve static HTML
# ============================================================================

@app.route('/payment-processing', methods=['GET'])
def payment_processing_page():
    """
    Serve the payment processing page.

    This page polls /api/payment-status to check if payment is confirmed.
    By serving it from the same origin as the API, we eliminate CORS complexity
    and avoid hardcoding URLs (uses window.location.origin).
    """
    try:
        # Read the HTML file
        with open('payment-processing.html', 'r') as f:
            html_content = f.read()

        return html_content, 200, {'Content-Type': 'text/html; charset=utf-8'}
    except Exception as e:
        logger.error(f"❌ [PAGE] Failed to serve payment-processing.html: {e}", exc_info=True)
        return jsonify({"error": "Failed to load payment processing page"}), 500


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    status = {
        "service": "PGP_NP_IPN_v1 NowPayments IPN Handler",
        "status": "healthy",
        "components": {
            "ipn_secret": "configured" if NOWPAYMENTS_IPN_SECRET else "missing",
            "database_credentials": "configured" if all([CLOUD_SQL_CONNECTION_NAME, DATABASE_NAME, DATABASE_USER, DATABASE_PASSWORD]) else "missing",
            "connector": "initialized" if connector else "not_initialized"
        }
    }

    http_status = 200 if all([
        NOWPAYMENTS_IPN_SECRET,
        CLOUD_SQL_CONNECTION_NAME,
        DATABASE_NAME,
        DATABASE_USER,
        DATABASE_PASSWORD,
        connector
    ]) else 503

    return jsonify(status), http_status


# ============================================================================
# GLOBAL ERROR HANDLERS (C-07: Error Sanitization)
# ============================================================================

@app.errorhandler(Exception)
def handle_exception(e):
    """
    Global error handler that sanitizes error messages based on environment.

    C-07 Fix: Prevents sensitive data exposure through error messages.
    - Production: Returns generic error with error ID
    - Development: Returns detailed error for debugging
    """
    # Get environment (defaults to production for safety)
    environment = os.getenv('ENVIRONMENT', 'production')

    # Sanitize error message (shows details only in development)
    sanitized_message = sanitize_error_for_user(e, environment)

    # Create standardized error response with error ID
    error_response, status_code = create_error_response(
        status_code=500,
        message=sanitized_message,
        include_error_id=True
    )

    # Log full error details internally (always, regardless of environment)
    logger.error(
        f"❌ [ERROR] Unhandled exception in PGP_NP_IPN_v1",
        extra={
            'error_id': error_response.get('error_id'),
            'error_type': type(e).__name__,
            'environment': environment
        },
        exc_info=True
    )

    return jsonify(error_response), status_code


@app.errorhandler(400)
def handle_bad_request(e):
    """Handle 400 Bad Request errors with sanitized messages."""
    error_response, _ = create_error_response(400, str(e))
    return jsonify(error_response), 400


@app.errorhandler(404)
def handle_not_found(e):
    """Handle 404 Not Found errors."""
    error_response, _ = create_error_response(404, "Endpoint not found")
    return jsonify(error_response), 404


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    logger.info(f"🌐 [APP] Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port)
