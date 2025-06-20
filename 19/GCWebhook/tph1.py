import os
import time
import struct
import base64
import hmac
import hashlib
import asyncio
import psycopg2
from typing import Tuple, Optional
from flask import Flask, request, abort, jsonify
from telegram import Bot
from google.cloud import secretmanager

# --- Utility to decode and verify signed token ---
def decode_and_verify_token(token: str, signing_key: str) -> Tuple[int, int, str, str, int]:
    """Returns (user_id, closed_channel_id, wallet_address, payout_currency, subscription_time_days) if valid, else raises Exception.
    
    Decodes optimized token format:
    - 6 bytes user_id (48-bit)
    - 6 bytes closed_channel_id (48-bit) 
    - 2 bytes timestamp_minutes
    - 2 bytes subscription_time_days
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
    
    # Minimum size check: 6+6+2+2+1+1+16 = 34 bytes
    if len(raw) < 34:
        raise ValueError(f"Invalid token: too small (got {len(raw)}, minimum 34)")
    
    # Parse fixed part: 6 bytes user_id, 6 bytes channel_id, 2 bytes timestamp_minutes, 2 bytes subscription_time
    user_id = int.from_bytes(raw[0:6], 'big')
    closed_channel_id = int.from_bytes(raw[6:12], 'big')
    timestamp_minutes = struct.unpack(">H", raw[12:14])[0]
    subscription_time_days = struct.unpack(">H", raw[14:16])[0]
    
    # Parse variable part: wallet address and currency
    offset = 16
    
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
    print(f"[DEBUG] wallet_address: '{wallet_address}', payout_currency: '{payout_currency}', subscription_time_days: {subscription_time_days}")
    
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
    print(f"[DEBUG] Wallet: '{wallet_address}', Currency: '{payout_currency}', Subscription: {subscription_time_days} days")
    
    # Check for expiration (e.g., 2hr window)
    now = int(time.time())
    if not (now - 7200 <= timestamp <= now + 300):
        raise ValueError("Token expired or not yet valid")
    
    return user_id, closed_channel_id, wallet_address, payout_currency, subscription_time_days

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

def fetch_database_host() -> str:
    """Fetch database host from Google Secret Manager."""
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_name = os.getenv("DATABASE_HOST_SECRET")
        if not secret_name:
            raise ValueError("Environment variable DATABASE_HOST_SECRET is not set.")
        secret_path = f"{secret_name}"
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"Error fetching DATABASE_HOST_SECRET: {e}")
        return "34.58.246.248"  # Fallback for migration period

def fetch_database_name() -> str:
    """Fetch database name from Google Secret Manager."""
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_name = os.getenv("DATABASE_NAME_SECRET")
        if not secret_name:
            raise ValueError("Environment variable DATABASE_NAME_SECRET is not set.")
        secret_path = f"{secret_name}"
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"Error fetching DATABASE_NAME_SECRET: {e}")
        return "client_table"  # Fallback for migration period

def fetch_database_user() -> str:
    """Fetch database user from Google Secret Manager."""
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_name = os.getenv("DATABASE_USER_SECRET")
        if not secret_name:
            raise ValueError("Environment variable DATABASE_USER_SECRET is not set.")
        secret_path = f"{secret_name}"
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"Error fetching DATABASE_USER_SECRET: {e}")
        return "postgres"  # Fallback for migration period

def fetch_database_password() -> str:
    """Fetch database password from Google Secret Manager."""
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_name = os.getenv("DATABASE_PASSWORD_SECRET")
        if not secret_name:
            raise ValueError("Environment variable DATABASE_PASSWORD_SECRET is not set.")
        secret_path = f"{secret_name}"
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"Error fetching DATABASE_PASSWORD_SECRET: {e}")
        return None  # No fallback for password - this should fail safely

def get_database_connection():
    """Create and return a database connection."""
    try:
        return psycopg2.connect(
            dbname=fetch_database_name(),
            user=fetch_database_user(),
            password=fetch_database_password(),
            host=fetch_database_host(),
            port=5432
        )
    except Exception as e:
        print(f"Error creating database connection: {e}")
        return None

def record_private_channel_user(user_id: int, private_channel_id: int, sub_time: int, is_active: bool = True) -> bool:
    """
    Record or update a user's subscription in the private_channel_users table.
    
    Args:
        user_id: The user's Telegram ID
        private_channel_id: The private channel ID (closed channel ID)
        sub_time: Subscription time in days
        is_active: Whether the subscription is active (default: True)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        conn = get_database_connection()
        if not conn:
            print("❌ Could not establish database connection")
            return False
        
        with conn, conn.cursor() as cur:
            # Use INSERT ... ON CONFLICT to handle both insert and update cases
            cur.execute("""
                INSERT INTO private_channel_users (private_channel_id, user_id, sub_time, is_active)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (private_channel_id, user_id) 
                DO UPDATE SET 
                    sub_time = EXCLUDED.sub_time,
                    is_active = EXCLUDED.is_active
            """, (private_channel_id, user_id, sub_time, is_active))
            
            print(f"✅ Successfully recorded user {user_id} for channel {private_channel_id} with {sub_time} days subscription")
            return True
            
    except Exception as e:
        print(f"❌ Error recording private channel user: {e}")
        return False

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
    subscription_time_days = None

    # Validate and decode token
    try:
        user_id, closed_channel_id, wallet_address, payout_currency, subscription_time_days = decode_and_verify_token(token, signing_key)
        print(f"[INFO] Successfully decoded token - User: {user_id}, Channel: {closed_channel_id}")
        print(f"[INFO] Wallet: '{wallet_address}', Currency: '{payout_currency}', Subscription: {subscription_time_days} days")
    except Exception as e:
        abort(400, f"Token error: {e}")

    # Record user subscription in private_channel_users table
    try:
        success = record_private_channel_user(
            user_id=user_id,
            private_channel_id=closed_channel_id,
            sub_time=subscription_time_days,
            is_active=True
        )
        if success:
            print(f"[INFO] ✅ Database: Recorded user {user_id} subscription for channel {closed_channel_id}")
        else:
            print(f"[WARNING] ❌ Database: Failed to record user {user_id} subscription - continuing with invite")
    except Exception as e:
        # Log error but don't fail the webhook - user should still get their invite
        print(f"[ERROR] ❌ Database error (non-fatal): {e}")

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
