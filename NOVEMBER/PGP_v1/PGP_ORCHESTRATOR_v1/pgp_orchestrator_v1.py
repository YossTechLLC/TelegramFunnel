#!/usr/bin/env python
"""
PGP_ORCHESTRATOR_v1: Payment Processor Service
Receives success_url from NOWPayments API, processes payment confirmation,
writes to database, and enqueues tasks to PGP_INVITE_v1 (Telegram invite)
and PGP_SPLIT1_v1 (payment split).
"""
import time
from datetime import datetime, timedelta
from flask import Flask, request, abort, jsonify

# Import service modules
from config_manager import ConfigManager
from token_manager import TokenManager
from database_manager import DatabaseManager
from cloudtasks_client import CloudTasksClient

app = Flask(__name__)

# Initialize managers
print(f"🚀 [APP] Initializing PGP_ORCHESTRATOR_v1 Payment Processor Service")
config_manager = ConfigManager()
config = config_manager.initialize_config()

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
    signing_key = config.get('success_url_signing_key')

    if not project_id or not location or not signing_key:
        raise ValueError("Cloud Tasks configuration incomplete")

    cloudtasks_client = CloudTasksClient(project_id, location, signing_key)
    print(f"✅ [APP] Cloud Tasks client initialized")
except Exception as e:
    print(f"❌ [APP] Failed to initialize Cloud Tasks client: {e}")
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

    print(f"🕒 [CALC] Expiration calculation: {subscription_time_days} days from {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📅 [CALC] Results: expire_time={expire_time}, expire_date={expire_date}")

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
        print(f"🎯 [ENDPOINT] Payment confirmation received from NOWPayments")

        # Extract token from URL
        token = request.args.get("token")
        if not token:
            print(f"❌ [ENDPOINT] Missing token parameter")
            abort(400, "Missing token")

        # Decode and verify token
        if not token_manager:
            print(f"❌ [ENDPOINT] Token manager not available")
            abort(500, "Service configuration error")

        try:
            user_id, closed_channel_id, wallet_address, payout_currency, payout_network, subscription_time_days, subscription_price = token_manager.decode_and_verify_token(token)
            print(f"✅ [ENDPOINT] Token decoded successfully")
            print(f"👤 [ENDPOINT] User: {user_id}, Channel: {closed_channel_id}")
            print(f"💰 [ENDPOINT] Price: ${subscription_price}, Duration: {subscription_time_days} days")
            print(f"🏦 [ENDPOINT] Wallet: {wallet_address}")
            print(f"🌐 [ENDPOINT] Currency: {payout_currency}, Network: {payout_network}")
        except Exception as e:
            print(f"❌ [ENDPOINT] Token validation error: {e}")
            abort(400, f"Token error: {e}")

        # Calculate expiration time and date
        expire_time, expire_date = calculate_expiration_time(subscription_time_days)
        print(f"📅 [ENDPOINT] Calculated expiration: {expire_time} on {expire_date}")

        # Write to database
        if not db_manager:
            print(f"❌ [ENDPOINT] Database manager not available")
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
                print(f"✅ [ENDPOINT] Database: Successfully recorded subscription")
            else:
                print(f"⚠️ [ENDPOINT] Database: Failed to record subscription")
                # Continue anyway
        except Exception as e:
            print(f"❌ [ENDPOINT] Database error: {e}")
            # Continue anyway

        # ============================================================================
        # DEPRECATED: Payment queuing removed
        # ============================================================================
        print(f"")
        print(f"⚠️ [DEPRECATED] This endpoint no longer queues payments")
        print(f"ℹ️ [DEPRECATED] Payment processing happens via /process-validated-payment")
        print(f"ℹ️ [DEPRECATED] Triggered by np-webhook after IPN validation")
        print(f"")

        print(f"🎉 [ENDPOINT] Payment processing completed successfully")
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print(f"❌ [ENDPOINT] Unexpected error: {e}")
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
        print(f"")
        print(f"=" * 80)
        print(f"🎯 [VALIDATED] Received validated payment from NP-Webhook")

        # Get validated payment data from NP-Webhook
        payment_data = request.get_json()

        if not payment_data:
            print(f"❌ [VALIDATED] No JSON payload received")
            abort(400, "Missing payment data")

        # ============================================================================
        # IDEMPOTENCY CHECK: Verify payment not already processed
        # ============================================================================

        # Extract payment_id early for idempotency check
        nowpayments_payment_id = payment_data.get('nowpayments_payment_id')

        if not nowpayments_payment_id:
            print(f"❌ [VALIDATED] Missing nowpayments_payment_id")
            abort(400, "Missing payment_id for idempotency tracking")

        print(f"")
        print(f"🔍 [IDEMPOTENCY] Checking if payment {nowpayments_payment_id} already processed...")

        if not db_manager:
            print(f"⚠️ [IDEMPOTENCY] Database manager not available - cannot check idempotency")
            print(f"⚠️ [IDEMPOTENCY] Proceeding with processing (fail-open mode)")
        else:
            try:
                conn = db_manager.get_connection()
                if conn:
                    cur = conn.cursor()
                    cur.execute("""
                        SELECT
                            gcwebhook1_processed,
                            gcwebhook1_processed_at
                        FROM processed_payments
                        WHERE payment_id = %s
                    """, (nowpayments_payment_id,))
                    existing = cur.fetchone()
                    cur.close()
                    conn.close()
                else:
                    existing = None

                if existing and existing[0]:  # gcwebhook1_processed is index 0
                    # Payment already processed - return success without re-processing
                    # Tuple indexes: 0=gcwebhook1_processed, 1=gcwebhook1_processed_at
                    gcwebhook1_processed = existing[0]
                    processed_at = existing[1]

                    print(f"✅ [IDEMPOTENCY] Payment already processed")
                    print(f"   Processed at: {processed_at}")
                    print(f"   Payment ID: {nowpayments_payment_id}")
                    print(f"🎉 [VALIDATED] Returning success (no duplicate processing)")
                    print(f"=" * 80)

                    return jsonify({
                        "status": "success",
                        "message": "Payment already processed",
                        "payment_id": nowpayments_payment_id,
                        "processed_at": str(processed_at)
                    }), 200
                else:
                    print(f"🆕 [IDEMPOTENCY] Payment not yet processed - proceeding...")

            except Exception as e:
                print(f"⚠️ [IDEMPOTENCY] Error checking payment status: {e}")
                import traceback
                traceback.print_exc()
                print(f"⚠️ [IDEMPOTENCY] Proceeding with processing (fail-open mode)")

        print(f"")

        # ============================================================================
        # CRITICAL: Defense-in-depth - Validate payment_status again
        # ============================================================================
        payment_status = payment_data.get('payment_status', '').lower()

        ALLOWED_PAYMENT_STATUSES = ['finished']

        print(f"🔍 [GCWEBHOOK1] Payment status received: '{payment_status}'")
        print(f"✅ [GCWEBHOOK1] Allowed statuses: {ALLOWED_PAYMENT_STATUSES}")

        if payment_status not in ALLOWED_PAYMENT_STATUSES:
            print(f"=" * 80)
            print(f"⏸️ [GCWEBHOOK1] PAYMENT STATUS VALIDATION FAILED (Second Layer)")
            print(f"=" * 80)
            print(f"📊 [GCWEBHOOK1] Current status: '{payment_status}'")
            print(f"⏳ [GCWEBHOOK1] Required status: 'finished'")
            print(f"👤 [GCWEBHOOK1] User ID: {payment_data.get('user_id')}")
            print(f"💰 [GCWEBHOOK1] Amount: {payment_data.get('subscription_price')}")
            print(f"🛡️ [GCWEBHOOK1] Defense-in-depth check prevented processing")
            print(f"=" * 80)

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
        print(f"=" * 80)
        print(f"✅ [GCWEBHOOK1] PAYMENT STATUS VALIDATED (Second Layer): '{payment_status}'")
        print(f"✅ [GCWEBHOOK1] Proceeding with instant/threshold routing")
        print(f"=" * 80)

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
            print(f"❌ [VALIDATED] Type conversion error for integer fields: {e}")
            print(f"   user_id: {payment_data.get('user_id')} (type: {type(payment_data.get('user_id'))})")
            print(f"   closed_channel_id: {payment_data.get('closed_channel_id')} (type: {type(payment_data.get('closed_channel_id'))})")
            print(f"   subscription_time_days: {payment_data.get('subscription_time_days')} (type: {type(payment_data.get('subscription_time_days'))})")
            abort(400, f"Invalid integer field types: {e}")

        print(f"")
        print(f"✅ [VALIDATED] Payment Data Received:")
        print(f"   User ID: {user_id}")
        print(f"   Channel ID: {closed_channel_id}")
        print(f"   Wallet: {wallet_address}")
        print(f"   Payout: {payout_currency} on {payout_network}")
        print(f"   Subscription Days: {subscription_time_days}")
        print(f"   Declared Price: ${subscription_price}")
        print(f"   💰 ACTUAL Outcome (USD): ${outcome_amount_usd}")
        print(f"   💰 ACTUAL Outcome (ETH): {nowpayments_outcome_amount}")  # ✅ ADD LOG
        print(f"   Payment ID: {nowpayments_payment_id}")

        # Validate required fields
        if not all([user_id, closed_channel_id, outcome_amount_usd]):
            print(f"❌ [VALIDATED] Missing required fields")
            print(f"   user_id: {user_id}")
            print(f"   closed_channel_id: {closed_channel_id}")
            print(f"   outcome_amount_usd: {outcome_amount_usd}")
            abort(400, "Missing required payment data")

        # ========================================================================
        # PAYOUT ROUTING DECISION
        # ========================================================================
        print(f"")
        print(f"🔍 [VALIDATED] Checking payout strategy for channel {closed_channel_id}")

        if not db_manager:
            print(f"❌ [VALIDATED] Database manager not available")
            abort(500, "Database unavailable")

        payout_mode, payout_threshold = db_manager.get_payout_strategy(closed_channel_id)
        print(f"💰 [VALIDATED] Payout mode: {payout_mode}")

        if payout_mode == "threshold":
            print(f"🎯 [VALIDATED] Threshold payout mode - ${payout_threshold} threshold")
            print(f"📊 [VALIDATED] Routing to PGP_ACCUMULATOR for accumulation")

            # Get subscription ID for accumulation record
            subscription_id = db_manager.get_subscription_id(user_id, closed_channel_id)

            # Get PGP_ACCUMULATOR configuration
            pgp_accumulator_queue = config.get('pgp_accumulator_queue')
            pgp_accumulator_url = config.get('pgp_accumulator_url')

            if not pgp_accumulator_queue or not pgp_accumulator_url:
                print(f"❌ [VALIDATED] PGP_ACCUMULATOR configuration missing")
                abort(500, "PGP_ACCUMULATOR configuration error")

            # Queue to PGP_ACCUMULATOR with ACTUAL outcome amount
            print(f"")
            print(f"🚀 [VALIDATED] Queuing to PGP_ACCUMULATOR...")
            print(f"   💰 Using ACTUAL outcome: ${outcome_amount_usd} (not ${subscription_price})")

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
                print(f"✅ [VALIDATED] Successfully enqueued to PGP_ACCUMULATOR")
                print(f"🆔 [VALIDATED] Task: {task_name}")
            else:
                print(f"❌ [VALIDATED] Failed to enqueue to PGP_ACCUMULATOR")
                abort(500, "Failed to enqueue to PGP_ACCUMULATOR")

        else:  # instant payout
            print(f"⚡ [VALIDATED] Instant payout mode - processing immediately")
            print(f"📊 [VALIDATED] Routing to PGP_SPLIT1_v1 for payment split")

            # Get PGP_SPLIT1_v1 configuration
            pgp_split1_queue = config.get('pgp_split1_queue')
            pgp_split1_url = config.get('pgp_split1_url')

            if not pgp_split1_queue or not pgp_split1_url:
                print(f"❌ [VALIDATED] PGP_SPLIT1_v1 configuration missing")
                abort(500, "PGP_SPLIT1_v1 configuration error")

            # Queue to PGP_SPLIT1_v1 with ACTUAL outcome amount
            print(f"")
            print(f"🚀 [VALIDATED] Queuing to PGP_SPLIT1_v1...")
            print(f"   💰 Using ACTUAL outcome: ${outcome_amount_usd} (not ${subscription_price})")

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
                print(f"✅ [VALIDATED] Successfully enqueued to PGP_SPLIT1_v1")
                print(f"🆔 [VALIDATED] Task: {task_name}")
            else:
                print(f"❌ [VALIDATED] Failed to enqueue to PGP_SPLIT1_v1")
                abort(500, "Failed to enqueue to PGP_SPLIT1_v1")

        # ========================================================================
        # TELEGRAM INVITE
        # ========================================================================
        print(f"")
        print(f"📱 [VALIDATED] Queuing Telegram invite to PGP_INVITE_v1")

        if not token_manager:
            print(f"❌ [VALIDATED] Token manager not available")
            abort(500, "Token manager unavailable")

        # Validate subscription data before encryption
        if not subscription_time_days or not subscription_price:
            print(f"❌ [VALIDATED] Missing subscription data:")
            print(f"   subscription_time_days: {subscription_time_days} (type: {type(subscription_time_days)})")
            print(f"   subscription_price: {subscription_price} (type: {type(subscription_price)})")
            abort(400, "Missing subscription data from payment")

        # Ensure subscription_price is string for token encryption
        # (user_id, closed_channel_id, subscription_time_days already converted to int at line 251-253)
        try:
            subscription_price = str(subscription_price)
        except (ValueError, TypeError) as e:
            print(f"❌ [VALIDATED] Invalid type for subscription_price: {e}")
            print(f"   subscription_price: {subscription_price} (type: {type(subscription_price)})")
            abort(400, "Invalid subscription_price type")

        encrypted_token = token_manager.encrypt_token_for_gcwebhook2(
            user_id=user_id,
            closed_channel_id=closed_channel_id,
            wallet_address=wallet_address,
            payout_currency=payout_currency,
            payout_network=payout_network,
            subscription_time_days=subscription_time_days,
            subscription_price=subscription_price
        )

        if not encrypted_token:
            print(f"❌ [VALIDATED] Failed to encrypt token for PGP_INVITE_v1")
            abort(500, "Token encryption failed")

        pgp_invite_queue = config.get('pgp_invite_queue')
        pgp_invite_url = config.get('pgp_invite_url')

        if not pgp_invite_queue or not pgp_invite_url:
            print(f"⚠️ [VALIDATED] PGP_INVITE_v1 configuration missing - skipping invite")
        else:
            task_name_gcwebhook2 = cloudtasks_client.enqueue_pgp_invite_telegram_invite(
                queue_name=pgp_invite_queue,
                target_url=pgp_invite_url,
                encrypted_token=encrypted_token,
                payment_id=nowpayments_payment_id
            )

            if task_name_gcwebhook2:
                print(f"✅ [VALIDATED] Enqueued Telegram invite to PGP_INVITE_v1")
                print(f"🆔 [VALIDATED] Task: {task_name_gcwebhook2}")
            else:
                print(f"⚠️ [VALIDATED] Failed to enqueue Telegram invite")

        # ============================================================================
        # IDEMPOTENCY: Mark payment as processed
        # ============================================================================

        try:
            conn = db_manager.get_connection()
            if conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE processed_payments
                    SET
                        gcwebhook1_processed = TRUE,
                        gcwebhook1_processed_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE payment_id = %s
                """, (nowpayments_payment_id,))
                conn.commit()
                cur.close()
                conn.close()

                print(f"")
                print(f"✅ [IDEMPOTENCY] Marked payment {nowpayments_payment_id} as processed")
            else:
                print(f"⚠️ [IDEMPOTENCY] Could not get database connection")
        except Exception as e:
            # Non-critical error - payment already enqueued successfully
            print(f"⚠️ [IDEMPOTENCY] Failed to mark payment as processed: {e}")
            print(f"⚠️ [IDEMPOTENCY] Payment processing will continue (non-blocking error)")

        print(f"")
        print(f"🎉 [VALIDATED] Payment processing completed successfully")
        print(f"=" * 80)

        return jsonify({
            "status": "success",
            "message": "Payment processed with actual outcome amount",
            "outcome_amount_usd": outcome_amount_usd,
            "declared_price": subscription_price,
            "difference": outcome_amount_usd - float(subscription_price)
        }), 200

    except Exception as e:
        print(f"❌ [VALIDATED] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e)
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
            "service": "PGP_ORCHESTRATOR_v1 Payment Processor",
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
            "service": "PGP_ORCHESTRATOR_v1 Payment Processor",
            "error": str(e)
        }), 503


# ============================================================================
# FLASK ENTRYPOINT
# ============================================================================

if __name__ == "__main__":
    print(f"🚀 [APP] Starting PGP_ORCHESTRATOR_v1 on port 8080")
    app.run(host="0.0.0.0", port=8080, debug=False)
