import os
import time
import struct
import base64
import hmac
import hashlib
import asyncio
from typing import Tuple, Dict, Any
from flask import Flask, request, abort, jsonify
from telegram import Bot
from google.cloud import secretmanager

# --- Secure Secret Fetchers (GCP) ---
def fetch_telegram_token():
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_name = os.getenv("TELEGRAM_BOT_SECRET_NAME")
        if not secret_name:
            raise ValueError("Environment variable TELEGRAM_BOT_SECRET_NAME is not set.")
        response = client.access_secret_version(request={"name": secret_name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"Error fetching the Telegram bot TOKEN: {e}")
        return None

def fetch_success_url_signing_key():
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_name = os.getenv("SUCCESS_URL_SIGNING_KEY")
        if not secret_name:
            raise ValueError("Environment variable SUCCESS_URL_SIGNING_KEY is not set.")
        response = client.access_secret_version(request={"name": secret_name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"Error fetching the SUCCESS_URL_SIGNING_KEY: {e}")
        return None

def decode_and_verify_token(token: str, signing_key: str) -> Tuple[int, int]:
    """Returns (user_id, closed_channel_id) if valid, else raises Exception."""
    # Pad the token if base64 length is not a multiple of 4
    padding = '=' * (-len(token) % 4)
    try:
        raw = base64.urlsafe_b64decode(token + padding)
    except Exception:
        raise ValueError("Invalid token: cannot decode base64")
    if len(raw) != 8+8+4+32:
        raise ValueError("Invalid token: wrong size")
    data = raw[:8+8+4]
    sig  = raw[8+8+4:]
    # Verify signature
    expected_sig = hmac.new(signing_key.encode(), data, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected_sig):
        raise ValueError("Signature mismatch")
    tele_open_id, closed_channel_id, timestamp = struct.unpack(">QQI", data)
    # Optionally check for expiration (e.g., 2hr window)
    now = int(time.time())
    if not (now - 7200 <= timestamp <= now + 300):
        raise ValueError("Token expired or not yet valid")
    return tele_open_id, closed_channel_id

# --- Flask app and webhook handler ---
app = Flask(__name__)

@app.route("/", methods=["GET"])
def send_invite():
    # Extract token from URL
    token = request.args.get("token")
    if not token:
        abort(400, "Missing token")
    # Fetch secrets
    bot_token = "8139434770:AAGQNpGzbpeY1FgENcuJ_rctuXOAmRuPVJU"
    signing_key = "sSllV0e7c6jJvBlG2l03Wub9NRIDQ4xW9p+Njke8q+sI="
    if not bot_token or not signing_key:
        abort(500, "Missing credentials")
    # Validate and decode token
    try:
        user_id, closed_channel_id = decode_and_verify_token(token, signing_key)
    except Exception as e:
        abort(400, f"Token error: {e}")

    # Send invite via Telegram
    try:
        bot = Bot(bot_token)
        async def run_invite():
            invite = await bot.create_chat_invite_link(
                chat_id=closed_channel_id,
                expire_date=int(time.time()) + 3600,
                member_limit=1
            )
            await bot.send_message(
                chat_id=user_id,
                text=(
                    "✅ You’ve been granted access!\n"
                    "Here is your one-time invite link:\n"
                    f"{invite.invite_link}"
                ),
                disable_web_page_preview=True
            )
        asyncio.run(run_invite())
    except Exception as e:
        app.logger.error("telegram error: %s", e, exc_info=True)
        abort(500, "telegram error")

    return jsonify(status="ok"), 200

# --- Flask entrypoint for deployment ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
