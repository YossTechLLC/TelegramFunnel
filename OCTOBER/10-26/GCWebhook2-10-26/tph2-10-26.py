#!/usr/bin/env python
"""
GCWebhook2-10-26: Telegram Invite Sender Service
Receives encrypted tokens from GCWebhook1 via Cloud Tasks,
sends Telegram one-time invitation links to users.
Implements infinite retry via Cloud Tasks (60s fixed backoff, 24h max duration).

IMPORTANT - Async Route Architecture:
The main endpoint is defined as async to properly handle the python-telegram-bot's
async API calls. This prevents connection pool exhaustion that occurs when using
asyncio.run() within a synchronous Flask route.

Why async route instead of asyncio.run():
- Flask 3.0+ supports native async routes
- Each asyncio.run() creates a NEW event loop
- python-telegram-bot uses httpx with connection pooling PER event loop
- Creating multiple event loops causes connection pool exhaustion
- Async route reuses the same event loop and connection pool across requests
- Result: Proper connection management and no pool timeout errors
"""
import time
from flask import Flask, request, abort, jsonify
from telegram import Bot
from telegram.error import TelegramError

# Import service modules
from config_manager import ConfigManager
from token_manager import TokenManager

app = Flask(__name__)

# Initialize managers
print(f"🚀 [APP] Initializing GCWebhook2-10-26 Telegram Invite Sender Service")
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

# Initialize Telegram bot
try:
    bot_token = config.get('telegram_bot_token')
    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN not available")
    telegram_bot = Bot(bot_token)
    print(f"✅ [APP] Telegram bot initialized")
except Exception as e:
    print(f"❌ [APP] Failed to initialize Telegram bot: {e}")
    telegram_bot = None


# ============================================================================
# MAIN ENDPOINT: POST / - Receives request from GCWebhook1 via Cloud Tasks
# ============================================================================

@app.route("/", methods=["POST"])
async def send_telegram_invite():
    """
    Main endpoint for sending Telegram invites.

    Flow:
    1. Decrypt token from GCWebhook1
    2. Create Telegram invite link
    3. Send invite message to user
    4. Return 200 (Cloud Tasks marks success)
    5. If error: Return 500 (Cloud Tasks retries after 60s)

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
        if not encrypted_token:
            print(f"❌ [ENDPOINT] Missing token")
            abort(400, "Missing token")

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

        # Send Telegram invite
        if not telegram_bot:
            print(f"❌ [ENDPOINT] Telegram bot not available")
            abort(500, "Telegram bot unavailable")

        try:
            print(f"📨 [ENDPOINT] Creating Telegram invite link for channel {closed_channel_id}")

            # Create one-time invite link (expires in 1 hour, 1 use only)
            invite = await telegram_bot.create_chat_invite_link(
                chat_id=closed_channel_id,
                expire_date=int(time.time()) + 3600,
                member_limit=1
            )
            print(f"✅ [ENDPOINT] Invite link created: {invite.invite_link}")

            # Send invite message to user
            await telegram_bot.send_message(
                chat_id=user_id,
                text=(
                    "✅ You've been granted access!\n"
                    "Here is your one-time invite link:\n"
                    f"{invite.invite_link}"
                ),
                disable_web_page_preview=True
            )
            print(f"✅ [ENDPOINT] Invite message sent to user {user_id}")

            print(f"🎉 [ENDPOINT] Telegram invite completed successfully")
            return jsonify({
                "status": "success",
                "message": "Telegram invite sent successfully",
                "user_id": user_id,
                "channel_id": closed_channel_id
            }), 200

        except TelegramError as te:
            # Telegram API error - Cloud Tasks will retry
            print(f"❌ [ENDPOINT] Telegram API error: {te}")
            print(f"🔄 [ENDPOINT] Cloud Tasks will retry after 60s")
            abort(500, f"Telegram API error: {te}")

        except Exception as e:
            # Other error - Cloud Tasks will retry
            print(f"❌ [ENDPOINT] Unexpected error sending invite: {e}")
            print(f"🔄 [ENDPOINT] Cloud Tasks will retry after 60s")
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
        return jsonify({
            "status": "healthy",
            "service": "GCWebhook2-10-26 Telegram Invite Sender",
            "timestamp": int(time.time()),
            "components": {
                "token_manager": "healthy" if token_manager else "unhealthy",
                "telegram_bot": "healthy" if telegram_bot else "unhealthy"
            }
        }), 200

    except Exception as e:
        print(f"❌ [HEALTH] Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "service": "GCWebhook2-10-26 Telegram Invite Sender",
            "error": str(e)
        }), 503


# ============================================================================
# FLASK ENTRYPOINT
# ============================================================================

if __name__ == "__main__":
    print(f"🚀 [APP] Starting GCWebhook2-10-26 on port 8080")
    app.run(host="0.0.0.0", port=8080, debug=False)
