#!/usr/bin/env python
"""
PGP_ORCHESTRATOR_v1: Payment Processor Service
Receives success_url from NOWPayments API, processes payment confirmation,
writes to database, and enqueues tasks to PGP_INVITE_v1 (Telegram invite)
and PGP_SPLIT1_v1 (payment split).
"""
import os
import time
from datetime import datetime, timedelta
from flask import Flask, request, abort, jsonify

# Import logging
from PGP_COMMON.logging import setup_logger

# Import security utilities (C-07 fix)
from PGP_COMMON.utils import sanitize_error_for_user, create_error_response

# Import service modules
from config_manager import ConfigManager
from token_manager import TokenManager
from database_manager import DatabaseManager
from cloudtasks_client import CloudTasksClient

app = Flask(__name__)

# Initialize logger
logger = setup_logger(__name__)

# Initialize managers
logger.info("🚀 [APP] Initializing PGP_ORCHESTRATOR_v1 Payment Processor Service")
config_manager = ConfigManager()
config = config_manager.initialize_config()

# Initialize token manager
try:
    signing_key = config.get('success_url_signing_key')
    if not signing_key:
        raise ValueError("SUCCESS_URL_SIGNING_KEY not available")
    token_manager = TokenManager(signing_key)
    logger.info("✅ [APP] Token manager initialized")
except Exception as e:
    logger.error(f"❌ [APP] Failed to initialize token manager: {e}", exc_info=True)
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
    logger.info("✅ [APP] Database manager initialized")
except Exception as e:
    logger.error(f"❌ [APP] Failed to initialize database manager: {e}", exc_info=True)
    db_manager = None

# Initialize Cloud Tasks client
try:
    project_id = config.get('cloud_tasks_project_id')
    location = config.get('cloud_tasks_location')
    signing_key = config.get('success_url_signing_key')

    if not project_id or not location or not signing_key:
        raise ValueError("Cloud Tasks configuration incomplete")

    cloudtasks_client = CloudTasksClient(project_id, location, signing_key)
    logger.info("✅ [APP] Cloud Tasks client initialized")
except Exception as e:
    logger.error(f"❌ [APP] Failed to initialize Cloud Tasks client: {e}", exc_info=True)
    cloudtasks_client = None


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def calculate_expiration_time(subscription_time_days: int) -> tuple:
    """
    Calculate expiration time and date based on subscription time in days.

    Args:
        subscription_time_days: Subscription duration in days

    Returns:
        Tuple of (expire_time, expire_date) in PostgreSQL format
        - expire_time: HH:MM:SS format
        - expire_date: YYYY-MM-DD format
    """
    # Get current datetime
    now = datetime.now()

    # Add subscription days to current time
    expiration_datetime = now + timedelta(days=subscription_time_days)

    # Format for PostgreSQL
    expire_time = expiration_datetime.strftime('%H:%M:%S')
    expire_date = expiration_datetime.strftime('%Y-%m-%d')

    logger.debug(f"🕒 [CALC] Expiration calculation: {subscription_time_days} days from {now.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.debug(f"📅 [CALC] Results: expire_time={expire_time}, expire_date={expire_date}")

    return expire_time, expire_date


# ============================================================================
# MAIN ENDPOINT: GET / - Receives success_url from NOWPayments
# ============================================================================

@app.route("/", methods=["GET"])
def process_payment():
    """
    Main endpoint for processing payment confirmations from NOWPayments success_url.

    Flow:
    1. Decode and verify token from URL parameter
    2. Calculate expiration time/date
    3. Write to database (private_channel_users_database)
    4. Encrypt and enqueue to PGP_INVITE_v1 (Telegram invite)
    5. Enqueue to PGP_SPLIT1_v1 (payment split)
    6. Return 200 to NOWPayments

    Returns:
        JSON response with status
    """
    try:
        logger.info(f"🎯 [ENDPOINT] Payment confirmation received from NOWPayments")

        # Extract token from URL
        token = request.args.get("token")
        if not token:
            logger.error(f"❌ [ENDPOINT] Missing token parameter", exc_info=True)
            abort(400, "Missing token")

        # Decode and verify token
        if not token_manager:
            logger.error(f"❌ [ENDPOINT] Token manager not available", exc_info=True)
            abort(500, "Service configuration error")

        try:
            user_id, closed_channel_id, wallet_address, payout_currency, payout_network, subscription_time_days, subscription_price = token_manager.decode_and_verify_token(token)
            logger.info(f"✅ [ENDPOINT] Token decoded successfully")
            logger.info(f"👤 [ENDPOINT] User: {user_id}, Channel: {closed_channel_id}")
            logger.info(f"💰 [ENDPOINT] Price: ${subscription_price}, Duration: {subscription_time_days} days")
            logger.info(f"🏦 [ENDPOINT] Wallet: {wallet_address}")
            logger.info(f"🌐 [ENDPOINT] Currency: {payout_currency}, Network: {payout_network}")
        except Exception as e:
            logger.error(f"❌ [ENDPOINT] Token validation error: {e}", exc_info=True)
            abort(400, f"Token error: {e}")

        # Calculate expiration time and date
        expire_time, expire_date = calculate_expiration_time(subscription_time_days)
        logger.info(f"📅 [ENDPOINT] Calculated expiration: {expire_time} on {expire_date}")

        # Write to database
        if not db_manager:
            logger.error(f"❌ [ENDPOINT] Database manager not available", exc_info=True)
            abort(500, "Database unavailable")

        try:
            success = db_manager.record_private_channel_user(
                user_id=user_id,
                private_channel_id=closed_channel_id,
                sub_time=subscription_time_days,
                sub_price=subscription_price,
                expire_time=expire_time,
                expire_date=expire_date,
                is_active=True
            )
            if success:
                logger.info(f"✅ [ENDPOINT] Database: Successfully recorded subscription")
            else:
                logger.warning(f"⚠️ [ENDPOINT] Database: Failed to record subscription")
                # Continue anyway
        except Exception as e:
            logger.error(f"❌ [ENDPOINT] Database error: {e}", exc_info=True)
            # Continue anyway

        # ============================================================================
        # DEPRECATED: Payment queuing removed
        # ============================================================================
        logger.debug("")
        logger.warning(f"⚠️ [DEPRECATED] This endpoint no longer queues payments")
        logger.info(f"ℹ️ [DEPRECATED] Payment processing happens via /process-validated-payment")
        logger.info(f"ℹ️ [DEPRECATED] Triggered by np-webhook after IPN validation")
        logger.debug("")

        logger.info(f"🎉 [ENDPOINT] Payment processing completed successfully")
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logger.error(f"❌ [ENDPOINT] Unexpected error: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": f"Processing error: {str(e)}"
        }), 500


# ============================================================================
# NEW ENDPOINT: POST /process-validated-payment
# Receives validated payment data from NP-Webhook and orchestrates processing
# ============================================================================

@app.route("/process-validated-payment", methods=["POST"])
def process_validated_payment():
    """
    Process a payment that has been validated by np-webhook.

    This endpoint is called by np-webhook AFTER:
    - IPN signature validation
    - CoinGecko price fetch
    - Outcome USD amount calculation
    - Database update with outcome_amount_usd

    Flow:
    1. Receive validated payment data from np-webhook
    2. Extract outcome_amount_usd (ACTUAL USD value)
    3. Lookup payout strategy (instant vs threshold)
    4. Route to PGP_SPLIT1_v1 (instant) or PGP_ACCUMULATOR (threshold) with REAL amount
    5. Queue Telegram invite to PGP_INVITE_v1

    CRITICAL: This endpoint ensures all payments are processed with
    the ACTUAL crypto outcome value in USD, not the declared subscription price.
    """
    try:
        logger.debug("")
        logger.info(f"=" * 80)
        logger.info(f"🎯 [VALIDATED] Received validated payment from NP-Webhook")

        # Get validated payment data from NP-Webhook
        payment_data = request.get_json()

        if not payment_data:
            logger.error(f"❌ [VALIDATED] No JSON payload received", exc_info=True)
            abort(400, "Missing payment data")

        # ============================================================================
        # IDEMPOTENCY CHECK: Verify payment not already processed
        # ============================================================================

        # Extract payment_id early for idempotency check
        nowpayments_payment_id = payment_data.get('nowpayments_payment_id')

        if not nowpayments_payment_id:
            logger.error(f"❌ [VALIDATED] Missing nowpayments_payment_id", exc_info=True)
            abort(400, "Missing payment_id for idempotency tracking")

        logger.debug("")
        logger.debug(f"🔍 [IDEMPOTENCY] Atomically checking and marking payment {nowpayments_payment_id}...")

        if not db_manager:
            logger.warning(f"⚠️ [IDEMPOTENCY] Database manager not available - cannot check idempotency")
            logger.warning(f"⚠️ [IDEMPOTENCY] Proceeding with processing (fail-open mode)")
        else:
            try:
                # Use atomic UPSERT to prevent race conditions (C-04 fix)
                is_new_payment = db_manager.mark_payment_processed_atomic(
                    payment_id=nowpayments_payment_id,
                    service_name='pgp_orchestrator'
                )

                if not is_new_payment:
                    # Payment already processed by another request (race condition prevented)
                    logger.info(f"✅ [IDEMPOTENCY] Payment already processed (atomic check)")
                    logger.info(f"   Payment ID: {nowpayments_payment_id}")
                    logger.info(f"🎉 [VALIDATED] Returning success (duplicate prevented)")
                    logger.info(f"=" * 80)

                    return jsonify({
                        "status": "success",
                        "message": "Payment already processed",
                        "payment_id": nowpayments_payment_id
                    }), 200
                else:
                    logger.info(f"🆕 [IDEMPOTENCY] Payment atomically marked as processing - proceeding...")

            except Exception as e:
                logger.warning(f"⚠️ [IDEMPOTENCY] Error in atomic payment check: {e}")
                import traceback
                traceback.print_exc()
                logger.warning(f"⚠️ [IDEMPOTENCY] Proceeding with processing (fail-open mode)")

        logger.debug("")

        # ============================================================================
        # CRITICAL: Defense-in-depth - Validate payment_status again
        # ============================================================================
        payment_status = payment_data.get('payment_status', '').lower()

        ALLOWED_PAYMENT_STATUSES = ['finished']

        logger.debug(f"🔍 [GCWEBHOOK1] Payment status received: '{payment_status}'")
        logger.info(f"✅ [GCWEBHOOK1] Allowed statuses: {ALLOWED_PAYMENT_STATUSES}")

        if payment_status not in ALLOWED_PAYMENT_STATUSES:
            logger.info(f"=" * 80)
            logger.info(f"⏸️ [GCWEBHOOK1] PAYMENT STATUS VALIDATION FAILED (Second Layer)")
            logger.info(f"=" * 80)
            logger.info(f"📊 [GCWEBHOOK1] Current status: '{payment_status}'")
            logger.info(f"⏳ [GCWEBHOOK1] Required status: 'finished'")
            logger.info(f"👤 [GCWEBHOOK1] User ID: {payment_data.get('user_id')}")
            logger.info(f"💰 [GCWEBHOOK1] Amount: {payment_data.get('subscription_price')}")
            logger.info(f"🛡️ [GCWEBHOOK1] Defense-in-depth check prevented processing")
            logger.info(f"=" * 80)

            # Return 200 OK to prevent Cloud Tasks retry
            # This should never happen if np-webhook is working correctly
            return jsonify({
                "status": "rejected",
                "message": f"Payment status not ready for processing (current: {payment_status})",
                "payment_status": payment_status,
                "required_status": "finished",
                "defense_layer": "gcwebhook1_second_layer"
            }), 200

        # If we reach here, payment_status is 'finished' - proceed with routing
        logger.info(f"=" * 80)
        logger.info(f"✅ [GCWEBHOOK1] PAYMENT STATUS VALIDATED (Second Layer): '{payment_status}'")
        logger.info(f"✅ [GCWEBHOOK1] Proceeding with instant/threshold routing")
        logger.info(f"=" * 80)

        # Extract all required fields
        user_id = payment_data.get('user_id')
        closed_channel_id = payment_data.get('closed_channel_id')
        wallet_address = payment_data.get('wallet_address')
        payout_currency = payment_data.get('payout_currency')
        payout_network = payment_data.get('payout_network')
        subscription_time_days = payment_data.get('subscription_time_days')
        subscription_price = payment_data.get('subscription_price')

        # CRITICAL: This is the ACTUAL outcome amount in USD from CoinGecko
        outcome_amount_usd = payment_data.get('outcome_amount_usd')

        # NowPayments metadata (payment_id already extracted for idempotency check)
        nowpayments_pay_address = payment_data.get('nowpayments_pay_address')
        nowpayments_outcome_amount = payment_data.get('nowpayments_outcome_amount')

        # Normalize types immediately after extraction (defensive coding)
        # JSON can send integers as strings, so convert to proper types
        try:
            user_id = int(user_id) if user_id is not None else None
            closed_channel_id = int(closed_channel_id) if closed_channel_id is not None else None
            subscription_time_days = int(subscription_time_days) if subscription_time_days is not None else None
        except (ValueError, TypeError) as e:
            logger.error(f"❌ [VALIDATED] Type conversion error for integer fields: {e}", exc_info=True)
            logger.info(f"   user_id: {payment_data.get('user_id')} (type: {type(payment_data.get('user_id'))})")
            logger.info(f"   closed_channel_id: {payment_data.get('closed_channel_id')} (type: {type(payment_data.get('closed_channel_id'))})")
            logger.info(f"   subscription_time_days: {payment_data.get('subscription_time_days')} (type: {type(payment_data.get('subscription_time_days'))})")
            abort(400, f"Invalid integer field types: {e}")

        logger.debug("")
        logger.info(f"✅ [VALIDATED] Payment Data Received:")
        logger.info(f"   User ID: {user_id}")
        logger.info(f"   Channel ID: {closed_channel_id}")
        logger.info(f"   Wallet: {wallet_address}")
        logger.info(f"   Payout: {payout_currency} on {payout_network}")
        logger.info(f"   Subscription Days: {subscription_time_days}")
        logger.info(f"   Declared Price: ${subscription_price}")
        logger.info(f"   💰 ACTUAL Outcome (USD): ${outcome_amount_usd}")
        logger.info(f"   💰 ACTUAL Outcome (ETH): {nowpayments_outcome_amount}")  # ✅ ADD LOG
        logger.info(f"   Payment ID: {nowpayments_payment_id}")

        # Validate required fields
        if not all([user_id, closed_channel_id, outcome_amount_usd]):
            logger.error(f"❌ [VALIDATED] Missing required fields", exc_info=True)
            logger.info(f"   user_id: {user_id}")
            logger.info(f"   closed_channel_id: {closed_channel_id}")
            logger.info(f"   outcome_amount_usd: {outcome_amount_usd}")
            abort(400, "Missing required payment data")

        # ========================================================================
        # PAYOUT ROUTING DECISION
        # ========================================================================
        logger.debug("")
        logger.debug(f"🔍 [VALIDATED] Checking payout strategy for channel {closed_channel_id}")

        if not db_manager:
            logger.error(f"❌ [VALIDATED] Database manager not available", exc_info=True)
            abort(500, "Database unavailable")

        payout_mode, payout_threshold = db_manager.get_payout_strategy(closed_channel_id)
        logger.info(f"💰 [VALIDATED] Payout mode: {payout_mode}")

        if payout_mode == "threshold":
            logger.info(f"🎯 [VALIDATED] Threshold payout mode - ${payout_threshold} threshold")
            logger.info(f"📊 [VALIDATED] Routing to PGP_ACCUMULATOR for accumulation")

            # Get subscription ID for accumulation record
            subscription_id = db_manager.get_subscription_id(user_id, closed_channel_id)

            # Get PGP_ACCUMULATOR configuration
            pgp_accumulator_queue = config.get('pgp_accumulator_queue')
            pgp_accumulator_url = config.get('pgp_accumulator_url')

            if not pgp_accumulator_queue or not pgp_accumulator_url:
                logger.error(f"❌ [VALIDATED] PGP_ACCUMULATOR configuration missing", exc_info=True)
                abort(500, "PGP_ACCUMULATOR configuration error")

            # Queue to PGP_ACCUMULATOR with ACTUAL outcome amount
            logger.debug("")
            logger.info(f"🚀 [VALIDATED] Queuing to PGP_ACCUMULATOR...")
            logger.info(f"   💰 Using ACTUAL outcome: ${outcome_amount_usd} (not ${subscription_price})")

            task_name = cloudtasks_client.enqueue_pgp_accumulator_payment(
                queue_name=pgp_accumulator_queue,
                target_url=pgp_accumulator_url,
                user_id=user_id,
                client_id=closed_channel_id,
                wallet_address=wallet_address,
                payout_currency=payout_currency,
                payout_network=payout_network,
                subscription_price=outcome_amount_usd,  # ✅ ACTUAL USD amount
                subscription_id=subscription_id,
                nowpayments_payment_id=nowpayments_payment_id,
                nowpayments_pay_address=nowpayments_pay_address,
                nowpayments_outcome_amount=nowpayments_outcome_amount
            )

            if task_name:
                logger.info(f"✅ [VALIDATED] Successfully enqueued to PGP_ACCUMULATOR")
                logger.info(f"🆔 [VALIDATED] Task: {task_name}")
            else:
                logger.error(f"❌ [VALIDATED] Failed to enqueue to PGP_ACCUMULATOR", exc_info=True)
                abort(500, "Failed to enqueue to PGP_ACCUMULATOR")

        else:  # instant payout
            logger.info(f"⚡ [VALIDATED] Instant payout mode - processing immediately")
            logger.info(f"📊 [VALIDATED] Routing to PGP_SPLIT1_v1 for payment split")

            # Get PGP_SPLIT1_v1 configuration
            pgp_split1_queue = config.get('pgp_split1_queue')
            pgp_split1_url = config.get('pgp_split1_url')

            if not pgp_split1_queue or not pgp_split1_url:
                logger.error(f"❌ [VALIDATED] PGP_SPLIT1_v1 configuration missing", exc_info=True)
                abort(500, "PGP_SPLIT1_v1 configuration error")

            # Queue to PGP_SPLIT1_v1 with ACTUAL outcome amount
            logger.debug("")
            logger.info(f"🚀 [VALIDATED] Queuing to PGP_SPLIT1_v1...")
            logger.info(f"   💰 Using ACTUAL outcome: ${outcome_amount_usd} (not ${subscription_price})")

            task_name = cloudtasks_client.enqueue_pgp_split1_payment_split(
                queue_name=pgp_split1_queue,
                target_url=pgp_split1_url,
                user_id=user_id,
                closed_channel_id=closed_channel_id,
                wallet_address=wallet_address,
                payout_currency=payout_currency,
                payout_network=payout_network,
                subscription_price=outcome_amount_usd,  # ✅ ACTUAL USD amount
                actual_eth_amount=float(nowpayments_outcome_amount) if nowpayments_outcome_amount else 0.0,  # ✅ ADD ACTUAL ETH
                payout_mode='instant'  # ✅ NEW: Pass instant mode to PGP_SPLIT1_v1
            )

            if task_name:
                logger.info(f"✅ [VALIDATED] Successfully enqueued to PGP_SPLIT1_v1")
                logger.info(f"🆔 [VALIDATED] Task: {task_name}")
            else:
                logger.error(f"❌ [VALIDATED] Failed to enqueue to PGP_SPLIT1_v1", exc_info=True)
                abort(500, "Failed to enqueue to PGP_SPLIT1_v1")

        # ========================================================================
        # TELEGRAM INVITE
        # ========================================================================
        logger.debug("")
        logger.info(f"📱 [VALIDATED] Queuing Telegram invite to PGP_INVITE_v1")

        if not token_manager:
            logger.error(f"❌ [VALIDATED] Token manager not available", exc_info=True)
            abort(500, "Token manager unavailable")

        # Validate subscription data before encryption
        if not subscription_time_days or not subscription_price:
            logger.error(f"❌ [VALIDATED] Missing subscription data:", exc_info=True)
            logger.info(f"   subscription_time_days: {subscription_time_days} (type: {type(subscription_time_days)})")
            logger.info(f"   subscription_price: {subscription_price} (type: {type(subscription_price)})")
            abort(400, "Missing subscription data from payment")

        # Ensure subscription_price is string for token encryption
        # (user_id, closed_channel_id, subscription_time_days already converted to int at line 251-253)
        try:
            subscription_price = str(subscription_price)
        except (ValueError, TypeError) as e:
            logger.error(f"❌ [VALIDATED] Invalid type for subscription_price: {e}", exc_info=True)
            logger.info(f"   subscription_price: {subscription_price} (type: {type(subscription_price)})")
            abort(400, "Invalid subscription_price type")

        encrypted_token = token_manager.encrypt_token_for_pgp_invite(
            user_id=user_id,
            closed_channel_id=closed_channel_id,
            wallet_address=wallet_address,
            payout_currency=payout_currency,
            payout_network=payout_network,
            subscription_time_days=subscription_time_days,
            subscription_price=subscription_price
        )

        if not encrypted_token:
            logger.error(f"❌ [VALIDATED] Failed to encrypt token for PGP_INVITE_v1", exc_info=True)
            abort(500, "Token encryption failed")

        pgp_invite_queue = config.get('pgp_invite_queue')
        pgp_invite_url = config.get('pgp_invite_url')

        if not pgp_invite_queue or not pgp_invite_url:
            logger.warning(f"⚠️ [VALIDATED] PGP_INVITE_v1 configuration missing - skipping invite")
        else:
            task_name_gcwebhook2 = cloudtasks_client.enqueue_pgp_invite_telegram_invite(
                queue_name=pgp_invite_queue,
                target_url=pgp_invite_url,
                encrypted_token=encrypted_token,
                payment_id=nowpayments_payment_id
            )

            if task_name_gcwebhook2:
                logger.info(f"✅ [VALIDATED] Enqueued Telegram invite to PGP_INVITE_v1")
                logger.info(f"🆔 [VALIDATED] Task: {task_name_gcwebhook2}")
            else:
                logger.warning(f"⚠️ [VALIDATED] Failed to enqueue Telegram invite")

        # ============================================================================
        # IDEMPOTENCY: Mark payment as processed
        # ============================================================================
        # NOTE: Payment already marked as processed atomically at the start (C-04 fix)
        # The atomic UPSERT prevents race conditions and ensures idempotency
        # No need for separate UPDATE here - it was done in one atomic operation

        logger.debug("")
        logger.info(f"🎉 [VALIDATED] Payment processing completed successfully")
        logger.info(f"=" * 80)

        return jsonify({
            "status": "success",
            "message": "Payment processed with actual outcome amount",
            "outcome_amount_usd": outcome_amount_usd,
            "declared_price": subscription_price,
            "difference": outcome_amount_usd - float(subscription_price)
        }), 200

    except Exception as e:
        logger.error(f"❌ [VALIDATED] Unexpected error: {e}", exc_info=True)
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


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
        f"❌ [ERROR] Unhandled exception in PGP_ORCHESTRATOR_v1",
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
# HEALTH CHECK ENDPOINT
# ============================================================================

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for monitoring."""
    try:
        return jsonify({
            "status": "healthy",
            "service": "PGP_ORCHESTRATOR_v1 Payment Processor",
            "timestamp": int(time.time()),
            "components": {
                "token_manager": "healthy" if token_manager else "unhealthy",
                "database": "healthy" if db_manager else "unhealthy",
                "cloudtasks": "healthy" if cloudtasks_client else "unhealthy"
            }
        }), 200

    except Exception as e:
        logger.error(f"❌ [HEALTH] Health check failed: {e}", exc_info=True)
        return jsonify({
            "status": "unhealthy",
            "service": "PGP_ORCHESTRATOR_v1 Payment Processor",
            "error": str(e)
        }), 503


# ============================================================================
# FLASK ENTRYPOINT
# ============================================================================

if __name__ == "__main__":
    logger.info(f"🚀 [APP] Starting PGP_ORCHESTRATOR_v1 on port 8080")
    app.run(host="0.0.0.0", port=8080, debug=False)
