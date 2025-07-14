import os
import time
import struct
import base64
import hmac
import hashlib
import asyncio
from typing import Tuple
from flask import Flask, request, abort, jsonify
from telegram import Bot
# from google.cloud import secretmanager  # not used since secrets are hard-coded

# --- Utility to decode and verify signed token ---
def decode_and_verify_token(token: str, signing_key: str) -> Tuple[int, int]:
    """Returns (user_id, closed_channel_id) if valid, else raises Exception."""
    # Pad the token if base64 length is not a multiple of 4
    padding = '=' * (-len(token) % 4)
    try:
        raw = base64.urlsafe_b64decode(token + padding)
    except Exception:
        raise ValueError("Invalid token: cannot decode base64")
    if len(raw) != 8+8+4+32:
        raise ValueError(f"Invalid token: wrong size (got {len(raw)}, expected {8+8+4+32})")
    data = raw[:20]
    sig  = raw[20:]
    # Debug logs for troubleshooting
    print(f"[DEBUG] raw: {raw.hex()}")
    print(f"[DEBUG] data: {data.hex()}")
    print(f"[DEBUG] sig: {sig.hex()}")
    expected_sig = hmac.new(signing_key.encode(), data, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected_sig):
        raise ValueError("Signature mismatch")
    tele_open_id, closed_channel_id, timestamp = struct.unpack(">QQI", data)
    # If closed_channel_id is "negative" in Telegram, fix here:
    if tele_open_id > 2**63 - 1:
        tele_open_id -= 2**64
    if closed_channel_id > 2**63 - 1:
        closed_channel_id -= 2**64
    print(f"[DEBUG] Decoded tele_open_id: {tele_open_id}, closed_channel_id: {closed_channel_id}, timestamp: {timestamp}")
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
    # Fetch hard-coded secrets (substitute your own values)
    bot_token = "8139434770:AAGQNpGzbpeY1FgENcuJ_rctuXOAmRuPVJU"
    signing_key = "sSllV0e7c6jJvBlG2l03Wub9NRIDQ4xW9p+Njke8q+sI="
    if not bot_token or not signing_key:
        abort(500, "Missing credentials")

    user_id = None
    closed_channel_id = None

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
        import traceback
        error_msg = (
            f"telegram error: {e}\n"
            f"user_id: {user_id}, closed_channel_id: {closed_channel_id}\n"
            f"{traceback.format_exc()}"
        )
        print(error_msg)
        app.logger.error(error_msg)
        abort(
            500,
            f"telegram error: {e}\nuser_id: {user_id}, closed_channel_id: {closed_channel_id}"
        )

    return jsonify(status="ok"), 200

# --- Flask entrypoint for deployment ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
