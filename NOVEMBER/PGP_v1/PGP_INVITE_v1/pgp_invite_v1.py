#!/usr/bin/env python
"""
PGP_INVITE_v1: Telegram Invite Sender Service
Receives encrypted tokens from PGP_ORCHESTRATOR_v1 via Cloud Tasks,
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
import os
import time
import asyncio
from flask import Flask, request, abort, jsonify
from telegram import Bot
from telegram.error import TelegramError

# Import service modules
from config_manager import ConfigManager
from token_manager import TokenManager
from database_manager import DatabaseManager

# Import security utilities (C-07 fix)
from PGP_COMMON.utils import (
    sanitize_error_for_user,
    create_error_response,
    IdempotencyManager,
    ValidationError,
    validate_telegram_user_id,
    validate_telegram_channel_id,
    validate_payment_id
)

from PGP_COMMON.logging import setup_logger
logger = setup_logger(__name__)
# Initialize logger

app = Flask(__name__)

# Initialize managers
logger.info(f"🚀 [APP] Initializing PGP_INVITE_v1 Telegram Invite Sender Service")
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
    logger.info(f"✅ [APP] Database manager initialized for payment validation")
except Exception as e:
    logger.error(f"❌ [APP] Failed to initialize database manager: {e}", exc_info=True)
    logger.warning(f"⚠️ [APP] Payment validation will fail without database connection")
    db_manager = None

# Initialize idempotency manager (prevents race conditions in invite sending)
idempotency_manager = None
if db_manager:
    try:
        idempotency_manager = IdempotencyManager(db_manager)
        logger.info(f"✅ [APP] IdempotencyManager initialized")
        logger.info(f"🔒 [APP] Atomic invite tracking enabled (prevents duplicates)")
    except Exception as e:
        logger.error(f"❌ [APP] Failed to initialize IdempotencyManager: {e}", exc_info=True)
        logger.warning(f"⚠️ [APP] Race condition protection disabled - proceed with caution!")
else:
    logger.warning(f"⚠️ [APP] Skipping IdempotencyManager initialization - db_manager not available")

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

# Store bot token at module level (Bot instance created per-request)
try:
    bot_token = config.get('telegram_bot_token')
    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN not available")
    logger.info(f"✅ [APP] Telegram bot token loaded (Bot instance will be created per-request)")
except Exception as e:
    logger.error(f"❌ [APP] Failed to load Telegram bot token: {e}", exc_info=True)
    bot_token = None


# ============================================================================
# MAIN ENDPOINT: POST / - Receives request from PGP_ORCHESTRATOR_v1 via Cloud Tasks
# ============================================================================

@app.route("/", methods=["POST"])
def send_telegram_invite():
    """
    Main endpoint for sending Telegram invites.

    Flow:
    1. Decrypt token from PGP_ORCHESTRATOR_v1
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
        logger.info(f"🎯 [ENDPOINT] Telegram invite request received (from PGP_ORCHESTRATOR_v1)")

        # Parse JSON payload
        try:
            request_data = request.get_json()
            if not request_data:
                abort(400, "Invalid JSON payload")
        except Exception as e:
            logger.error(f"❌ [ENDPOINT] JSON parsing error: {e}", exc_info=True)
            abort(400, "Malformed JSON payload")

        encrypted_token = request_data.get('token')
        payment_id = request_data.get('payment_id')

        if not encrypted_token:
            logger.error(f"❌ [ENDPOINT] Missing token")
            abort(400, "Missing token")

        if not payment_id:
            logger.error(f"❌ [ENDPOINT] Missing payment_id")
            abort(400, "Missing payment_id for idempotency tracking")

        logger.info(f"📋 [ENDPOINT] Payment ID: {payment_id}")

        # Decrypt token first to extract user_id and closed_channel_id for idempotency check
        if not token_manager:
            logger.error(f"❌ [ENDPOINT] Token manager not available")
            abort(500, "Service configuration error")

        try:
            user_id, closed_channel_id, wallet_address, payout_currency, payout_network, subscription_time_days, subscription_price = token_manager.decode_and_verify_token(encrypted_token)
            logger.info(f"✅ [ENDPOINT] Token decoded successfully")
            logger.info(f"👤 [ENDPOINT] User: {user_id}, Channel: {closed_channel_id}")
            logger.info(f"💰 [ENDPOINT] Price: ${subscription_price}, Duration: {subscription_time_days} days")
        except Exception as e:
            logger.error(f"❌ [ENDPOINT] Token validation error: {e}", exc_info=True)
            abort(400, f"Token error: {e}")

        # ============================================================================
        # INPUT VALIDATION: Validate token data AFTER decryption (C-03 fix)
        # ============================================================================
        try:
            # Validate payment_id
            payment_id = validate_payment_id(payment_id, field_name="payment_id")

            # Validate user_id from token
            user_id = validate_telegram_user_id(user_id, field_name="user_id")

            # Validate closed_channel_id from token
            closed_channel_id = validate_telegram_channel_id(closed_channel_id, field_name="closed_channel_id")

            logger.info(f"✅ [VALIDATED] Token data validation passed")
            logger.info(f"   Payment ID: {payment_id}")
            logger.info(f"   User ID: {user_id}")
            logger.info(f"   Channel ID: {closed_channel_id}")

        except ValidationError as e:
            logger.error(f"❌ [VALIDATED] Token data validation failed: {e}", exc_info=True)
            abort(400, f"Invalid token data: {e}")

        # ============================================================================
        # IDEMPOTENCY CHECK: Atomic check using IdempotencyManager
        # ============================================================================
        logger.debug("")
        logger.debug(f"🔍 [IDEMPOTENCY] Checking if invite already sent for payment {payment_id}...")

        if not idempotency_manager:
            logger.warning(f"⚠️ [IDEMPOTENCY] IdempotencyManager not available - skipping idempotency check")
            logger.warning(f"⚠️ [IDEMPOTENCY] Race condition protection disabled (fail-open mode)")
        else:
            try:
                # ✅ ATOMIC CHECK: Try to claim processing (INSERT...ON CONFLICT)
                can_process, existing_data = idempotency_manager.check_and_claim_processing(
                    payment_id=payment_id,
                    user_id=user_id,
                    channel_id=closed_channel_id,
                    service_column='telegram_invite_sent'
                )

                if not can_process:
                    # Another request already sent the invite
                    logger.info(f"✅ [IDEMPOTENCY] Invite already sent for payment {payment_id}")
                    logger.info(f"   Service: telegram_invite_sent = TRUE")
                    if existing_data:
                        logger.info(f"   Payment status: {existing_data.get('payment_status')}")
                        logger.info(f"   Orchestrator processed: {existing_data.get('pgp_orchestrator_processed')}")
                        logger.info(f"   Created at: {existing_data.get('created_at')}")
                    logger.info(f"🎉 [ENDPOINT] Returning success (invite already sent)")

                    return jsonify({
                        "status": "success",
                        "message": "Telegram invite already sent (idempotency check)",
                        "payment_id": payment_id,
                        "already_processed": True
                    }), 200

                # ✅ We won the race - safe to send invite
                logger.info(f"🆕 [IDEMPOTENCY] Claimed processing for payment {payment_id}")
                logger.info(f"🔒 [IDEMPOTENCY] Atomic lock acquired - safe to send invite")

            except ValueError as e:
                logger.error(f"❌ [IDEMPOTENCY] Validation error: {e}", exc_info=True)
                logger.warning(f"⚠️ [IDEMPOTENCY] Invalid payment data - proceeding with caution")
            except Exception as e:
                logger.error(f"❌ [IDEMPOTENCY] Error during atomic check: {e}", exc_info=True)
                logger.warning(f"⚠️ [IDEMPOTENCY] Proceeding with invite send (fail-open mode)")

        logger.debug("")

        # ============================================================================
        # PAYMENT VALIDATION - Verify payment completed before sending invite
        # ============================================================================
        if not db_manager:
            logger.error(f"❌ [ENDPOINT] Database manager not available - cannot validate payment")
            abort(500, "Payment validation service unavailable")

        logger.info(f"🔐 [ENDPOINT] Validating payment completion...")
        is_valid, error_message = db_manager.validate_payment_complete(
            user_id=user_id,
            closed_channel_id=closed_channel_id,
            expected_price=subscription_price
        )

        if not is_valid:
            if "IPN callback" in error_message or "pending" in error_message:
                # IPN not yet processed - return 503 for Cloud Tasks retry
                logger.info(f"⏳ [ENDPOINT] Payment validation pending - Cloud Tasks will retry")
                logger.info(f"🔄 [ENDPOINT] Retry reason: {error_message}")
                abort(503, error_message)
            else:
                # Payment invalid - return 400 (no retry)
                logger.error(f"❌ [ENDPOINT] Payment validation failed - will not retry")
                logger.warning(f"🚫 [ENDPOINT] Failure reason: {error_message}")
                abort(400, error_message)

        logger.info(f"✅ [ENDPOINT] Payment validation successful - proceeding with invitation")

        # Check bot token availability
        if not bot_token:
            logger.error(f"❌ [ENDPOINT] Telegram bot token not available")
            abort(500, "Telegram bot configuration error")

        # Fetch channel and subscription details for enhanced message
        channel_details = {'channel_title': 'Premium Channel', 'tier_number': 'Unknown'}
        if db_manager:
            try:
                channel_details = db_manager.get_channel_subscription_details(
                    closed_channel_id=closed_channel_id,
                    subscription_price=subscription_price,
                    subscription_time_days=subscription_time_days
                )
            except Exception as e:
                logger.warning(f"⚠️ [ENDPOINT] Could not fetch channel details: {e}")
                logger.warning(f"⚠️ [ENDPOINT] Using fallback values for message")

        channel_title = channel_details.get('channel_title', 'Premium Channel')
        tier_number = channel_details.get('tier_number', 'Unknown')

        # Define async function to handle telegram operations
        async def send_invite_async():
            """
            Async function to handle telegram bot operations.
            Creates fresh Bot instance with isolated httpx connection pool.
            """
            # Create fresh Bot instance for this request
            bot = Bot(bot_token)

            try:
                logger.info(f"📨 [ENDPOINT] Creating Telegram invite link for channel {closed_channel_id}")

                # Create one-time invite link (expires in 1 hour, 1 use only)
                invite = await bot.create_chat_invite_link(
                    chat_id=closed_channel_id,
                    expire_date=int(time.time()) + 3600,
                    member_limit=1
                )
                logger.info(f"✅ [ENDPOINT] Invite link created: {invite.invite_link}")

                # Send invite message to user with enhanced format
                await bot.send_message(
                    chat_id=user_id,
                    text=(
                        "🎉 Your ONE-TIME Invitation Link\n\n"
                        f"📺 Channel: {channel_title}\n"
                        f"🔗 {invite.invite_link}\n\n"
                        f"📋 Subscription Details:\n"
                        f"├ 🎯 Tier: {tier_number}\n"
                        f"├ 💰 Price: ${subscription_price} USD\n"
                        f"└ ⏳ Duration: {subscription_time_days} days"
                    ),
                    disable_web_page_preview=True
                )
                logger.info(f"✅ [ENDPOINT] Enhanced invite message sent to user {user_id}")
                logger.info(f"📺 [ENDPOINT] Message details: {channel_title}, Tier {tier_number}, ${subscription_price}, {subscription_time_days} days")

                return {
                    "success": True,
                    "invite_link": invite.invite_link
                }

            except TelegramError as te:
                # Telegram API error - Cloud Tasks will retry
                logger.error(f"❌ [ENDPOINT] Telegram API error: {te}", exc_info=True)
                logger.info(f"🔄 [ENDPOINT] Cloud Tasks will retry after 60s")
                raise

            except Exception as e:
                # Other error - Cloud Tasks will retry
                logger.error(f"❌ [ENDPOINT] Unexpected error sending invite: {e}", exc_info=True)
                logger.info(f"🔄 [ENDPOINT] Cloud Tasks will retry after 60s")
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

                        logger.info(f"✅ [IDEMPOTENCY] Marked invite as sent for payment {payment_id}")
                        logger.info(f"   Link stored: {invite_link}")
                    else:
                        logger.warning(f"⚠️ [IDEMPOTENCY] Could not get database connection")
                except Exception as e:
                    # Non-critical error - invite already sent to user
                    logger.warning(f"⚠️ [IDEMPOTENCY] Failed to mark invite as sent: {e}")
                    logger.warning(f"⚠️ [IDEMPOTENCY] User received invite, but DB update failed")
                    logger.warning(f"⚠️ [IDEMPOTENCY] Will retry DB update on next task execution")
            else:
                logger.warning(f"⚠️ [IDEMPOTENCY] Database manager not available - cannot mark invite as sent")

            logger.info(f"🎉 [ENDPOINT] Telegram invite completed successfully")
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
        logger.error(f"❌ [ENDPOINT] Unexpected error: {e}", exc_info=True)
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
            "service": "PGP_INVITE_v1 Telegram Invite Sender (with Payment Validation)",
            "timestamp": int(time.time()),
            "components": {
                "token_manager": "healthy" if token_manager else "unhealthy",
                "bot_token": "healthy" if bot_token else "unhealthy",
                "database_manager": "healthy" if db_manager else "unhealthy"
            }
        }), 200

    except Exception as e:
        logger.error(f"❌ [HEALTH] Health check failed: {e}", exc_info=True)
        return jsonify({
            "status": "unhealthy",
            "service": "PGP_INVITE_v1 Telegram Invite Sender (with Payment Validation)",
            "error": str(e)
        }), 503


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
        f"❌ [ERROR] Unhandled exception in PGP_INVITE_v1",
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
# FLASK ENTRYPOINT
# ============================================================================

if __name__ == "__main__":
    logger.info(f"🚀 [APP] Starting PGP_INVITE_v1 on port 8080")
    app.run(host="0.0.0.0", port=8080, debug=False)
