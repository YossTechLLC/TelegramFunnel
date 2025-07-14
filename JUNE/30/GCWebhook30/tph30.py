import os
import time
import struct
import base64
import hmac
import hashlib
import asyncio
import requests
import re
import sys
from datetime import datetime
from typing import Tuple, Optional
from flask import Flask, request, abort, jsonify
from telegram import Bot
from google.cloud import secretmanager

# Import ChangeNOW swap functionality
try:
    from swap_processor import SwapProcessor
    CHANGENOW_AVAILABLE = True
    print("✅ [INFO] ChangeNOW swap processor imported successfully")
except ImportError as e:
    print(f"❌ [ERROR] ChangeNOW swap processor import failed: {e}")
    CHANGENOW_AVAILABLE = False
    SwapProcessor = None

# Import Cloud SQL Connector for database functionality
try:
    from google.cloud.sql.connector import Connector
    CLOUD_SQL_AVAILABLE = True
    print("✅ [INFO] Cloud SQL Connector imported successfully")
except ImportError as e:
    print(f"❌ [ERROR] Cloud SQL Connector import failed: {e}")
    CLOUD_SQL_AVAILABLE = False
    Connector = None


def get_current_timestamp() -> str:
    """
    Get current time in PostgreSQL time format.
    
    Returns:
        String representation of current time (e.g., '22:55:30')
    """
    now = datetime.now()
    return now.strftime('%H:%M:%S')

def get_current_datestamp() -> str:
    """
    Get current date in PostgreSQL date format.
    
    Returns:
        String representation of current date (e.g., '2025-06-20')
    """
    now = datetime.now()
    return now.strftime('%Y-%m-%d')

def calculate_expiration_time(sub_time_minutes: int) -> tuple[str, str]:
    """
    Calculate expiration time and date based on subscription time in minutes.
    
    Args:
        sub_time_minutes: Subscription duration in minutes (for testing - will be days in production)
        
    Returns:
        Tuple of (expire_time, expire_date) in PostgreSQL format
        - expire_time: HH:MM:SS format
        - expire_date: YYYY-MM-DD format
    """
    from datetime import timedelta
    
    # Get current datetime
    now = datetime.now()
    
    # Add subscription minutes to current time
    expiration_datetime = now + timedelta(minutes=sub_time_minutes)
    
    # Format for PostgreSQL
    expire_time = expiration_datetime.strftime('%H:%M:%S')
    expire_date = expiration_datetime.strftime('%Y-%m-%d')
    
    print(f"🕒 [DEBUG] Expiration calculation: {sub_time_minutes} minutes from {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📅 [DEBUG] Results: expire_time={expire_time}, expire_date={expire_date}")
    
    return expire_time, expire_date

# --- Utility to decode and verify signed token ---
def decode_and_verify_token(token: str, signing_key: str) -> Tuple[int, int, str, str, int, str]:
    """Returns (user_id, closed_channel_id, wallet_address, payout_currency, subscription_time_days, subscription_price) if valid, else raises Exception.
    
    Decodes optimized token format:
    - 6 bytes user_id (48-bit)
    - 6 bytes closed_channel_id (48-bit) 
    - 2 bytes timestamp_minutes
    - 2 bytes subscription_time_days
    - 1 byte price_length + subscription_price
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
    
    # Minimum size check: 6+6+2+2+1+1+1+1+16 = 36 bytes (added price field)
    if len(raw) < 36:
        raise ValueError(f"Invalid token: too small (got {len(raw)}, minimum 36)")
    
    # Parse fixed part: 6 bytes user_id, 6 bytes channel_id, 2 bytes timestamp_minutes, 2 bytes subscription_time
    user_id = int.from_bytes(raw[0:6], 'big')
    closed_channel_id = int.from_bytes(raw[6:12], 'big')
    timestamp_minutes = struct.unpack(">H", raw[12:14])[0]
    subscription_time_days = struct.unpack(">H", raw[14:16])[0]
    
    # Parse variable part: subscription price, wallet address and currency
    offset = 16
    
    # Read subscription price length and data
    if offset + 1 > len(raw):
        raise ValueError("Invalid token: missing price length field")
    price_len = struct.unpack(">B", raw[offset:offset+1])[0]
    offset += 1
    
    if offset + price_len > len(raw):
        raise ValueError("Invalid token: incomplete subscription price")
    subscription_price = raw[offset:offset+price_len].decode('utf-8')
    offset += price_len
    
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
    print(f"🔍 [DEBUG] raw: {raw.hex()}")
    print(f"📦 [DEBUG] data: {data.hex()}")
    print(f"🔐 [DEBUG] sig: {sig.hex()}")
    print(f"💰 [DEBUG] wallet_address: '{wallet_address}', payout_currency: '{payout_currency}', subscription_time_days: {subscription_time_days}")
    
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
    
    print(f"🔓 [DEBUG] Decoded user_id: {user_id}, closed_channel_id: {closed_channel_id}, timestamp: {timestamp} (from minutes: {timestamp_minutes})")
    print(f"🏦 [DEBUG] Wallet: '{wallet_address}', Currency: '{payout_currency}', Subscription: {subscription_time_days} days, Price: ${subscription_price}")
    
    # Check for expiration (e.g., 2hr window)
    now = int(time.time())
    if not (now - 7200 <= timestamp <= now + 300):
        raise ValueError("Token expired or not yet valid")
    
    return user_id, closed_channel_id, wallet_address, payout_currency, subscription_time_days, subscription_price

# Simplified secret/environment variable functions
def get_env_secret(env_var_name: str, fallback: str = None) -> str:
    """Get value from environment variable with optional fallback."""
    value = os.getenv(env_var_name)
    if not value:
        if fallback:
            return fallback
        raise ValueError(f"Environment variable {env_var_name} is not set")
    return value

def fetch_telegram_bot_token() -> str:
    """Get Telegram bot token from Secret Manager."""
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_path = os.getenv("TELEGRAM_BOT_SECRET_NAME")
        if not secret_path:
            raise ValueError("Environment variable TELEGRAM_BOT_SECRET_NAME is not set")
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"❌ Error fetching Telegram bot token: {e}")
        return None

def fetch_success_url_signing_key() -> str:
    """Get success URL signing key from Secret Manager."""
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_path = os.getenv("SUCCESS_URL_SIGNING_KEY")
        if not secret_path:
            raise ValueError("Environment variable SUCCESS_URL_SIGNING_KEY is not set")
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"❌ Error fetching signing key: {e}")
        return None

def fetch_database_name() -> str:
    """Get database name from Secret Manager."""
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_path = os.getenv("DATABASE_NAME_SECRET")
        if not secret_path:
            raise ValueError("Environment variable DATABASE_NAME_SECRET is not set.")
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"❌ Error fetching database name: {e}")
        raise

def fetch_database_user() -> str:
    """Get database user from Secret Manager."""
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_path = os.getenv("DATABASE_USER_SECRET")
        if not secret_path:
            raise ValueError("Environment variable DATABASE_USER_SECRET is not set.")
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"❌ Error fetching database user: {e}")
        raise

def fetch_database_password() -> str:
    """Get database password from Secret Manager."""
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_path = os.getenv("DATABASE_PASSWORD_SECRET")
        if not secret_path:
            return None
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"❌ Error fetching database password: {e}")
        return None

def fetch_cloud_sql_connection_name() -> str:
    """Get Cloud SQL connection name from environment (direct value)."""
    try:
        connection_name = os.getenv("CLOUD_SQL_CONNECTION_NAME")
        if not connection_name:
            return None
        return connection_name
    except Exception as e:
        print(f"❌ Error fetching Cloud SQL connection name: {e}")
        return None

def get_database_connection():
    """Create and return a database connection using Cloud SQL Connector."""
    if not CLOUD_SQL_AVAILABLE:
        print("❌ [ERROR] Cloud SQL Connector not available")
        return None
    
    try:
        # Get database credentials
        dbname = fetch_database_name()
        user = fetch_database_user()
        password = fetch_database_password()
        connection_name = fetch_cloud_sql_connection_name()
        
        if not password or not connection_name:
            print("❌ [ERROR] Missing database credentials")
            return None
        
        # Create connection
        connector = Connector()
        connection = connector.connect(
            connection_name,
            "pg8000",
            user=user,
            password=password,
            db=dbname
        )
        print("🔗 [DEBUG] ✅ Cloud SQL Connector connection successful!")
        return connection
        
    except Exception as e:
        print(f"❌ [ERROR] Database connection failed: {e}")
        return None


def record_private_channel_user(user_id: int, private_channel_id: int, sub_time: int, sub_price: str,
                                expire_time: str = "", expire_date: str = "", is_active: bool = True) -> bool:
    """
    Record a user's subscription in the private_channel_users_database table.
    
    Args:
        user_id: The user's Telegram ID
        private_channel_id: The private channel ID (closed channel ID)
        sub_time: Subscription time in minutes (for testing - will be days in production)
        sub_price: Subscription price as string (e.g., "15.00")
        expire_time: Expiration time in HH:MM:SS format
        expire_date: Expiration date in YYYY-MM-DD format
        is_active: Whether the subscription is active (default: True)
        
    Returns:
        True if successful, False otherwise
    """
    # Get current timestamp and datestamp for PostgreSQL
    current_timestamp = get_current_timestamp()
    current_datestamp = get_current_datestamp()
    print(f"📝 [DEBUG] Starting database record for user {user_id}, channel {private_channel_id}, sub_time {sub_time}, timestamp {current_timestamp}, datestamp {current_datestamp}, active {is_active}")
    
    if not CLOUD_SQL_AVAILABLE:
        print("❌ [ERROR] Cloud SQL Connector not available - cannot record user subscription")
        return False
        
    conn = None
    cur = None
    try:
        conn = get_database_connection()
        if not conn:
            print("❌ [ERROR] Could not establish database connection")
            return False
        
        cur = conn.cursor()
        
        # Start with explicit transaction control
        print(f"🔄 [DEBUG] Starting transaction for user {user_id}")
        
        # Update existing record or insert new record for user/channel combination
        update_query = """
            UPDATE private_channel_users_database 
            SET sub_time = %s, sub_price = %s, timestamp = %s, datestamp = %s, is_active = %s, 
                expire_time = %s, expire_date = %s
            WHERE user_id = %s AND private_channel_id = %s
        """
        update_params = (sub_time, sub_price, current_timestamp, current_datestamp, is_active, 
                        expire_time, expire_date, user_id, private_channel_id)
        cur.execute(update_query, update_params)
        rows_affected = cur.rowcount
        
        if rows_affected == 0:
            # No existing record found, insert new record
            print(f"📝 [DEBUG] No existing record found, inserting new record for user {user_id}")
            insert_query = """
                INSERT INTO private_channel_users_database 
                (private_channel_id, user_id, sub_time, sub_price, timestamp, datestamp, expire_time, expire_date, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            insert_params = (private_channel_id, user_id, sub_time, sub_price, current_timestamp, current_datestamp, 
                           expire_time, expire_date, is_active)
            cur.execute(insert_query, insert_params)
            operation = "inserted new record"
            print(f"✅ [DEBUG] INSERT executed successfully")
        else:
            operation = "updated existing record"
            print(f"✅ [DEBUG] UPDATE executed successfully. Rows affected: {rows_affected}")
        
        # Commit the transaction
        conn.commit()
        print(f"✅ [DEBUG] Transaction committed successfully - {operation} record for user {user_id}")
        
        print(f"🎉 [DEBUG] Successfully recorded user {user_id} for channel {private_channel_id} with {sub_time} minutes subscription")
        print(f"⏰ [DEBUG] Subscription expires at {expire_time} on {expire_date}")
        return True
        
    except Exception as e:
        # Rollback transaction on error
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        
        print(f"❌ [ERROR] Database error recording private channel user: {e}")
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def trigger_payment_splitting(user_id: int, client_wallet_address: str, subscription_price: str, client_payout_currency: str = "ETH") -> None:
    """
    Trigger payment splitting by calling the TPS30 webhook service.
    
    Args:
        user_id: The user's Telegram ID
        client_wallet_address: The client's wallet address to receive tokens
        subscription_price: The subscription price in USD as string
        client_payout_currency: The currency/token to pay out (ETH, USDT, USDC, etc.)
    """
    try:
        payout_currency = client_payout_currency.strip().upper()
        
        # Route all payments to TPS30 service
        print(f"🪙 [INFO] Routing {payout_currency} payment to TPS30 service...")
        trigger_erc20_payment_splitting(user_id, client_wallet_address, subscription_price, payout_currency)
    
    except Exception as e:
        print(f"❌ [ERROR] Payment routing failed: {e}")


def trigger_erc20_payment_splitting(user_id: int, client_wallet_address: str, subscription_price: str, client_payout_currency: str = "ETH") -> None:
    """
    Trigger ERC20 payment splitting by calling the TPS30 webhook.
    
    Args:
        user_id: The user's Telegram ID
        client_wallet_address: The client's Ethereum wallet address to receive tokens
        subscription_price: The subscription price in USD as string
        client_payout_currency: The currency/token to pay out (ETH, USDT, USDC, etc.)
    """
    try:
        # Get the TPS30 webhook URL from environment
        tps30_webhook_url = os.getenv("TPS30_WEBHOOK_URL")
        if not tps30_webhook_url:
            print("⚠️ [WARNING] TPS30_WEBHOOK_URL not configured - skipping ETH payment splitting")
            return
        
        # Validate inputs
        if not client_wallet_address or not client_wallet_address.startswith('0x'):
            print(f"⚠️ [WARNING] Invalid wallet address '{client_wallet_address}' - skipping ETH payment splitting")
            return
        
        if not subscription_price:
            print(f"⚠️ [WARNING] Missing subscription price - skipping ETH payment splitting")
            return
        
        # Prepare payload for TPS30 webhook
        payload = {
            "client_wallet_address": client_wallet_address,
            "sub_price": subscription_price,
            "user_id": user_id,
            "client_payout_currency": client_payout_currency
        }
        
        print(f"🔄 [INFO] Calling TPS30 webhook for {client_payout_currency} payment splitting...")
        print(f"📍 [INFO] URL: {tps30_webhook_url}")
        print(f"💰 [INFO] Payload: User {user_id}, Amount: ${subscription_price}, Wallet: {client_wallet_address}, Currency: {client_payout_currency}")
        
        # Make the webhook call with timeout
        response = requests.post(
            tps30_webhook_url,
            json=payload,
            timeout=30,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ [SUCCESS] {client_payout_currency} payment splitting completed successfully")
            print(f"🔗 [INFO] Transaction Hash: {result.get('transaction_hash', 'unknown')}")
            print(f"💰 [INFO] Amount Sent: {result.get('amount_sent', 'unknown')} {client_payout_currency}")
            print(f"⏱️ [INFO] Processing Time: {result.get('processing_time_seconds', 'unknown')}s")
        else:
            print(f"❌ [ERROR] TPS30 webhook failed with status {response.status_code}")
            print(f"❌ [ERROR] Response: {response.text}")
            
    except requests.exceptions.Timeout:
        print(f"⏰ [ERROR] TPS30 webhook timeout - {client_payout_currency} payment may still be processing")
    except requests.exceptions.RequestException as e:
        print(f"❌ [ERROR] TPS30 webhook request failed: {e}")
    except Exception as e:
        print(f"❌ [ERROR] Unexpected error calling TPS30 webhook: {e}")




async def process_changenow_swap(user_id: int, subscription_price_usd: str, 
                                client_wallet_address: str, client_payout_currency: str) -> None:
    """
    Process ChangeNOW cryptocurrency swap for client payment.
    Converts 30% of subscription payment from ETH to client's preferred currency.
    
    Args:
        user_id: User's Telegram ID
        subscription_price_usd: Subscription price in USD
        client_wallet_address: Client's wallet address to receive converted crypto
        client_payout_currency: Target currency for conversion
    """
    if not CHANGENOW_AVAILABLE:
        print("❌ [ERROR] ChangeNOW swap processor not available - skipping swap")
        return
    
    # Skip swap if target currency is ETH (already received in ETH)
    if client_payout_currency.upper() == "ETH":
        print("ℹ️ [INFO] Target currency is ETH - no swap needed")
        return
    
    try:
        print(f"🔄 [INFO] Initiating ChangeNOW swap for user {user_id}")
        print(f"💰 [INFO] Converting 30% of ${subscription_price_usd} to {client_payout_currency}")
        print(f"📍 [INFO] Destination wallet: {client_wallet_address}")
        
        # Initialize swap processor
        swap_processor = SwapProcessor()
        
        # Create order ID for tracking
        order_id = f"PGP-{user_id}-swap-{int(time.time())}"
        
        # Process the swap
        swap_result = await swap_processor.process_changenow_swap(
            user_id=user_id,
            subscription_price_usd=subscription_price_usd,
            client_wallet_address=client_wallet_address,
            client_payout_currency=client_payout_currency,
            order_id=order_id
        )
        
        if swap_result["success"]:
            if swap_result.get("skipped"):
                print(f"ℹ️ [INFO] ChangeNOW swap skipped: {swap_result.get('reason', 'Unknown reason')}")
            else:
                print(f"✅ [SUCCESS] ChangeNOW swap completed successfully")
                print(f"🔗 [INFO] Exchange ID: {swap_result.get('exchange_id', 'unknown')}")
                print(f"💸 [INFO] ETH sent: {swap_result.get('eth_amount_sent', 'unknown')} ETH")
                print(f"📈 [INFO] Expected {client_payout_currency}: {swap_result.get('expected_output', 'unknown')}")
                print(f"🔐 [INFO] ETH transaction: {swap_result.get('eth_tx_hash', 'unknown')}")
        else:
            print(f"❌ [ERROR] ChangeNOW swap failed: {swap_result.get('error', 'Unknown error')}")
            print(f"⚠️ [WARNING] User {user_id} will still have channel access, but swap failed")
            
    except Exception as e:
        print(f"❌ [ERROR] ChangeNOW swap processing exception: {e}")
        print(f"⚠️ [WARNING] User {user_id} will still have channel access, but swap failed")


# --- Flask app and webhook handler ---
app = Flask(__name__)

@app.route("/", methods=["GET"])
def send_invite():
    # Enhanced logging for webhook entry point
    print(f"🎯 [WEBHOOK] ================== TPH30 Webhook Called ==================")
    print(f"🕐 [WEBHOOK] Timestamp: {get_current_timestamp()}")
    print(f"🌐 [WEBHOOK] Request IP: {request.remote_addr}")
    print(f"📍 [WEBHOOK] Request URL: {request.url}")
    print(f"🔍 [WEBHOOK] Request Args: {dict(request.args)}")
    print(f"📊 [WEBHOOK] This webhook handles payment completion and client payouts")
    
    # Extract token from URL
    token = request.args.get("token")
    if not token:
        print(f"❌ [WEBHOOK] ERROR: No token provided in URL")
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
    subscription_price = None

    # Validate and decode token
    try:
        user_id, closed_channel_id, wallet_address, payout_currency, subscription_time_days, subscription_price = decode_and_verify_token(token, signing_key)
        print(f"✅ [INFO] Successfully decoded token - User: {user_id}, Channel: {closed_channel_id}")
        print(f"💳 [INFO] Wallet: '{wallet_address}', Currency: '{payout_currency}', Subscription: {subscription_time_days} days, Price: ${subscription_price}")
    except Exception as e:
        abort(400, f"Token error: {e}")

    # Calculate expiration time and date based on subscription time (in minutes for testing)
    expire_time, expire_date = calculate_expiration_time(subscription_time_days)
    print(f"📅 [INFO] Calculated expiration: {expire_time} on {expire_date} ({subscription_time_days} minutes from now)")
    
    # Record user subscription in private_channel_users_database table
    print(f"📊 [INFO] Starting database recording process for user {user_id}...")
    
    try:
        # Record user subscription in database with expiration details
        if CLOUD_SQL_AVAILABLE:
            success = record_private_channel_user(
                user_id=user_id,
                private_channel_id=closed_channel_id,
                sub_time=subscription_time_days,
                sub_price=subscription_price,
                expire_time=expire_time,
                expire_date=expire_date,
                is_active=True
            )
            if success:
                print(f"🎯 [INFO] Database: Successfully recorded user {user_id} subscription for channel {closed_channel_id}")
            else:
                print(f"⚠️ [WARNING] Database: Failed to record user {user_id} subscription - continuing with invite")
        else:
            print(f"❌ [ERROR] Cloud SQL Connector not available - skipping database recording for user {user_id}")
            
    except Exception as e:
        # Log error but don't fail the webhook - user should still get their invite
        print(f"❌ [ERROR] Database error (non-fatal): {e}")
        print(f"⚠️ [WARNING] User {user_id} will receive invite but subscription recording failed")

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
        
        # After successful invite, trigger payment splitting
        print(f"🚀 [PAYMENT_SPLITTING] ==================== Starting Client Payout ====================")
        print(f"👤 [PAYMENT_SPLITTING] User ID: {user_id}")
        print(f"💰 [PAYMENT_SPLITTING] Subscription Price: ${subscription_price}")
        print(f"📍 [PAYMENT_SPLITTING] Client Wallet: {wallet_address}")
        print(f"💱 [PAYMENT_SPLITTING] Payout Currency: {payout_currency}")
        print(f"📊 [PAYMENT_SPLITTING] Payment splitting will send ~30% of subscription to client")
        
        trigger_payment_splitting(
            user_id=user_id,
            client_wallet_address=wallet_address,
            subscription_price=subscription_price,
            client_payout_currency=payout_currency
        )
        
        print(f"✅ [PAYMENT_SPLITTING] Payment splitting process completed")
        
        # NEW: Trigger ChangeNOW swap for client payment (30% of subscription)
        if wallet_address and payout_currency and payout_currency.strip():
            print(f"🔄 [CHANGENOW_SWAP] ==================== Starting ChangeNOW Swap ====================")
            print(f"🎯 [CHANGENOW_SWAP] Target: Convert ETH → {payout_currency}")
            print(f"📍 [CHANGENOW_SWAP] Destination: {wallet_address}")
            print(f"💰 [CHANGENOW_SWAP] Base Amount: ${subscription_price} (30% will be swapped)")
            print(f"🌐 [CHANGENOW_SWAP] Service: ChangeNOW API v2")
            
            try:
                # Run the async swap process
                print(f"🚀 [CHANGENOW_SWAP] Executing swap process...")
                asyncio.run(process_changenow_swap(
                    user_id=user_id,
                    subscription_price_usd=subscription_price,
                    client_wallet_address=wallet_address,
                    client_payout_currency=payout_currency
                ))
                print(f"✅ [CHANGENOW_SWAP] ChangeNOW swap process completed successfully")
            except Exception as e:
                print(f"❌ [CHANGENOW_SWAP] ERROR: ChangeNOW swap failed (non-fatal): {e}")
                print(f"🔧 [CHANGENOW_SWAP] This error won't block the main payment flow")
                # Continue - don't fail main payment flow
        else:
            print(f"⚠️ [CHANGENOW_SWAP] WARNING: Skipping ChangeNOW swap - missing wallet info")
            print(f"📝 [CHANGENOW_SWAP] wallet='{wallet_address}', currency='{payout_currency}'")
        
    except Exception as e:
        import traceback
        error_msg = (
            f"telegram error: {e}\n"
            f"user_id: {user_id}, closed_channel_id: {closed_channel_id}\n"
            f"{traceback.format_exc()}"
        )
        print(f"❌ {error_msg}")
        app.logger.error(error_msg)
        abort(
            500,
            f"telegram error: {e}\nuser_id: {user_id}, closed_channel_id: {closed_channel_id}"
        )

    # Success completion logging
    print(f"🎉 [WEBHOOK] ==================== TPH30 Webhook Completed Successfully ====================")
    print(f"✅ [WEBHOOK] User {user_id} granted access to channel {closed_channel_id}")
    print(f"✅ [WEBHOOK] Payment splitting triggered for ${subscription_price}")
    print(f"✅ [WEBHOOK] ChangeNOW swap initiated for {payout_currency} → {wallet_address}")
    print(f"🕐 [WEBHOOK] Process completed at: {get_current_timestamp()}")
    print(f"🔍 [WEBHOOK] Monitor client wallet {wallet_address} for incoming {payout_currency}")
    print(f"📊 [WEBHOOK] Expected client payout: ~30% of ${subscription_price} in {payout_currency}")
    
    return jsonify(status="ok"), 200

# --- Flask entrypoint for deployment ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)