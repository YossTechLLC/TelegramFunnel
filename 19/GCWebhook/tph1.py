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
from google.cloud import secretmanager

# --- Utility to decode and verify signed token ---
def decode_and_verify_token(token: str, signing_key: str) -> Tuple[int, int, str, str]:
    """Returns (user_id, closed_channel_id, wallet_address, payout_currency) if valid, else raises Exception.
    
    Decodes optimized token format:
    - 6 bytes user_id (48-bit)
    - 6 bytes closed_channel_id (48-bit) 
    - 2 bytes timestamp_minutes
    - 1 byte wallet_length + wallet_address
    - 1 byte currency_length + payout_currency
    - 16 bytes truncated HMAC signature
    """
    # Pad the token if base64 length is not a multiple of 4
    padding = '=' * (-len(token) % 4)
    try:
        raw = base64.urlsafe_b64decode(token + padding)
    except Exception:
        raise ValueError("Invalid token: cannot decode base64")
    
    # Minimum size check: 6+6+2+1+1+16 = 32 bytes
    if len(raw) < 32:
        raise ValueError(f"Invalid token: too small (got {len(raw)}, minimum 32)")
    
    # Parse fixed part: 6 bytes user_id, 6 bytes channel_id, 2 bytes timestamp_minutes
    user_id = int.from_bytes(raw[0:6], 'big')
    closed_channel_id = int.from_bytes(raw[6:12], 'big')
    timestamp_minutes = struct.unpack(">H", raw[12:14])[0]
    
    # Parse variable part: wallet address and currency
    offset = 14
    
    # Read wallet address length and data
    if offset + 1 > len(raw):
        raise ValueError("Invalid token: missing wallet length field")
    wallet_len = struct.unpack(">B", raw[offset:offset+1])[0]
    offset += 1
    
    if offset + wallet_len > len(raw):
        raise ValueError("Invalid token: incomplete wallet address")
    wallet_address = raw[offset:offset+wallet_len].decode('utf-8')
    offset += wallet_len
    
    # Read currency length and data
    if offset + 1 > len(raw):
        raise ValueError("Invalid token: missing currency length field")
    currency_len = struct.unpack(">B", raw[offset:offset+1])[0]
    offset += 1
    
    if offset + currency_len > len(raw):
        raise ValueError("Invalid token: incomplete currency")
    payout_currency = raw[offset:offset+currency_len].decode('utf-8')
    offset += currency_len
    
    # The remaining bytes should be the 16-byte truncated signature
    if len(raw) - offset != 16:
        raise ValueError(f"Invalid token: wrong signature size (got {len(raw) - offset}, expected 16)")
    
    data = raw[:offset]  # All data except signature
    sig = raw[offset:]   # The signature
    
    # Debug logs for troubleshooting
    print(f"[DEBUG] raw: {raw.hex()}")
    print(f"[DEBUG] data: {data.hex()}")
    print(f"[DEBUG] sig: {sig.hex()}")
    print(f"[DEBUG] wallet_address: '{wallet_address}', payout_currency: '{payout_currency}'")
    
    # Verify truncated signature
    expected_full_sig = hmac.new(signing_key.encode(), data, hashlib.sha256).digest()
    expected_sig = expected_full_sig[:16]  # Compare only first 16 bytes
    if not hmac.compare_digest(sig, expected_sig):
        raise ValueError("Signature mismatch")
    
    # If IDs are "negative" in Telegram, fix here (48-bit range):
    if user_id > 2**47 - 1:
        user_id -= 2**48
    if closed_channel_id > 2**47 - 1:
        closed_channel_id -= 2**48
    
    # Reconstruct full timestamp from minutes
    current_time = int(time.time())
    current_minutes = current_time // 60
    
    # Handle timestamp wrap-around (65536 minute cycle ≈ 45 days)
    minutes_in_current_cycle = current_minutes % 65536
    base_minutes = current_minutes - minutes_in_current_cycle
    
    if timestamp_minutes > minutes_in_current_cycle:
        # Timestamp is likely from previous cycle
        timestamp = (base_minutes - 65536 + timestamp_minutes) * 60
    else:
        # Timestamp is from current cycle  
        timestamp = (base_minutes + timestamp_minutes) * 60
    
    # Additional validation: ensure timestamp is reasonable (within ~45 days)
    time_diff = abs(current_time - timestamp)
    if time_diff > 45 * 24 * 3600:  # 45 days in seconds
        raise ValueError(f"Timestamp too far from current time: {time_diff} seconds difference")
    
    print(f"[DEBUG] Decoded user_id: {user_id}, closed_channel_id: {closed_channel_id}, timestamp: {timestamp} (from minutes: {timestamp_minutes})")
    print(f"[DEBUG] Wallet: '{wallet_address}', Currency: '{payout_currency}'")
    
    # Check for expiration (e.g., 2hr window)
    now = int(time.time())
    if not (now - 7200 <= timestamp <= now + 300):
        raise ValueError("Token expired or not yet valid")
    
    return user_id, closed_channel_id, wallet_address, payout_currency

def fetch_telegram_bot_token() -> str:
    """Fetch Telegram bot token from Google Secret Manager."""
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_name = os.getenv("TELEGRAM_BOT_SECRET_NAME")
        if not secret_name:
            raise ValueError("Environment variable TELEGRAM_BOT_SECRET_NAME is not set.")
        secret_path = f"{secret_name}"
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"Error fetching Telegram bot token: {e}")
        return None

def fetch_success_url_signing_key() -> str:
    """Fetch success URL signing key from Google Secret Manager."""
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_name = os.getenv("SUCCESS_URL_SIGNING_KEY")
        if not secret_name:
            raise ValueError("Environment variable SUCCESS_URL_SIGNING_KEY is not set.")
        secret_path = f"{secret_name}"
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"Error fetching success URL signing key: {e}")
        return None

# --- Flask app and webhook handler ---
app = Flask(__name__)

@app.route("/", methods=["GET"])
def send_invite():
    # Extract token from URL
    token = request.args.get("token")
    if not token:
        abort(400, "Missing token")
    
    # Fetch secrets from Google Secret Manager
    bot_token = fetch_telegram_bot_token()
    signing_key = fetch_success_url_signing_key()
    
    if not bot_token or not signing_key:
        abort(500, "Missing credentials - unable to fetch from Secret Manager")

    user_id = None
    closed_channel_id = None
    wallet_address = None
    payout_currency = None

    # Validate and decode token
    try:
        user_id, closed_channel_id, wallet_address, payout_currency = decode_and_verify_token(token, signing_key)
        print(f"[INFO] Successfully decoded token - User: {user_id}, Channel: {closed_channel_id}")
        print(f"[INFO] Wallet: '{wallet_address}', Currency: '{payout_currency}'")
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
