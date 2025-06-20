import os
import time
import struct
import base64
import hmac
import hashlib
import asyncio
from typing import Tuple, Optional
from flask import Flask, request, abort, jsonify
from telegram import Bot
from google.cloud import secretmanager

# Try to import psycopg2 with graceful error handling
try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
    print("[INFO] psycopg2 imported successfully - database functionality enabled")
except ImportError as e:
    print(f"[WARNING] psycopg2 import failed: {e}")
    print("[WARNING] Database functionality will be disabled - webhook will still send invites")
    PSYCOPG2_AVAILABLE = False
    psycopg2 = None

# Try to import Cloud SQL Connector and SQLAlchemy
try:
    from google.cloud.sql.connector import Connector
    import sqlalchemy
    from sqlalchemy import text
    CLOUD_SQL_AVAILABLE = True
    print("[INFO] Cloud SQL Connector imported successfully - enhanced database connectivity enabled")
except ImportError as e:
    print(f"[WARNING] Cloud SQL Connector import failed: {e}")
    print("[WARNING] Falling back to direct psycopg2 connections (may have IP restrictions)")
    CLOUD_SQL_AVAILABLE = False
    Connector = None
    sqlalchemy = None

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
    """Fetch database host from environment variable or Google Secret Manager."""
    try:
        secret_value = os.getenv("DATABASE_HOST_SECRET")
        if not secret_value:
            raise ValueError("Environment variable DATABASE_HOST_SECRET is not set.")
        
        # Check if this is a direct value or a secret path
        if secret_value.startswith("projects/") and "/secrets/" in secret_value:
            # This is a secret path - use Secret Manager API
            print(f"[DEBUG] DATABASE_HOST_SECRET contains secret path: {secret_value}")
            client = secretmanager.SecretManagerServiceClient()
            response = client.access_secret_version(request={"name": secret_value})
            result = response.payload.data.decode("UTF-8")
            print(f"[DEBUG] Fetched database host from Secret Manager: {result}")
            return result
        else:
            # This is a direct value from --set-secrets
            print(f"[DEBUG] DATABASE_HOST_SECRET contains direct value: {secret_value}")
            return secret_value
            
    except Exception as e:
        print(f"Error fetching DATABASE_HOST_SECRET: {e}")
        fallback = "34.58.246.248"
        print(f"[DEBUG] Using fallback database host: {fallback}")
        return fallback

def fetch_database_name() -> str:
    """Fetch database name from environment variable or Google Secret Manager."""
    try:
        secret_value = os.getenv("DATABASE_NAME_SECRET")
        if not secret_value:
            raise ValueError("Environment variable DATABASE_NAME_SECRET is not set.")
        
        # Check if this is a direct value or a secret path
        if secret_value.startswith("projects/") and "/secrets/" in secret_value:
            # This is a secret path - use Secret Manager API
            print(f"[DEBUG] DATABASE_NAME_SECRET contains secret path: {secret_value}")
            client = secretmanager.SecretManagerServiceClient()
            response = client.access_secret_version(request={"name": secret_value})
            result = response.payload.data.decode("UTF-8")
            print(f"[DEBUG] Fetched database name from Secret Manager: {result}")
            return result
        else:
            # This is a direct value from --set-secrets
            print(f"[DEBUG] DATABASE_NAME_SECRET contains direct value: {secret_value}")
            return secret_value
            
    except Exception as e:
        print(f"Error fetching DATABASE_NAME_SECRET: {e}")
        fallback = "client_table"
        print(f"[DEBUG] Using fallback database name: {fallback}")
        return fallback

def fetch_database_user() -> str:
    """Fetch database user from environment variable or Google Secret Manager."""
    try:
        secret_value = os.getenv("DATABASE_USER_SECRET")
        if not secret_value:
            raise ValueError("Environment variable DATABASE_USER_SECRET is not set.")
        
        # Check if this is a direct value or a secret path
        if secret_value.startswith("projects/") and "/secrets/" in secret_value:
            # This is a secret path - use Secret Manager API
            print(f"[DEBUG] DATABASE_USER_SECRET contains secret path: {secret_value}")
            client = secretmanager.SecretManagerServiceClient()
            response = client.access_secret_version(request={"name": secret_value})
            result = response.payload.data.decode("UTF-8")
            print(f"[DEBUG] Fetched database user from Secret Manager: {result}")
            return result
        else:
            # This is a direct value from --set-secrets
            print(f"[DEBUG] DATABASE_USER_SECRET contains direct value: {secret_value}")
            return secret_value
            
    except Exception as e:
        print(f"Error fetching DATABASE_USER_SECRET: {e}")
        fallback = "postgres"
        print(f"[DEBUG] Using fallback database user: {fallback}")
        return fallback

def fetch_database_password() -> str:
    """Fetch database password from environment variable or Google Secret Manager."""
    try:
        secret_value = os.getenv("DATABASE_PASSWORD_SECRET")
        if not secret_value:
            raise ValueError("Environment variable DATABASE_PASSWORD_SECRET is not set.")
        
        # Check if this is a direct value or a secret path
        if secret_value.startswith("projects/") and "/secrets/" in secret_value:
            # This is a secret path - use Secret Manager API
            print(f"[DEBUG] DATABASE_PASSWORD_SECRET contains secret path")
            client = secretmanager.SecretManagerServiceClient()
            response = client.access_secret_version(request={"name": secret_value})
            result = response.payload.data.decode("UTF-8")
            print(f"[DEBUG] Fetched database password from Secret Manager (length: {len(result)})")
            return result
        else:
            # This is a direct value from --set-secrets
            print(f"[DEBUG] DATABASE_PASSWORD_SECRET contains direct value (length: {len(secret_value)})")
            return secret_value
            
    except Exception as e:
        print(f"Error fetching DATABASE_PASSWORD_SECRET: {e}")
        print(f"[DEBUG] No fallback for password - returning None")
        return None  # No fallback for password - this should fail safely

def fetch_cloud_sql_connection_name() -> str:
    """Fetch Cloud SQL connection name from environment variable or Google Secret Manager."""
    try:
        secret_value = os.getenv("CLOUD_SQL_CONNECTION_NAME")
        if not secret_value:
            raise ValueError("Environment variable CLOUD_SQL_CONNECTION_NAME is not set.")
        
        # Check if this is a direct value or a secret path
        if secret_value.startswith("projects/") and "/secrets/" in secret_value:
            # This is a secret path - use Secret Manager API
            print(f"[DEBUG] CLOUD_SQL_CONNECTION_NAME contains secret path")
            client = secretmanager.SecretManagerServiceClient()
            response = client.access_secret_version(request={"name": secret_value})
            result = response.payload.data.decode("UTF-8")
            print(f"[DEBUG] Fetched Cloud SQL connection name from Secret Manager: {result}")
            return result
        else:
            # This is a direct value - likely the connection name itself
            print(f"[DEBUG] CLOUD_SQL_CONNECTION_NAME contains direct value: {secret_value}")
            return secret_value
            
    except Exception as e:
        print(f"Error fetching CLOUD_SQL_CONNECTION_NAME: {e}")
        print(f"[DEBUG] No fallback for Cloud SQL connection name - returning None")
        return None

def get_database_connection():
    """Create and return a database connection using Cloud SQL Connector when available."""
    print("[DEBUG] Starting database connection process...")
    
    # Check if both database drivers are available
    if not PSYCOPG2_AVAILABLE:
        print("[WARNING] psycopg2 not available - cannot create database connection")
        return None
    
    # Fetch credentials
    dbname = fetch_database_name()  
    user = fetch_database_user()
    password = fetch_database_password()
    
    print(f"[DEBUG] Database connection parameters:")
    print(f"[DEBUG]   Database: {dbname}")
    print(f"[DEBUG]   User: {user}")
    print(f"[DEBUG]   Password: {'***' if password else 'None'} (length: {len(password) if password else 0})")
    
    if not password:
        print("[ERROR] Database password is None - cannot connect")
        return None
    
    # Try Cloud SQL Connector first (preferred method)
    if CLOUD_SQL_AVAILABLE:
        print("[DEBUG] Attempting Cloud SQL Connector connection...")
        try:
            connection_name = fetch_cloud_sql_connection_name()
            if not connection_name:
                print("[WARNING] Cloud SQL connection name not available - falling back to direct connection")
            else:
                print(f"[DEBUG] Using Cloud SQL connection: {connection_name}")
                
                # Initialize the Cloud SQL Connector
                connector = Connector()
                
                def getconn():
                    return connector.connect(
                        connection_name,
                        "pg8000",
                        user=user,
                        password=password,
                        db=dbname
                    )
                
                # Test the connection
                connection = getconn()
                print("[DEBUG] ✅ Cloud SQL Connector connection successful!")
                return connection
                
        except Exception as e:
            error_msg = str(e)
            print(f"[WARNING] Cloud SQL Connector failed: {e}")
            
            # Check for specific IAM permission issues
            if "403" in error_msg and "Forbidden" in error_msg:
                print(f"[ERROR] IAM Permission Issue Detected!")
                print(f"[ERROR] Cloud Run service account lacks Cloud SQL permissions.")
                print(f"[ERROR] Required fixes:")
                print(f"[ERROR] 1. Enable Cloud SQL Admin API: gcloud services enable sqladmin.googleapis.com")
                print(f"[ERROR] 2. Grant Cloud SQL Client role to service account")
                print(f"[ERROR] 3. Ensure Cloud SQL instance allows connections")
            elif "Driver" in error_msg and "not supported" in error_msg:
                print(f"[ERROR] Database driver issue - check pg8000 installation")
            
            print(f"[WARNING] Falling back to direct psycopg2 connection...")
    
    # Fallback to direct psycopg2 connection (legacy method)
    print("[DEBUG] Using direct psycopg2 connection...")
    try:
        host = fetch_database_host()
        port = 5432
        
        print(f"[DEBUG]   Host: {host}")
        print(f"[DEBUG]   Port: {port}")
        print("[DEBUG] Attempting direct psycopg2.connect()...")
        
        connection = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port,
            connect_timeout=10  # Add 10 second timeout
        )
        
        print("[DEBUG] ✅ Direct psycopg2 connection successful!")
        return connection
        
    except psycopg2.OperationalError as e:
        print(f"[ERROR] PostgreSQL connection error: {e}")
        print(f"[ERROR] This usually indicates wrong credentials, network issues, or IP blocking")
        print(f"[ERROR] Consider setting CLOUD_SQL_CONNECTION_NAME environment variable for Cloud SQL Connector")
        return None
    except Exception as e:
        print(f"[ERROR] Unexpected error creating database connection: {e}")
        print(f"[ERROR] Error type: {type(e).__name__}")
        return None

def test_database_health() -> bool:
    """
    Test database connectivity and table existence.
    
    Returns:
        True if database is healthy, False otherwise
    """
    print("[DEBUG] Starting database health check...")
    
    if not PSYCOPG2_AVAILABLE:
        print("[WARNING] psycopg2 not available - database health check failed")
        return False
    
    try:
        conn = get_database_connection()
        if not conn:
            print("[ERROR] Database health check failed - no connection")
            return False
        
        with conn, conn.cursor() as cur:
            # Test 1: Basic connection test
            print("[DEBUG] Testing basic connectivity...")
            cur.execute("SELECT 1;")
            result = cur.fetchone()
            if result[0] != 1:
                print("[ERROR] Basic connectivity test failed")
                return False
            print("[DEBUG] ✅ Basic connectivity test passed")
            
            # Test 2: Check if private_channel_users table exists
            print("[DEBUG] Checking if private_channel_users table exists...")
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'private_channel_users'
                );
            """)
            table_exists = cur.fetchone()[0]
            if not table_exists:
                print("[ERROR] Table 'private_channel_users' does not exist")
                return False
            print("[DEBUG] ✅ Table 'private_channel_users' exists")
            
            # Test 3: Check table structure
            print("[DEBUG] Checking table structure...")
            cur.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'private_channel_users'
                ORDER BY ordinal_position;
            """)
            columns = cur.fetchall()
            print(f"[DEBUG] Table columns found: {columns}")
            
            # Expected columns: private_channel_id, user_id, sub_time, is_active
            expected_columns = {'private_channel_id', 'user_id', 'sub_time', 'is_active'}
            actual_columns = {col[0] for col in columns}
            
            if not expected_columns.issubset(actual_columns):
                missing = expected_columns - actual_columns
                print(f"[ERROR] Missing required columns: {missing}")
                return False
            print("[DEBUG] ✅ All required columns present")
            
            print("[DEBUG] ✅ Database health check passed!")
            return True
            
    except Exception as e:
        print(f"[ERROR] Database health check failed: {e}")
        return False

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
    print(f"[DEBUG] Starting database insert for user {user_id}, channel {private_channel_id}, sub_time {sub_time}, active {is_active}")
    
    if not PSYCOPG2_AVAILABLE:
        print("[WARNING] Database functionality disabled - cannot record user subscription")
        return False
        
    try:
        conn = get_database_connection()
        if not conn:
            print("[ERROR] ❌ Could not establish database connection")
            return False
        
        print(f"[DEBUG] Database connection established, preparing SQL query...")
        
        with conn, conn.cursor() as cur:
            # Use INSERT ... ON CONFLICT to handle both insert and update cases
            sql_query = """
                INSERT INTO private_channel_users (private_channel_id, user_id, sub_time, is_active)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (private_channel_id, user_id) 
                DO UPDATE SET 
                    sub_time = EXCLUDED.sub_time,
                    is_active = EXCLUDED.is_active
            """
            sql_params = (private_channel_id, user_id, sub_time, is_active)
            
            print(f"[DEBUG] Executing SQL:")
            print(f"[DEBUG] Query: {sql_query.strip()}")
            print(f"[DEBUG] Parameters: {sql_params}")
            
            cur.execute(sql_query, sql_params)
            
            # Check if any rows were affected
            rows_affected = cur.rowcount
            print(f"[DEBUG] SQL execution completed. Rows affected: {rows_affected}")
            
            print(f"[DEBUG] ✅ Successfully recorded user {user_id} for channel {private_channel_id} with {sub_time} days subscription")
            return True
            
    except psycopg2.Error as e:
        print(f"[ERROR] ❌ PostgreSQL error recording private channel user: {e}")
        print(f"[ERROR] Error code: {e.pgcode if hasattr(e, 'pgcode') else 'N/A'}")
        print(f"[ERROR] Error details: {e.pgerror if hasattr(e, 'pgerror') else 'N/A'}")
        return False
    except Exception as e:
        print(f"[ERROR] ❌ Unexpected error recording private channel user: {e}")
        print(f"[ERROR] Error type: {type(e).__name__}")
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
    print(f"[INFO] Starting database recording process for user {user_id}...")
    
    try:
        # First, run a database health check
        if PSYCOPG2_AVAILABLE:
            print(f"[DEBUG] Running database health check before recording...")
            health_ok = test_database_health()
            if not health_ok:
                print(f"[WARNING] ❌ Database health check failed - skipping database recording")
                print(f"[WARNING] User {user_id} will receive invite but subscription won't be recorded")
            else:
                print(f"[DEBUG] Database health check passed - proceeding with recording...")
                success = record_private_channel_user(
                    user_id=user_id,
                    private_channel_id=closed_channel_id,
                    sub_time=subscription_time_days,
                    is_active=True
                )
                if success:
                    print(f"[INFO] ✅ Database: Successfully recorded user {user_id} subscription for channel {closed_channel_id}")
                else:
                    print(f"[WARNING] ❌ Database: Failed to record user {user_id} subscription - continuing with invite")
        else:
            print(f"[WARNING] ❌ psycopg2 not available - skipping database recording for user {user_id}")
            
    except Exception as e:
        # Log error but don't fail the webhook - user should still get their invite
        print(f"[ERROR] ❌ Database error (non-fatal): {e}")
        print(f"[ERROR] Error type: {type(e).__name__}")
        print(f"[WARNING] User {user_id} will receive invite but subscription recording failed")

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
