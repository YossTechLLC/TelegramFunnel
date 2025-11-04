#!/usr/bin/env python
"""
GCWebhook2-10-26: Telegram Invite Sender Service
Receives encrypted tokens from GCWebhook1 via Cloud Tasks,
sends Telegram one-time invitation links to users.
Implements infinite retry via Cloud Tasks (60s fixed backoff, 24h max duration).

ARCHITECTURE - Sync Route with asyncio.run():
This service uses a SYNCHRONOUS Flask route with asyncio.run() to handle
python-telegram-bot's async API calls. This approach is optimal for Cloud Run.

Why sync route with asyncio.run():
- Creates a fresh, isolated event loop for EACH request
- Prevents "Event loop is closed" errors in serverless environments
- Each request gets a fresh Bot instance with new httpx connection pool
- Event loop lifecycle is contained within the request scope
- Cloud Run's stateless model works perfectly with this pattern
- Previous async route approach failed because event loops closed between requests

Key Implementation:
- Bot instance created per-request (not at module level)
- asyncio.run() creates isolated event loop for async telegram operations
- Event loop and connections properly cleaned up after each request
"""
import time
import asyncio
from flask import Flask, request, abort, jsonify
from telegram import Bot
from telegram.error import TelegramError

# Import service modules
from config_manager import ConfigManager
from token_manager import TokenManager
from database_manager import DatabaseManager

app = Flask(__name__)

# Initialize managers
print(f"🚀 [APP] Initializing GCWebhook2-10-26 Telegram Invite Sender Service")
config_manager = ConfigManager()
config = config_manager.initialize_config()

# Initialize database manager for payment validation
try:
    db_manager = DatabaseManager(
        instance_connection_name=config.get('instance_connection_name'),
        db_name=config.get('db_name'),
        db_user=config.get('db_user'),
        db_password=config.get('db_password'),
        payment_min_tolerance=config.get('payment_min_tolerance', 0.50),
        payment_fallback_tolerance=config.get('payment_fallback_tolerance', 0.75)
    )
    print(f"✅ [APP] Database manager initialized for payment validation")
except Exception as e:
    print(f"❌ [APP] Failed to initialize database manager: {e}")
    print(f"⚠️ [APP] Payment validation will fail without database connection")
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

# Store bot token at module level (Bot instance created per-request)
try:
    bot_token = config.get('telegram_bot_token')
    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN not available")
    print(f"✅ [APP] Telegram bot token loaded (Bot instance will be created per-request)")
except Exception as e:
    print(f"❌ [APP] Failed to load Telegram bot token: {e}")
    bot_token = None


# ============================================================================
# MAIN ENDPOINT: POST / - Receives request from GCWebhook1 via Cloud Tasks
# ============================================================================

@app.route("/", methods=["POST"])
def send_telegram_invite():
    """
    Main endpoint for sending Telegram invites.

    Flow:
    1. Decrypt token from GCWebhook1
    2. Create fresh Bot instance for this request
    3. Use asyncio.run() to execute async telegram operations in isolated event loop
    4. Create Telegram invite link
    5. Send invite message to user
    6. Return 200 (Cloud Tasks marks success)
    7. If error: Return 500 (Cloud Tasks retries after 60s)

    Returns:
        JSON response with status
    """
    try:
        print(f"🎯 [ENDPOINT] Telegram invite request received (from GCWebhook1)")

        # Parse JSON payload
        try:
            request_data = request.get_json()
            if not request_data:
                abort(400, "Invalid JSON payload")
        except Exception as e:
            print(f"❌ [ENDPOINT] JSON parsing error: {e}")
            abort(400, "Malformed JSON payload")

        encrypted_token = request_data.get('token')
        payment_id = request_data.get('payment_id')

        if not encrypted_token:
            print(f"❌ [ENDPOINT] Missing token")
            abort(400, "Missing token")

        if not payment_id:
            print(f"❌ [ENDPOINT] Missing payment_id")
            abort(400, "Missing payment_id for idempotency tracking")

        print(f"📋 [ENDPOINT] Payment ID: {payment_id}")

        # ================================================================
        # IDEMPOTENCY CHECK: Check if invite already sent for this payment
        # ================================================================

        print(f"")
        print(f"🔍 [IDEMPOTENCY] Checking if invite already sent for payment {payment_id}...")

        if not db_manager:
            print(f"⚠️ [IDEMPOTENCY] Database manager not available - cannot check idempotency")
            print(f"⚠️ [IDEMPOTENCY] Proceeding with invite send (fail-open mode)")
        else:
            try:
                conn = db_manager.get_connection()
                if conn:
                    cur = conn.cursor()
                    cur.execute("""
                        SELECT
                            telegram_invite_sent,
                            telegram_invite_link,
                            telegram_invite_sent_at
                        FROM processed_payments
                        WHERE payment_id = %s
                    """, (payment_id,))
                    existing_invite = cur.fetchone()
                    cur.close()
                    conn.close()
                else:
                    existing_invite = None

                if existing_invite and existing_invite[0]:  # telegram_invite_sent is index 0
                    # Invite already sent - return success without re-sending
                    # Tuple indexes: 0=telegram_invite_sent, 1=telegram_invite_link, 2=telegram_invite_sent_at
                    telegram_invite_sent = existing_invite[0]
                    existing_link = existing_invite[1]
                    sent_at = existing_invite[2]

                    print(f"✅ [IDEMPOTENCY] Invite already sent for payment {payment_id}")
                    print(f"   Sent at: {sent_at}")
                    print(f"   Link: {existing_link}")
                    print(f"🎉 [ENDPOINT] Returning success (invite already sent)")

                    return jsonify({
                        "status": "success",
                        "message": "Telegram invite already sent",
                        "payment_id": payment_id,
                        "invite_sent_at": str(sent_at)
                    }), 200
                else:
                    print(f"🆕 [IDEMPOTENCY] No existing invite found - proceeding to send")

            except Exception as e:
                print(f"⚠️ [IDEMPOTENCY] Error checking invite status: {e}")
                import traceback
                traceback.print_exc()
                print(f"⚠️ [IDEMPOTENCY] Proceeding with invite send (fail-open mode)")

        print(f"")

        # Decrypt token
        if not token_manager:
            print(f"❌ [ENDPOINT] Token manager not available")
            abort(500, "Service configuration error")

        try:
            user_id, closed_channel_id, wallet_address, payout_currency, payout_network, subscription_time_days, subscription_price = token_manager.decode_and_verify_token(encrypted_token)
            print(f"✅ [ENDPOINT] Token decoded successfully")
            print(f"👤 [ENDPOINT] User: {user_id}, Channel: {closed_channel_id}")
            print(f"💰 [ENDPOINT] Price: ${subscription_price}, Duration: {subscription_time_days} days")
        except Exception as e:
            print(f"❌ [ENDPOINT] Token validation error: {e}")
            abort(400, f"Token error: {e}")

        # ============================================================================
        # PAYMENT VALIDATION - Verify payment completed before sending invite
        # ============================================================================
        if not db_manager:
            print(f"❌ [ENDPOINT] Database manager not available - cannot validate payment")
            abort(500, "Payment validation service unavailable")

        print(f"🔐 [ENDPOINT] Validating payment completion...")
        is_valid, error_message = db_manager.validate_payment_complete(
            user_id=user_id,
            closed_channel_id=closed_channel_id,
            expected_price=subscription_price
        )

        if not is_valid:
            if "IPN callback" in error_message or "pending" in error_message:
                # IPN not yet processed - return 503 for Cloud Tasks retry
                print(f"⏳ [ENDPOINT] Payment validation pending - Cloud Tasks will retry")
                print(f"🔄 [ENDPOINT] Retry reason: {error_message}")
                abort(503, error_message)
            else:
                # Payment invalid - return 400 (no retry)
                print(f"❌ [ENDPOINT] Payment validation failed - will not retry")
                print(f"🚫 [ENDPOINT] Failure reason: {error_message}")
                abort(400, error_message)

        print(f"✅ [ENDPOINT] Payment validation successful - proceeding with invitation")

        # Check bot token availability
        if not bot_token:
            print(f"❌ [ENDPOINT] Telegram bot token not available")
            abort(500, "Telegram bot configuration error")

        # Define async function to handle telegram operations
        async def send_invite_async():
            """
            Async function to handle telegram bot operations.
            Creates fresh Bot instance with isolated httpx connection pool.
            """
            # Create fresh Bot instance for this request
            bot = Bot(bot_token)

            try:
                print(f"📨 [ENDPOINT] Creating Telegram invite link for channel {closed_channel_id}")

                # Create one-time invite link (expires in 1 hour, 1 use only)
                invite = await bot.create_chat_invite_link(
                    chat_id=closed_channel_id,
                    expire_date=int(time.time()) + 3600,
                    member_limit=1
                )
                print(f"✅ [ENDPOINT] Invite link created: {invite.invite_link}")

                # Send invite message to user
                await bot.send_message(
                    chat_id=user_id,
                    text=(
                        "✅ You've been granted access!\n"
                        "Here is your one-time invite link:\n"
                        f"{invite.invite_link}"
                    ),
                    disable_web_page_preview=True
                )
                print(f"✅ [ENDPOINT] Invite message sent to user {user_id}")

                return {
                    "success": True,
                    "invite_link": invite.invite_link
                }

            except TelegramError as te:
                # Telegram API error - Cloud Tasks will retry
                print(f"❌ [ENDPOINT] Telegram API error: {te}")
                print(f"🔄 [ENDPOINT] Cloud Tasks will retry after 60s")
                raise

            except Exception as e:
                # Other error - Cloud Tasks will retry
                print(f"❌ [ENDPOINT] Unexpected error sending invite: {e}")
                print(f"🔄 [ENDPOINT] Cloud Tasks will retry after 60s")
                raise

        # Execute async function in isolated event loop
        try:
            result = asyncio.run(send_invite_async())

            # ================================================================
            # IDEMPOTENCY: Mark invite as sent in database
            # ================================================================

            invite_link = result.get('invite_link')

            if db_manager:
                try:
                    conn = db_manager.get_connection()
                    if conn:
                        cur = conn.cursor()
                        cur.execute("""
                            UPDATE processed_payments
                            SET
                                telegram_invite_sent = TRUE,
                                telegram_invite_sent_at = CURRENT_TIMESTAMP,
                                telegram_invite_link = %s,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE payment_id = %s
                        """, (invite_link, payment_id))
                        conn.commit()
                        cur.close()
                        conn.close()

                        print(f"✅ [IDEMPOTENCY] Marked invite as sent for payment {payment_id}")
                        print(f"   Link stored: {invite_link}")
                    else:
                        print(f"⚠️ [IDEMPOTENCY] Could not get database connection")
                except Exception as e:
                    # Non-critical error - invite already sent to user
                    print(f"⚠️ [IDEMPOTENCY] Failed to mark invite as sent: {e}")
                    print(f"⚠️ [IDEMPOTENCY] User received invite, but DB update failed")
                    print(f"⚠️ [IDEMPOTENCY] Will retry DB update on next task execution")
            else:
                print(f"⚠️ [IDEMPOTENCY] Database manager not available - cannot mark invite as sent")

            print(f"🎉 [ENDPOINT] Telegram invite completed successfully")
            return jsonify({
                "status": "success",
                "message": "Telegram invite sent successfully",
                "user_id": user_id,
                "channel_id": closed_channel_id,
                "payment_id": payment_id
            }), 200

        except TelegramError as te:
            # Telegram API error - return 500 for Cloud Tasks retry
            abort(500, f"Telegram API error: {te}")

        except Exception as e:
            # Other error - return 500 for Cloud Tasks retry
            abort(500, f"Error sending invite: {e}")

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
        # Check if all required components are healthy
        all_healthy = all([token_manager, bot_token, db_manager])

        return jsonify({
            "status": "healthy" if all_healthy else "degraded",
            "service": "GCWebhook2-10-26 Telegram Invite Sender (with Payment Validation)",
            "timestamp": int(time.time()),
            "components": {
                "token_manager": "healthy" if token_manager else "unhealthy",
                "bot_token": "healthy" if bot_token else "unhealthy",
                "database_manager": "healthy" if db_manager else "unhealthy"
            }
        }), 200

    except Exception as e:
        print(f"❌ [HEALTH] Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "service": "GCWebhook2-10-26 Telegram Invite Sender (with Payment Validation)",
            "error": str(e)
        }), 503


# ============================================================================
# FLASK ENTRYPOINT
# ============================================================================

if __name__ == "__main__":
    print(f"🚀 [APP] Starting GCWebhook2-10-26 on port 8080")
    app.run(host="0.0.0.0", port=8080, debug=False)
