#!/usr/bin/env python
"""
np-webhook-10-26: NowPayments IPN Webhook Handler
Receives Instant Payment Notification (IPN) callbacks from NowPayments.
Verifies signature and updates database with payment_id and payment metadata.
"""
import os
import hmac
import hashlib
import json
import requests
from flask import Flask, request, jsonify, abort
from flask_cors import CORS
from google.cloud.sql.connector import Connector
from typing import Optional

app = Flask(__name__)

# ============================================================================
# CORS CONFIGURATION
# ============================================================================
# NOTE: CORS is now only for backward compatibility with cached URLs.
# The payment-processing.html is served from this same service (GET /payment-processing)
# so it uses same-origin requests which don't need CORS.
# CORS is kept here in case old Cloud Storage URLs are still cached somewhere.

# Configure CORS to allow requests from Cloud Storage and custom domain
CORS(app, resources={
    r"/api/*": {
        "origins": [
            "https://storage.googleapis.com",  # Backward compatibility
            "https://www.paygateprime.com",
            "http://localhost:3000",  # For local testing
            "http://localhost:*"
        ],
        "methods": ["GET", "OPTIONS"],
        "allow_headers": ["Content-Type", "Accept"],
        "expose_headers": ["Content-Type"],
        "supports_credentials": False,
        "max_age": 3600
    }
})

print(f"✅ [CORS] Configured for /api/* routes (backward compatibility)")
print(f"   NOTE: Main flow (GET /payment-processing) uses same-origin, no CORS needed")
print(f"   Allowed origins: storage.googleapis.com, www.paygateprime.com, localhost")
print(f"   IPN endpoint (POST /) remains protected (no CORS)")
print(f"")

# ============================================================================
# CONFIGURATION AND INITIALIZATION
# ============================================================================

print(f"🚀 [APP] Initializing np-webhook-10-26 - NowPayments IPN Handler")
print(f"📋 [APP] This service processes IPN callbacks from NowPayments")
print(f"🔐 [APP] Verifies signatures and updates database with payment_id")
print(f"")

# Fetch required secrets from environment (mounted by Cloud Run)
print(f"⚙️ [CONFIG] Loading configuration from Secret Manager...")

# IPN Secret for signature verification
NOWPAYMENTS_IPN_SECRET = (os.getenv('NOWPAYMENTS_IPN_SECRET') or '').strip() or None
if NOWPAYMENTS_IPN_SECRET:
    print(f"✅ [CONFIG] NOWPAYMENTS_IPN_SECRET loaded")
else:
    print(f"❌ [CONFIG] NOWPAYMENTS_IPN_SECRET not found")
    print(f"⚠️ [CONFIG] IPN signature verification will fail!")

# Database credentials
CLOUD_SQL_CONNECTION_NAME = (os.getenv('CLOUD_SQL_CONNECTION_NAME') or '').strip() or None
DATABASE_NAME = (os.getenv('DATABASE_NAME_SECRET') or '').strip() or None
DATABASE_USER = (os.getenv('DATABASE_USER_SECRET') or '').strip() or None
DATABASE_PASSWORD = (os.getenv('DATABASE_PASSWORD_SECRET') or '').strip() or None

print(f"")
print(f"📊 [CONFIG] Database Configuration Status:")
print(f"   CLOUD_SQL_CONNECTION_NAME: {'✅ Loaded' if CLOUD_SQL_CONNECTION_NAME else '❌ Missing'}")
print(f"   DATABASE_NAME_SECRET: {'✅ Loaded' if DATABASE_NAME else '❌ Missing'}")
print(f"   DATABASE_USER_SECRET: {'✅ Loaded' if DATABASE_USER else '❌ Missing'}")
print(f"   DATABASE_PASSWORD_SECRET: {'✅ Loaded' if DATABASE_PASSWORD else '❌ Missing'}")

if not all([CLOUD_SQL_CONNECTION_NAME, DATABASE_NAME, DATABASE_USER, DATABASE_PASSWORD]):
    print(f"")
    print(f"❌ [CONFIG] CRITICAL: Missing database credentials!")
    print(f"⚠️ [CONFIG] Service will not be able to update payment_id in database")
    print(f"⚠️ [CONFIG] Required secrets:")
    print(f"   - CLOUD_SQL_CONNECTION_NAME")
    print(f"   - DATABASE_NAME_SECRET")
    print(f"   - DATABASE_USER_SECRET")
    print(f"   - DATABASE_PASSWORD_SECRET")
else:
    print(f"✅ [CONFIG] All database credentials loaded successfully")
    print(f"🗄️ [CONFIG] Database: {DATABASE_NAME}")
    print(f"🔗 [CONFIG] Instance: {CLOUD_SQL_CONNECTION_NAME}")

print(f"")
print(f"🎯 [APP] Initialization complete - Ready to process IPN callbacks")
print(f"=" * 80)
print(f"")

# Initialize Cloud SQL Connector
connector = None
if all([CLOUD_SQL_CONNECTION_NAME, DATABASE_NAME, DATABASE_USER, DATABASE_PASSWORD]):
    try:
        connector = Connector()
        print(f"✅ [DATABASE] Cloud SQL Connector initialized")
    except Exception as e:
        print(f"❌ [DATABASE] Failed to initialize Cloud SQL Connector: {e}")
else:
    print(f"⚠️ [DATABASE] Skipping connector initialization - missing credentials")

# ============================================================================
# CLOUD TASKS INITIALIZATION
# ============================================================================

print(f"")
print(f"⚙️ [CONFIG] Loading Cloud Tasks configuration...")

# Cloud Tasks configuration for triggering GCWebhook1
CLOUD_TASKS_PROJECT_ID = (os.getenv('CLOUD_TASKS_PROJECT_ID') or '').strip() or None
CLOUD_TASKS_LOCATION = (os.getenv('CLOUD_TASKS_LOCATION') or '').strip() or None
GCWEBHOOK1_QUEUE = (os.getenv('GCWEBHOOK1_QUEUE') or '').strip() or None
GCWEBHOOK1_URL = (os.getenv('GCWEBHOOK1_URL') or '').strip() or None

# 🆕 TelePay Bot URL for notification service (NOTIFICATION_MANAGEMENT_ARCHITECTURE)
TELEPAY_BOT_URL = (os.getenv('TELEPAY_BOT_URL') or '').strip() or None

print(f"   CLOUD_TASKS_PROJECT_ID: {'✅ Loaded' if CLOUD_TASKS_PROJECT_ID else '❌ Missing'}")
print(f"   CLOUD_TASKS_LOCATION: {'✅ Loaded' if CLOUD_TASKS_LOCATION else '❌ Missing'}")
print(f"   GCWEBHOOK1_QUEUE: {'✅ Loaded' if GCWEBHOOK1_QUEUE else '❌ Missing'}")
print(f"   GCWEBHOOK1_URL: {'✅ Loaded' if GCWEBHOOK1_URL else '❌ Missing'}")
print(f"   🆕 TELEPAY_BOT_URL: {'✅ Loaded' if TELEPAY_BOT_URL else '❌ Missing (notifications disabled)'}")

# Initialize Cloud Tasks client
cloudtasks_client = None
if all([CLOUD_TASKS_PROJECT_ID, CLOUD_TASKS_LOCATION]):
    try:
        from cloudtasks_client import CloudTasksClient
        cloudtasks_client = CloudTasksClient(CLOUD_TASKS_PROJECT_ID, CLOUD_TASKS_LOCATION)
        print(f"✅ [CLOUDTASKS] Client initialized successfully")
    except Exception as e:
        print(f"❌ [CLOUDTASKS] Failed to initialize client: {e}")
        print(f"⚠️ [CLOUDTASKS] GCWebhook1 triggering will not work!")
else:
    print(f"⚠️ [CLOUDTASKS] Skipping initialization - missing configuration")
    print(f"⚠️ [CLOUDTASKS] GCWebhook1 will NOT be triggered after IPN validation!")

print(f"")


# ============================================================================
# COINGECKO PRICE FETCHING
# ============================================================================

def get_crypto_usd_price(crypto_symbol: str) -> Optional[float]:
    """
    Fetch current USD price for a cryptocurrency from CoinGecko API.

    Args:
        crypto_symbol: Cryptocurrency symbol (e.g., 'ETH', 'BTC')

    Returns:
        Current USD price or None if fetch fails
    """
    # Map common symbols to CoinGecko IDs
    coin_id_map = {
        'ETH': 'ethereum',
        'BTC': 'bitcoin',
        'USDT': 'tether',
        'USDC': 'usd-coin',
        'LTC': 'litecoin',
        'TRX': 'tron',
        'BNB': 'binancecoin',
        'SOL': 'solana',
        'MATIC': 'matic-network'
    }

    coin_id = coin_id_map.get(crypto_symbol.upper())
    if not coin_id:
        print(f"❌ [PRICE] Unsupported crypto symbol: {crypto_symbol}")
        print(f"💡 [PRICE] Supported symbols: {', '.join(coin_id_map.keys())}")
        return None

    try:
        print(f"🔍 [PRICE] Fetching {crypto_symbol} price from CoinGecko...")

        url = f"https://api.coingecko.com/api/v3/simple/price"
        params = {
            'ids': coin_id,
            'vs_currencies': 'usd'
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        usd_price = data.get(coin_id, {}).get('usd')

        if usd_price:
            print(f"💰 [PRICE] {crypto_symbol}/USD = ${usd_price:,.2f}")
            return float(usd_price)
        else:
            print(f"❌ [PRICE] Price not found in CoinGecko response")
            return None

    except requests.exceptions.Timeout:
        print(f"❌ [PRICE] CoinGecko API timeout after 10 seconds")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ [PRICE] Failed to fetch price from CoinGecko: {e}")
        return None
    except Exception as e:
        print(f"❌ [PRICE] Unexpected error fetching price: {e}")
        return None


# ============================================================================
# DATABASE FUNCTIONS
# ============================================================================

def parse_order_id(order_id: str) -> tuple:
    """
    Parse NowPayments order_id to extract user_id and open_channel_id.

    Format: PGP-{user_id}|{open_channel_id}
    Example: PGP-6271402111|-1003268562225

    Also supports old format for backward compatibility:
    Old Format: PGP-{user_id}-{channel_id} (loses negative sign)
    Example: PGP-6271402111-1003268562225

    Returns:
        Tuple of (user_id, open_channel_id) or (None, None) if invalid
    """
    try:
        # Check for new format first (with | separator)
        if '|' in order_id:
            # New format: PGP-{user_id}|{open_channel_id}
            prefix_and_user, channel_id_str = order_id.split('|')
            if not prefix_and_user.startswith('PGP-'):
                print(f"❌ [PARSE] order_id does not start with 'PGP-': {order_id}")
                return None, None
            user_id_str = prefix_and_user[4:]  # Remove 'PGP-' prefix
            user_id = int(user_id_str)
            open_channel_id = int(channel_id_str)  # Preserves negative sign
            print(f"✅ [PARSE] New format detected")
            print(f"   User ID: {user_id}")
            print(f"   Open Channel ID: {open_channel_id}")
            return user_id, open_channel_id

        # Fallback to old format for backward compatibility (during transition)
        else:
            # Old format: PGP-{user_id}-{channel_id} (loses negative sign)
            parts = order_id.split('-')
            if len(parts) < 3 or parts[0] != 'PGP':
                print(f"❌ [PARSE] Invalid order_id format: {order_id}")
                return None, None
            user_id = int(parts[1])
            channel_id = int(parts[2])
            # FIX: Add negative sign back (all Telegram channels are negative)
            open_channel_id = -abs(channel_id)
            print(f"⚠️ [PARSE] Old format detected - added negative sign")
            print(f"   User ID: {user_id}")
            print(f"   Open Channel ID: {open_channel_id} (corrected from {channel_id})")
            return user_id, open_channel_id

    except (ValueError, IndexError) as e:
        print(f"❌ [PARSE] Failed to parse order_id '{order_id}': {e}")
        return None, None


def get_db_connection():
    """Create and return a database connection."""
    if not connector:
        print(f"❌ [DATABASE] Connector not initialized")
        return None

    try:
        connection = connector.connect(
            CLOUD_SQL_CONNECTION_NAME,
            "pg8000",
            user=DATABASE_USER,
            password=DATABASE_PASSWORD,
            db=DATABASE_NAME
        )
        print(f"🔗 [DATABASE] Connection established")
        return connection
    except Exception as e:
        print(f"❌ [DATABASE] Connection failed: {e}")
        return None


def update_payment_data(order_id: str, payment_data: dict) -> bool:
    """
    UPSERT payment data into private_channel_users_database.

    This function handles both scenarios:
    1. UPDATE: Existing record (normal bot flow)
    2. INSERT: No existing record (direct payment link, race condition)

    Three-step process:
    1. Parse order_id to get user_id and open_channel_id
    2. Look up closed_channel_id + client config from main_clients_database
    3. UPSERT into private_channel_users_database with full client configuration

    Args:
        order_id: NowPayments order_id (format: PGP-{user_id}|{open_channel_id})
        payment_data: Dictionary with payment metadata from IPN

    Returns:
        True if operation successful, False otherwise
    """
    conn = None
    cur = None

    try:
        # Step 1: Parse order_id
        user_id, open_channel_id = parse_order_id(order_id)
        if user_id is None or open_channel_id is None:
            print(f"❌ [DATABASE] Invalid order_id format: {order_id}")
            return False

        print(f"")
        print(f"📝 [DATABASE] Parsed order_id successfully:")
        print(f"   User ID: {user_id}")
        print(f"   Open Channel ID: {open_channel_id}")

        conn = get_db_connection()
        if not conn:
            return False

        cur = conn.cursor()

        # Step 2: Look up closed_channel_id + client configuration from main_clients_database
        print(f"")
        print(f"🔍 [DATABASE] Looking up channel mapping and client config...")
        print(f"   Searching for open_channel_id: {open_channel_id}")

        cur.execute("""
            SELECT
                closed_channel_id,
                client_wallet_address,
                client_payout_currency::text,
                client_payout_network::text
            FROM main_clients_database
            WHERE open_channel_id = %s
        """, (str(open_channel_id),))

        result = cur.fetchone()

        if not result or not result[0]:
            print(f"")
            print(f"❌ [DATABASE] No closed_channel_id found for open_channel_id: {open_channel_id}")
            print(f"⚠️ [DATABASE] This channel may not be registered in main_clients_database")
            print(f"💡 [HINT] Register this channel first:")
            print(f"   INSERT INTO main_clients_database (open_channel_id, closed_channel_id, ...)")
            print(f"   VALUES ('{open_channel_id}', '<closed_channel_id>', ...)")
            return False

        closed_channel_id = result[0]
        client_wallet_address = result[1]
        client_payout_currency = result[2]
        client_payout_network = result[3]

        print(f"✅ [DATABASE] Found channel mapping:")
        print(f"   Open Channel ID (public): {open_channel_id}")
        print(f"   Closed Channel ID (private): {closed_channel_id}")
        print(f"   Client Wallet: {client_wallet_address}")
        print(f"   Payout Currency: {client_payout_currency}")
        print(f"   Payout Network: {client_payout_network}")

        # Step 3: UPSERT into private_channel_users_database
        # This handles both new records (INSERT) and existing records (UPDATE)
        print(f"")
        print(f"🗄️ [DATABASE] Upserting payment record (INSERT or UPDATE)...")
        print(f"   Target table: private_channel_users_database")
        print(f"   Key: user_id = {user_id} AND private_channel_id = {closed_channel_id}")

        # Calculate expiration (30 days from now as default)
        from datetime import datetime, timedelta
        now = datetime.now()
        expiration = now + timedelta(days=30)
        expire_time = expiration.strftime('%H:%M:%S')
        expire_date = expiration.strftime('%Y-%m-%d')
        current_timestamp = now.strftime('%H:%M:%S')
        current_datestamp = now.strftime('%Y-%m-%d')

        # First, check if record exists to determine operation type
        cur.execute("""
            SELECT id FROM private_channel_users_database
            WHERE user_id = %s AND private_channel_id = %s
            ORDER BY id DESC LIMIT 1
        """, (user_id, closed_channel_id))

        existing_record = cur.fetchone()

        if existing_record:
            # Record exists - UPDATE
            print(f"📝 [DATABASE] Existing record found (id={existing_record[0]}) - will UPDATE")

            update_query = """
                UPDATE private_channel_users_database
                SET
                    nowpayments_payment_id = %s,
                    nowpayments_invoice_id = %s,
                    nowpayments_order_id = %s,
                    nowpayments_pay_address = %s,
                    nowpayments_payment_status = %s,
                    nowpayments_pay_amount = %s,
                    nowpayments_pay_currency = %s,
                    nowpayments_outcome_amount = %s,
                    nowpayments_price_amount = %s,
                    nowpayments_price_currency = %s,
                    nowpayments_outcome_currency = %s,
                    payment_status = 'confirmed',
                    nowpayments_created_at = CURRENT_TIMESTAMP,
                    nowpayments_updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s AND private_channel_id = %s
                AND id = %s
            """

            cur.execute(update_query, (
                payment_data.get('payment_id'),
                payment_data.get('invoice_id'),
                payment_data.get('order_id'),
                payment_data.get('pay_address'),
                payment_data.get('payment_status'),
                payment_data.get('pay_amount'),
                payment_data.get('pay_currency'),
                payment_data.get('outcome_amount'),
                payment_data.get('price_amount'),
                payment_data.get('price_currency'),
                payment_data.get('outcome_currency'),
                user_id,
                closed_channel_id,
                existing_record[0]
            ))

            operation = "UPDATED"

        else:
            # No record exists - INSERT with full client configuration
            print(f"📝 [DATABASE] No existing record - will INSERT new record")
            print(f"💡 [DATABASE] Populating default subscription data (30 days)")

            insert_query = """
                INSERT INTO private_channel_users_database (
                    user_id,
                    private_channel_id,
                    sub_time,
                    sub_price,
                    timestamp,
                    datestamp,
                    expire_time,
                    expire_date,
                    is_active,
                    payment_status,
                    nowpayments_payment_id,
                    nowpayments_invoice_id,
                    nowpayments_order_id,
                    nowpayments_pay_address,
                    nowpayments_payment_status,
                    nowpayments_pay_amount,
                    nowpayments_pay_currency,
                    nowpayments_outcome_amount,
                    nowpayments_price_amount,
                    nowpayments_price_currency,
                    nowpayments_outcome_currency,
                    nowpayments_created_at,
                    nowpayments_updated_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """

            cur.execute(insert_query, (
                user_id,
                closed_channel_id,
                30,  # Default subscription time: 30 days
                str(payment_data.get('price_amount')),  # Use price_amount as sub_price
                current_timestamp,
                current_datestamp,
                expire_time,
                expire_date,
                True,  # is_active
                'confirmed',  # payment_status
                payment_data.get('payment_id'),
                payment_data.get('invoice_id'),
                payment_data.get('order_id'),
                payment_data.get('pay_address'),
                payment_data.get('payment_status'),
                payment_data.get('pay_amount'),
                payment_data.get('pay_currency'),
                payment_data.get('outcome_amount'),
                payment_data.get('price_amount'),
                payment_data.get('price_currency'),
                payment_data.get('outcome_currency')
            ))

            operation = "INSERTED"

        conn.commit()
        rows_affected = cur.rowcount

        print(f"")
        print(f"✅ [DATABASE] Successfully {operation} {rows_affected} record(s)")
        print(f"   User ID: {user_id}")
        print(f"   Private Channel ID: {closed_channel_id}")
        print(f"   Payment ID: {payment_data.get('payment_id')}")
        print(f"   Invoice ID: {payment_data.get('invoice_id')}")
        print(f"   NowPayments Status: {payment_data.get('payment_status')}")
        print(f"   Payment Status: confirmed ✅")
        print(f"   Amount: {payment_data.get('outcome_amount')} {payment_data.get('pay_currency')}")

        if operation == "INSERTED":
            print(f"   Subscription: 30 days")
            print(f"   Expires: {expire_date} {expire_time}")

        return True

    except Exception as e:
        print(f"")
        print(f"❌ [DATABASE] Operation failed with exception: {e}")
        print(f"🔄 [DATABASE] Rolling back transaction...")
        if conn:
            conn.rollback()
        import traceback
        traceback.print_exc()
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
            print(f"🔌 [DATABASE] Connection closed")


# ============================================================================
# IPN SIGNATURE VERIFICATION
# ============================================================================

def verify_ipn_signature(payload: bytes, signature: str) -> bool:
    """
    Verify IPN callback signature from NowPayments.

    Args:
        payload: Raw request body bytes
        signature: Signature from x-nowpayments-sig header

    Returns:
        True if signature valid, False otherwise
    """
    if not NOWPAYMENTS_IPN_SECRET:
        print(f"❌ [IPN] Cannot verify signature - NOWPAYMENTS_IPN_SECRET not configured")
        return False

    try:
        # Calculate expected signature
        expected_sig = hmac.new(
            NOWPAYMENTS_IPN_SECRET.encode('utf-8'),
            payload,
            hashlib.sha512
        ).hexdigest()

        # Compare signatures
        if hmac.compare_digest(expected_sig, signature):
            print(f"✅ [IPN] Signature verified successfully")
            return True
        else:
            print(f"❌ [IPN] Signature verification failed")
            print(f"   Expected: {expected_sig[:20]}...")
            print(f"   Received: {signature[:20]}...")
            return False

    except Exception as e:
        print(f"❌ [IPN] Signature verification error: {e}")
        return False


# ============================================================================
# IPN ENDPOINT
# ============================================================================

@app.route('/', methods=['POST'])
def handle_ipn():
    """
    Handle IPN callback from NowPayments.
    Verifies signature and updates database with payment_id.
    """
    print(f"")
    print(f"=" * 80)
    print(f"📬 [IPN] Received callback from NowPayments")
    print(f"🌐 [IPN] Source IP: {request.remote_addr}")
    print(f"⏰ [IPN] Timestamp: {request.headers.get('Date', 'N/A')}")

    # Get signature from header
    signature = request.headers.get('x-nowpayments-sig')
    if not signature:
        print(f"❌ [IPN] Missing x-nowpayments-sig header")
        print(f"🚫 [IPN] Rejecting request - no signature")
        abort(403, "Missing signature header")

    print(f"🔐 [IPN] Signature header present: {signature[:20]}...")

    # Get raw request body for signature verification
    payload = request.get_data()
    print(f"📦 [IPN] Payload size: {len(payload)} bytes")

    # Verify signature
    if not verify_ipn_signature(payload, signature):
        print(f"❌ [IPN] Signature verification failed - rejecting request")
        print(f"=" * 80)
        abort(403, "Invalid signature")

    # Parse JSON payload
    try:
        ipn_data = request.get_json()
        print(f"")
        print(f"📋 [IPN] Payment Data Received:")
        print(f"   Payment ID: {ipn_data.get('payment_id', 'N/A')}")
        print(f"   Order ID: {ipn_data.get('order_id', 'N/A')}")
        print(f"   Payment Status: {ipn_data.get('payment_status', 'N/A')}")
        print(f"   Pay Amount: {ipn_data.get('pay_amount', 'N/A')} {ipn_data.get('pay_currency', 'N/A')}")
        print(f"   Outcome Amount: {ipn_data.get('outcome_amount', 'N/A')} {ipn_data.get('outcome_currency', ipn_data.get('pay_currency', 'N/A'))}")
        print(f"   Price Amount: {ipn_data.get('price_amount', 'N/A')} {ipn_data.get('price_currency', 'N/A')}")
        print(f"   Pay Address: {ipn_data.get('pay_address', 'N/A')}")

    except Exception as e:
        print(f"❌ [IPN] Failed to parse JSON payload: {e}")
        print(f"=" * 80)
        abort(400, "Invalid JSON payload")

    # ============================================================================
    # CRITICAL: Validate payment_status before processing
    # ============================================================================
    payment_status = ipn_data.get('payment_status', '').lower()

    # Define allowed statuses (only process finished payments)
    ALLOWED_PAYMENT_STATUSES = ['finished']

    print(f"🔍 [IPN] Payment status received: '{payment_status}'")
    print(f"✅ [IPN] Allowed statuses: {ALLOWED_PAYMENT_STATUSES}")

    if payment_status not in ALLOWED_PAYMENT_STATUSES:
        print(f"=" * 80)
        print(f"⏸️ [IPN] PAYMENT STATUS NOT READY FOR PROCESSING")
        print(f"=" * 80)
        print(f"📊 [IPN] Current status: '{payment_status}'")
        print(f"⏳ [IPN] Waiting for status: 'finished'")
        print(f"💳 [IPN] Payment ID: {ipn_data.get('payment_id')}")
        print(f"💰 [IPN] Amount: {ipn_data.get('price_amount')} {ipn_data.get('price_currency')}")
        print(f"📝 [IPN] Action: Acknowledged but not processed")
        print(f"🔄 [IPN] NowPayments will send another IPN when status becomes 'finished'")
        print(f"=" * 80)

        # Return 200 OK to acknowledge receipt to NowPayments
        # But DO NOT trigger GCWebhook1 or any downstream processing
        return jsonify({
            "status": "acknowledged",
            "message": f"IPN received but not processed. Waiting for status 'finished' (current: {payment_status})",
            "payment_id": ipn_data.get('payment_id'),
            "current_status": payment_status,
            "required_status": "finished"
        }), 200

    # If we reach here, payment_status is 'finished' - proceed with processing
    print(f"=" * 80)
    print(f"✅ [IPN] PAYMENT STATUS VALIDATED: '{payment_status}'")
    print(f"✅ [IPN] Proceeding with payment processing")
    print(f"=" * 80)

    # Extract required fields
    order_id = ipn_data.get('order_id')
    if not order_id:
        print(f"❌ [IPN] Missing order_id in payload")
        print(f"=" * 80)
        abort(400, "Missing order_id")

    # Update database with payment data
    print(f"")
    print(f"🗄️ [DATABASE] Updating database with payment data...")

    payment_data = {
        'payment_id': ipn_data.get('payment_id'),
        'invoice_id': ipn_data.get('invoice_id'),
        'order_id': ipn_data.get('order_id'),
        'pay_address': ipn_data.get('pay_address'),
        'payment_status': ipn_data.get('payment_status'),
        'pay_amount': ipn_data.get('pay_amount'),
        'pay_currency': ipn_data.get('pay_currency'),
        'outcome_amount': ipn_data.get('outcome_amount'),
        'price_amount': ipn_data.get('price_amount'),           # NEW: Original USD amount
        'price_currency': ipn_data.get('price_currency'),       # NEW: Original currency
        'outcome_currency': ipn_data.get('outcome_currency')    # NEW: Outcome currency
    }

    # If outcome_currency not provided, infer from pay_currency
    # (NowPayments might not always include outcome_currency)
    if not payment_data.get('outcome_currency'):
        # Assume outcome is in same currency as payment
        payment_data['outcome_currency'] = payment_data.get('pay_currency')
        print(f"💡 [IPN] outcome_currency not provided, inferring from pay_currency: {payment_data['outcome_currency']}")

    success = update_payment_data(order_id, payment_data)

    if not success:
        print(f"")
        print(f"⚠️ [IPN] Database update failed")
        print(f"🔄 [IPN] Returning 500 - NowPayments will retry")
        print(f"=" * 80)
        print(f"")
        abort(500, "Database update failed")

    # ============================================================================
    # NEW: Calculate Outcome Amount in USD using CoinGecko
    # ============================================================================
    print(f"")
    print(f"💱 [CONVERSION] Calculating USD value of outcome amount...")

    outcome_amount = payment_data.get('outcome_amount')
    outcome_currency = payment_data.get('outcome_currency', payment_data.get('pay_currency'))
    outcome_amount_usd = None

    # Check if outcome is already in USD/stablecoin
    if outcome_currency and outcome_currency.upper() in ['USDT', 'USDC', 'USD', 'BUSD', 'DAI']:
        # Already in USD equivalent - no conversion needed
        outcome_amount_usd = float(outcome_amount) if outcome_amount else None
        if outcome_amount_usd:
            print(f"✅ [CONVERSION] Already in USD equivalent: ${outcome_amount_usd:.2f}")
    elif outcome_currency and outcome_amount:
        # Fetch current market price from CoinGecko
        crypto_usd_price = get_crypto_usd_price(outcome_currency)

        if crypto_usd_price:
            # Calculate USD value
            outcome_amount_usd = float(outcome_amount) * crypto_usd_price
            print(f"💰 [CONVERT] {outcome_amount} {outcome_currency} × ${crypto_usd_price:,.2f}")
            print(f"💰 [CONVERT] = ${outcome_amount_usd:.2f} USD")
        else:
            print(f"❌ [CONVERT] Failed to fetch {outcome_currency} price from CoinGecko")
            print(f"⚠️ [CONVERT] Will not calculate outcome_amount_usd")
    else:
        print(f"⚠️ [CONVERT] Missing outcome_amount or outcome_currency")
        print(f"   outcome_amount: {outcome_amount}")
        print(f"   outcome_currency: {outcome_currency}")

    if outcome_amount_usd:
        print(f"💰 [VALIDATION] Final Outcome in USD: ${outcome_amount_usd:.2f}")

        # Update database with outcome_amount_usd
        try:
            # Need to get user_id and closed_channel_id again
            user_id, open_channel_id = parse_order_id(order_id)
            if user_id and open_channel_id:
                conn = get_db_connection()
                if conn:
                    cur = conn.cursor()

                    # Get closed_channel_id
                    cur.execute(
                        "SELECT closed_channel_id FROM main_clients_database WHERE open_channel_id = %s",
                        (str(open_channel_id),)
                    )
                    result = cur.fetchone()

                    if result:
                        closed_channel_id = result[0]

                        # Update outcome_amount_usd
                        cur.execute("""
                            UPDATE private_channel_users_database
                            SET nowpayments_outcome_amount_usd = %s
                            WHERE user_id = %s AND private_channel_id = %s
                            AND id = (
                                SELECT id FROM private_channel_users_database
                                WHERE user_id = %s AND private_channel_id = %s
                                ORDER BY id DESC LIMIT 1
                            )
                        """, (outcome_amount_usd, user_id, closed_channel_id, user_id, closed_channel_id))

                        conn.commit()
                        print(f"✅ [DATABASE] Updated nowpayments_outcome_amount_usd: ${outcome_amount_usd:.2f}")

                        # Now fetch subscription details for GCWebhook1 triggering
                        # JOIN with main_clients_database to get wallet/payout info
                        cur.execute("""
                            SELECT
                                c.client_wallet_address,
                                c.client_payout_currency::text,
                                c.client_payout_network::text,
                                u.sub_time,
                                u.sub_price
                            FROM private_channel_users_database u
                            JOIN main_clients_database c ON u.private_channel_id = c.closed_channel_id
                            WHERE u.user_id = %s AND u.private_channel_id = %s
                            ORDER BY u.id DESC LIMIT 1
                        """, (user_id, closed_channel_id))

                        sub_data = cur.fetchone()

                        cur.close()
                        conn.close()

                        # ============================================================================
                        # IDEMPOTENCY CHECK: Prevent duplicate payment processing
                        # ============================================================================

                        nowpayments_payment_id = payment_data['payment_id']

                        print(f"")
                        print(f"🔍 [IDEMPOTENCY] Checking if payment {nowpayments_payment_id} already processed...")

                        try:
                            # Query database to check if payment already processed
                            conn_check = get_db_connection()
                            if conn_check:
                                cur_check = conn_check.cursor()

                                cur_check.execute("""
                                    SELECT
                                        gcwebhook1_processed,
                                        telegram_invite_sent,
                                        telegram_invite_sent_at
                                    FROM processed_payments
                                    WHERE payment_id = %s
                                """, (nowpayments_payment_id,))

                                existing_payment = cur_check.fetchone()

                                cur_check.close()
                                conn_check.close()

                                if existing_payment and existing_payment[0]:  # gcwebhook1_processed = TRUE
                                    print(f"✅ [IDEMPOTENCY] Payment {nowpayments_payment_id} already processed")
                                    print(f"   GCWebhook1 processed: TRUE")
                                    print(f"   Telegram invite sent: {existing_payment[1]}")
                                    if existing_payment[2]:
                                        print(f"   Invite sent at: {existing_payment[2]}")

                                    # Already processed - return success without re-enqueueing
                                    print(f"✅ [IPN] IPN acknowledged (payment already handled)")
                                    print(f"=" * 80)
                                    print(f"")
                                    return jsonify({
                                        "status": "success",
                                        "message": "IPN processed (already handled)",
                                        "payment_id": nowpayments_payment_id
                                    }), 200

                                elif existing_payment:
                                    # Record exists but not fully processed
                                    print(f"⚠️ [IDEMPOTENCY] Payment {nowpayments_payment_id} record exists but processing incomplete")
                                    print(f"   GCWebhook1 processed: {existing_payment[0]}")
                                    print(f"   Will allow re-processing to complete")
                                else:
                                    # No existing record - first time processing
                                    print(f"🆕 [IDEMPOTENCY] Payment {nowpayments_payment_id} is new - creating processing record")

                                    # Insert initial record (prevents race conditions)
                                    conn_insert = get_db_connection()
                                    if conn_insert:
                                        cur_insert = conn_insert.cursor()

                                        cur_insert.execute("""
                                            INSERT INTO processed_payments (payment_id, user_id, channel_id)
                                            VALUES (%s, %s, %s)
                                            ON CONFLICT (payment_id) DO NOTHING
                                        """, (nowpayments_payment_id, user_id, closed_channel_id))

                                        conn_insert.commit()
                                        cur_insert.close()
                                        conn_insert.close()

                                        print(f"✅ [IDEMPOTENCY] Created processing record for payment {nowpayments_payment_id}")
                                    else:
                                        print(f"⚠️ [IDEMPOTENCY] Failed to create processing record (DB connection failed)")
                                        print(f"⚠️ [IDEMPOTENCY] Proceeding with processing (fail-open mode)")
                            else:
                                print(f"⚠️ [IDEMPOTENCY] Database connection failed - cannot check idempotency")
                                print(f"⚠️ [IDEMPOTENCY] Proceeding with processing (fail-open mode)")

                        except Exception as e:
                            print(f"❌ [IDEMPOTENCY] Error during idempotency check: {e}")
                            import traceback
                            traceback.print_exc()
                            print(f"⚠️ [IDEMPOTENCY] Proceeding with processing (fail-open mode)")

                        print(f"")
                        print(f"🚀 [ORCHESTRATION] Proceeding to enqueue payment to GCWebhook1...")

                        # ============================================================================
                        # NEW: Trigger GCWebhook1 for Payment Orchestration
                        # ============================================================================
                        if sub_data:
                            wallet_address = sub_data[0]
                            payout_currency = sub_data[1]
                            payout_network = sub_data[2]
                            subscription_time_days = sub_data[3]
                            subscription_price = str(sub_data[4])  # Ensure string type

                            print(f"")
                            print(f"🚀 [ORCHESTRATION] Triggering GCWebhook1 for payment processing...")

                            if not cloudtasks_client:
                                print(f"❌ [ORCHESTRATION] Cloud Tasks client not initialized")
                                print(f"⚠️ [ORCHESTRATION] Cannot trigger GCWebhook1 - payment will not be processed!")
                            elif not GCWEBHOOK1_QUEUE or not GCWEBHOOK1_URL:
                                print(f"❌ [ORCHESTRATION] GCWebhook1 configuration missing")
                                print(f"⚠️ [ORCHESTRATION] Cannot trigger GCWebhook1 - payment will not be processed!")
                            else:
                                try:
                                    task_name = cloudtasks_client.enqueue_gcwebhook1_validated_payment(
                                        queue_name=GCWEBHOOK1_QUEUE,
                                        target_url=f"{GCWEBHOOK1_URL}/process-validated-payment",
                                        user_id=user_id,
                                        closed_channel_id=closed_channel_id,
                                        wallet_address=wallet_address,
                                        payout_currency=payout_currency,
                                        payout_network=payout_network,
                                        subscription_time_days=subscription_time_days,
                                        subscription_price=subscription_price,
                                        outcome_amount_usd=outcome_amount_usd,  # CRITICAL: Real amount
                                        nowpayments_payment_id=payment_data['payment_id'],
                                        nowpayments_pay_address=ipn_data.get('pay_address'),
                                        nowpayments_outcome_amount=outcome_amount,
                                        payment_status=payment_status  # ✅ NEW: Pass validated status to GCWebhook1
                                    )

                                    if task_name:
                                        print(f"✅ [ORCHESTRATION] Successfully enqueued to GCWebhook1")
                                        print(f"🆔 [ORCHESTRATION] Task: {task_name}")

                                        # 🆕 Trigger notification service (NOTIFICATION_MANAGEMENT_ARCHITECTURE)
                                        try:
                                            print(f"")
                                            print(f"📬 [NOTIFICATION] Triggering payment notification...")

                                            if TELEPAY_BOT_URL:
                                                # Determine payment type
                                                payment_type = 'donation' if subscription_time_days == 0 else 'subscription'

                                                # Prepare notification payload
                                                notification_payload = {
                                                    'open_channel_id': open_channel_id,
                                                    'payment_type': payment_type,
                                                    'payment_data': {
                                                        'user_id': user_id,
                                                        'username': None,  # Could fetch from Telegram API if needed
                                                        'amount_crypto': outcome_amount,
                                                        'amount_usd': str(outcome_amount_usd),
                                                        'crypto_currency': outcome_currency,
                                                        'timestamp': payment_data.get('created_at', 'N/A')
                                                    }
                                                }

                                                # Add payment-type-specific data
                                                if payment_type == 'subscription':
                                                    # Determine tier based on price
                                                    tier = 1  # Default
                                                    if subscription_price == sub_data[9]:  # sub_2_price
                                                        tier = 2
                                                    elif subscription_price == sub_data[11]:  # sub_3_price
                                                        tier = 3

                                                    notification_payload['payment_data'].update({
                                                        'tier': tier,
                                                        'tier_price': str(subscription_price),
                                                        'duration_days': subscription_time_days
                                                    })

                                                # Send HTTP POST to TelePay Bot notification endpoint
                                                try:
                                                    response = requests.post(
                                                        f"{TELEPAY_BOT_URL}/send-notification",
                                                        json=notification_payload,
                                                        timeout=5
                                                    )

                                                    if response.status_code == 200:
                                                        print(f"✅ [NOTIFICATION] Notification triggered successfully")
                                                        print(f"📤 [NOTIFICATION] Response: {response.json()}")
                                                    else:
                                                        print(f"⚠️ [NOTIFICATION] Notification request failed: {response.status_code}")
                                                        print(f"📄 [NOTIFICATION] Response: {response.text}")

                                                except requests.exceptions.Timeout:
                                                    print(f"⏱️ [NOTIFICATION] Request timeout (5s) - notification may still be processed")
                                                except requests.exceptions.ConnectionError as e:
                                                    print(f"🔌 [NOTIFICATION] Connection error: {e}")
                                                except Exception as e:
                                                    print(f"❌ [NOTIFICATION] Request error: {e}")

                                            else:
                                                print(f"⏭️ [NOTIFICATION] TELEPAY_BOT_URL not configured, skipping notification")

                                        except Exception as e:
                                            print(f"❌ [NOTIFICATION] Error in notification flow: {e}")
                                            print(f"⚠️ [NOTIFICATION] Payment processing continues despite notification failure")
                                            import traceback
                                            traceback.print_exc()

                                        print(f"")

                                    else:
                                        print(f"❌ [ORCHESTRATION] Failed to enqueue to GCWebhook1")
                                        print(f"⚠️ [ORCHESTRATION] Payment validated but not queued for processing!")

                                except Exception as e:
                                    print(f"❌ [ORCHESTRATION] Error queuing to GCWebhook1: {e}")
                                    import traceback
                                    traceback.print_exc()
                        else:
                            print(f"⚠️ [ORCHESTRATION] Could not fetch subscription data for GCWebhook1 triggering")

        except Exception as e:
            print(f"❌ [DATABASE] Failed to update outcome_amount_usd: {e}")
            import traceback
            traceback.print_exc()

    print(f"")
    print(f"✅ [IPN] IPN processed successfully")
    print(f"🎯 [IPN] payment_id {payment_data['payment_id']} stored in database")
    print(f"=" * 80)
    print(f"")
    return jsonify({"status": "success", "message": "IPN processed"}), 200


# ============================================================================
# PAYMENT STATUS API ENDPOINT (FOR LANDING PAGE POLLING)
# ============================================================================

@app.route('/api/payment-status', methods=['GET'])
def payment_status_api():
    """
    API endpoint for landing page to poll payment confirmation status.

    Query Parameters:
        order_id (str): NowPayments order_id (format: PGP-{user_id}|{open_channel_id})

    Returns:
        JSON: {
            "status": "pending" | "confirmed" | "error",
            "message": "descriptive message",
            "data": {
                "order_id": str,
                "payment_status": str,
                "confirmed": bool
            }
        }
    """
    print(f"")
    print(f"=" * 80)
    print(f"📡 [API] Payment Status Request Received")
    print(f"=" * 80)

    # Get order_id from query parameters
    order_id = request.args.get('order_id')

    if not order_id:
        print(f"❌ [API] Missing order_id parameter")
        return jsonify({
            "status": "error",
            "message": "Missing order_id parameter",
            "data": None
        }), 400

    print(f"🔍 [API] Looking up payment status for order_id: {order_id}")

    try:
        # Parse order_id to get user_id and open_channel_id
        user_id, open_channel_id = parse_order_id(order_id)

        if not user_id or not open_channel_id:
            print(f"❌ [API] Invalid order_id format: {order_id}")
            return jsonify({
                "status": "error",
                "message": "Invalid order_id format",
                "data": None
            }), 400

        print(f"✅ [API] Parsed order_id:")
        print(f"   User ID: {user_id}")
        print(f"   Open Channel ID: {open_channel_id}")

        # Connect to database
        conn = get_db_connection()
        if not conn:
            print(f"❌ [API] Failed to connect to database")
            return jsonify({
                "status": "error",
                "message": "Database connection failed",
                "data": None
            }), 500

        cur = conn.cursor()

        # Look up closed_channel_id from main_clients_database
        cur.execute("""
            SELECT closed_channel_id
            FROM main_clients_database
            WHERE open_channel_id = %s
        """, (open_channel_id,))

        result = cur.fetchone()

        if not result:
            print(f"❌ [API] No channel mapping found for open_channel_id: {open_channel_id}")
            cur.close()
            conn.close()
            return jsonify({
                "status": "error",
                "message": "Channel not found",
                "data": None
            }), 404

        closed_channel_id = result[0]
        print(f"✅ [API] Found closed_channel_id: {closed_channel_id}")

        # Query payment_status from private_channel_users_database
        cur.execute("""
            SELECT payment_status, nowpayments_payment_id, nowpayments_payment_status
            FROM private_channel_users_database
            WHERE user_id = %s AND private_channel_id = %s
            ORDER BY id DESC LIMIT 1
        """, (user_id, closed_channel_id))

        payment_record = cur.fetchone()

        cur.close()
        conn.close()

        if not payment_record:
            print(f"⚠️ [API] No payment record found")
            print(f"   User ID: {user_id}")
            print(f"   Private Channel ID: {closed_channel_id}")
            return jsonify({
                "status": "pending",
                "message": "Payment record not found - still pending",
                "data": {
                    "order_id": order_id,
                    "payment_status": "pending",
                    "confirmed": False
                }
            }), 200

        payment_status = payment_record[0] or 'pending'
        nowpayments_payment_id = payment_record[1]
        nowpayments_payment_status = payment_record[2]

        print(f"✅ [API] Found payment record:")
        print(f"   Payment Status: {payment_status}")
        print(f"   NowPayments Payment ID: {nowpayments_payment_id}")
        print(f"   NowPayments Status: {nowpayments_payment_status}")

        # Determine response based on payment_status
        if payment_status == 'confirmed':
            print(f"✅ [API] Payment CONFIRMED - IPN validated")
            return jsonify({
                "status": "confirmed",
                "message": "Payment confirmed - redirecting to Telegram",
                "data": {
                    "order_id": order_id,
                    "payment_status": payment_status,
                    "confirmed": True,
                    "payment_id": nowpayments_payment_id
                }
            }), 200
        elif payment_status == 'failed':
            print(f"❌ [API] Payment FAILED")
            return jsonify({
                "status": "failed",
                "message": "Payment failed",
                "data": {
                    "order_id": order_id,
                    "payment_status": payment_status,
                    "confirmed": False
                }
            }), 200
        else:
            print(f"⏳ [API] Payment PENDING - IPN not yet received")
            return jsonify({
                "status": "pending",
                "message": "Payment pending - waiting for confirmation",
                "data": {
                    "order_id": order_id,
                    "payment_status": payment_status,
                    "confirmed": False
                }
            }), 200

    except Exception as e:
        print(f"❌ [API] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": f"Internal server error: {str(e)}",
            "data": None
        }), 500


# ============================================================================
# PAYMENT PROCESSING PAGE - Serve static HTML
# ============================================================================

@app.route('/payment-processing', methods=['GET'])
def payment_processing_page():
    """
    Serve the payment processing page.

    This page polls /api/payment-status to check if payment is confirmed.
    By serving it from the same origin as the API, we eliminate CORS complexity
    and avoid hardcoding URLs (uses window.location.origin).
    """
    try:
        # Read the HTML file
        with open('payment-processing.html', 'r') as f:
            html_content = f.read()

        return html_content, 200, {'Content-Type': 'text/html; charset=utf-8'}
    except Exception as e:
        print(f"❌ [PAGE] Failed to serve payment-processing.html: {e}")
        return jsonify({"error": "Failed to load payment processing page"}), 500


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    status = {
        "service": "np-webhook-10-26 NowPayments IPN Handler",
        "status": "healthy",
        "components": {
            "ipn_secret": "configured" if NOWPAYMENTS_IPN_SECRET else "missing",
            "database_credentials": "configured" if all([CLOUD_SQL_CONNECTION_NAME, DATABASE_NAME, DATABASE_USER, DATABASE_PASSWORD]) else "missing",
            "connector": "initialized" if connector else "not_initialized"
        }
    }

    http_status = 200 if all([
        NOWPAYMENTS_IPN_SECRET,
        CLOUD_SQL_CONNECTION_NAME,
        DATABASE_NAME,
        DATABASE_USER,
        DATABASE_PASSWORD,
        connector
    ]) else 503

    return jsonify(status), http_status


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    print(f"🌐 [APP] Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port)
