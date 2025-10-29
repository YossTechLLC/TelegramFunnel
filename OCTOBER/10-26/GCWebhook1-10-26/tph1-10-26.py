#!/usr/bin/env python
"""
GCWebhook1-10-26: Payment Processor Service
Receives success_url from NOWPayments API, processes payment confirmation,
writes to database, and enqueues tasks to GCWebhook2 (Telegram invite)
and GCSplit1 (payment split).
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
print(f"🚀 [APP] Initializing GCWebhook1-10-26 Payment Processor Service")
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
    4. Encrypt and enqueue to GCWebhook2 (Telegram invite)
    5. Enqueue to GCSplit1 (payment split)
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
                # Continue anyway - enqueue tasks for retry
        except Exception as e:
            print(f"❌ [ENDPOINT] Database error: {e}")
            # Continue anyway - enqueue tasks for retry

        # ============================================================================
        # NEW: Check payout strategy and route accordingly
        # ============================================================================
        print(f"🔍 [ENDPOINT] Checking payout strategy for channel {closed_channel_id}")
        payout_strategy, payout_threshold = db_manager.get_payout_strategy(closed_channel_id)

        print(f"💰 [ENDPOINT] Payout strategy: {payout_strategy}")
        if payout_strategy == 'threshold':
            print(f"🎯 [ENDPOINT] Threshold payout mode - ${payout_threshold} threshold")
            print(f"📊 [ENDPOINT] Will accumulate in USDT to eliminate volatility")

            # Get subscription ID for accumulation record
            subscription_id = db_manager.get_subscription_id(user_id, closed_channel_id)

            # Route to GCAccumulator instead of GCSplit1
            gcaccumulator_queue = config.get('gcaccumulator_queue')
            gcaccumulator_url = config.get('gcaccumulator_url')

            if not gcaccumulator_queue or not gcaccumulator_url:
                print(f"⚠️ [ENDPOINT] GCAccumulator config missing - falling back to instant payout")
                payout_strategy = 'instant'  # Fallback to instant
            else:
                # Enqueue to GCAccumulator
                task_name_accumulator = cloudtasks_client.enqueue_gcaccumulator_payment(
                    queue_name=gcaccumulator_queue,
                    target_url=gcaccumulator_url,
                    user_id=user_id,
                    client_id=closed_channel_id,
                    wallet_address=wallet_address,
                    payout_currency=payout_currency,
                    payout_network=payout_network,
                    subscription_price=subscription_price,
                    subscription_id=subscription_id
                )

                if task_name_accumulator:
                    print(f"✅ [ENDPOINT] Enqueued to GCAccumulator for threshold payout")
                    print(f"🆔 [ENDPOINT] Task: {task_name_accumulator}")
                else:
                    print(f"❌ [ENDPOINT] Failed to enqueue to GCAccumulator - falling back to instant")
                    payout_strategy = 'instant'  # Fallback to instant
        else:
            print(f"⚡ [ENDPOINT] Instant payout mode - processing immediately")

        # ============================================================================
        # Continue with existing flow (Telegram invite always sent)
        # ============================================================================

        # Encrypt token for GCWebhook2
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
            print(f"❌ [ENDPOINT] Failed to encrypt token for GCWebhook2")
            abort(500, "Token encryption failed")

        # Enqueue Telegram invite to GCWebhook2
        if not cloudtasks_client:
            print(f"❌ [ENDPOINT] Cloud Tasks client not available")
            abort(500, "Cloud Tasks unavailable")

        gcwebhook2_queue = config.get('gcwebhook2_queue')
        gcwebhook2_url = config.get('gcwebhook2_url')

        if not gcwebhook2_queue or not gcwebhook2_url:
            print(f"❌ [ENDPOINT] GCWebhook2 configuration missing")
            abort(500, "Service configuration error")

        task_name_gcwebhook2 = cloudtasks_client.enqueue_gcwebhook2_telegram_invite(
            queue_name=gcwebhook2_queue,
            target_url=gcwebhook2_url,
            encrypted_token=encrypted_token
        )

        if not task_name_gcwebhook2:
            print(f"❌ [ENDPOINT] Failed to enqueue Telegram invite to GCWebhook2")
            # Don't abort - continue to enqueue payment split
        else:
            print(f"✅ [ENDPOINT] Enqueued Telegram invite to GCWebhook2")
            print(f"🆔 [ENDPOINT] Task: {task_name_gcwebhook2}")

        # Enqueue payment split to GCSplit1 (ONLY for instant payout)
        if payout_strategy == 'instant':
            print(f"⚡ [ENDPOINT] Routing to GCSplit1 for instant payout")
            gcsplit1_queue = config.get('gcsplit1_queue')
            gcsplit1_url = config.get('gcsplit1_url')

            if not gcsplit1_queue or not gcsplit1_url:
                print(f"❌ [ENDPOINT] GCSplit1 configuration missing")
                abort(500, "Service configuration error")

            task_name_gcsplit1 = cloudtasks_client.enqueue_gcsplit1_payment_split(
                queue_name=gcsplit1_queue,
                target_url=gcsplit1_url,
                user_id=user_id,
                closed_channel_id=closed_channel_id,
                wallet_address=wallet_address,
                payout_currency=payout_currency,
                payout_network=payout_network,
                subscription_price=subscription_price
            )

            if not task_name_gcsplit1:
                print(f"❌ [ENDPOINT] Failed to enqueue payment split to GCSplit1")
                # Don't abort - at least Telegram invite was enqueued
            else:
                print(f"✅ [ENDPOINT] Enqueued payment split to GCSplit1")
                print(f"🆔 [ENDPOINT] Task: {task_name_gcsplit1}")
        else:
            print(f"📊 [ENDPOINT] Skipping GCSplit1 - using threshold accumulation instead")

        print(f"🎉 [ENDPOINT] Payment processing completed successfully")
        return jsonify({"status": "ok"}), 200

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
            "service": "GCWebhook1-10-26 Payment Processor",
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
            "service": "GCWebhook1-10-26 Payment Processor",
            "error": str(e)
        }), 503


# ============================================================================
# FLASK ENTRYPOINT
# ============================================================================

if __name__ == "__main__":
    print(f"🚀 [APP] Starting GCWebhook1-10-26 on port 8080")
    app.run(host="0.0.0.0", port=8080, debug=False)
