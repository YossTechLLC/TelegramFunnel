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
from flask import Flask, request, jsonify, abort
from google.cloud.sql.connector import Connector
from typing import Optional

app = Flask(__name__)

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
NOWPAYMENTS_IPN_SECRET = os.getenv('NOWPAYMENTS_IPN_SECRET')
if NOWPAYMENTS_IPN_SECRET:
    print(f"✅ [CONFIG] NOWPAYMENTS_IPN_SECRET loaded")
else:
    print(f"❌ [CONFIG] NOWPAYMENTS_IPN_SECRET not found")
    print(f"⚠️ [CONFIG] IPN signature verification will fail!")

# Database credentials
CLOUD_SQL_CONNECTION_NAME = os.getenv('CLOUD_SQL_CONNECTION_NAME')
DATABASE_NAME = os.getenv('DATABASE_NAME_SECRET')
DATABASE_USER = os.getenv('DATABASE_USER_SECRET')
DATABASE_PASSWORD = os.getenv('DATABASE_PASSWORD_SECRET')

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
    Update private_channel_users_database with NowPayments payment data.

    Two-step process:
    1. Parse order_id to get user_id and open_channel_id
    2. Look up closed_channel_id from main_clients_database using open_channel_id
    3. Update private_channel_users_database using user_id and closed_channel_id (as private_channel_id)

    Args:
        order_id: NowPayments order_id (format: PGP-{user_id}|{open_channel_id})
        payment_data: Dictionary with payment metadata from IPN

    Returns:
        True if update successful, False otherwise
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

        # Step 2: Look up closed_channel_id (private_channel_id) from main_clients_database
        print(f"")
        print(f"🔍 [DATABASE] Looking up channel mapping...")
        print(f"   Searching for open_channel_id: {open_channel_id}")

        cur.execute(
            "SELECT closed_channel_id FROM main_clients_database WHERE open_channel_id = %s",
            (str(open_channel_id),)
        )
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
        print(f"✅ [DATABASE] Found channel mapping:")
        print(f"   Open Channel ID (public): {open_channel_id}")
        print(f"   Closed Channel ID (private): {closed_channel_id}")

        # Step 3: Update private_channel_users_database
        # Note: private_channel_id in this table = closed_channel_id from main_clients_database
        print(f"")
        print(f"🗄️ [DATABASE] Updating subscription record...")
        print(f"   Target table: private_channel_users_database")
        print(f"   WHERE user_id = {user_id} AND private_channel_id = {closed_channel_id}")

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
                nowpayments_created_at = CURRENT_TIMESTAMP,
                nowpayments_updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s AND private_channel_id = %s
            AND id = (
                SELECT id FROM private_channel_users_database
                WHERE user_id = %s AND private_channel_id = %s
                ORDER BY id DESC LIMIT 1
            )
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
            user_id,
            closed_channel_id,  # Use closed_channel_id (not open_channel_id!)
            user_id,
            closed_channel_id
        ))

        conn.commit()
        rows_updated = cur.rowcount

        if rows_updated > 0:
            print(f"")
            print(f"✅ [DATABASE] Successfully updated {rows_updated} record(s)")
            print(f"   User ID: {user_id}")
            print(f"   Private Channel ID: {closed_channel_id}")
            print(f"   Payment ID: {payment_data.get('payment_id')}")
            print(f"   Invoice ID: {payment_data.get('invoice_id')}")
            print(f"   Status: {payment_data.get('payment_status')}")
            print(f"   Amount: {payment_data.get('outcome_amount')} {payment_data.get('pay_currency')}")
            return True
        else:
            print(f"")
            print(f"⚠️ [DATABASE] No records found to update")
            print(f"   User ID: {user_id}")
            print(f"   Private Channel ID: {closed_channel_id}")
            print(f"💡 [HINT] User may not have an active subscription record")
            print(f"💡 [HINT] Check if record exists:")
            print(f"   SELECT * FROM private_channel_users_database")
            print(f"   WHERE user_id = {user_id} AND private_channel_id = {closed_channel_id}")
            print(f"   ORDER BY id DESC LIMIT 1")
            return False

    except Exception as e:
        print(f"")
        print(f"❌ [DATABASE] Update failed with exception: {e}")
        print(f"🔄 [DATABASE] Rolling back transaction...")
        if conn:
            conn.rollback()
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
        print(f"   Outcome Amount: {ipn_data.get('outcome_amount', 'N/A')}")
        print(f"   Pay Address: {ipn_data.get('pay_address', 'N/A')}")

    except Exception as e:
        print(f"❌ [IPN] Failed to parse JSON payload: {e}")
        print(f"=" * 80)
        abort(400, "Invalid JSON payload")

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
        'outcome_amount': ipn_data.get('outcome_amount')
    }

    success = update_payment_data(order_id, payment_data)

    if success:
        print(f"")
        print(f"✅ [IPN] IPN processed successfully")
        print(f"🎯 [IPN] payment_id {payment_data['payment_id']} stored in database")
        print(f"=" * 80)
        print(f"")
        return jsonify({"status": "success", "message": "IPN processed"}), 200
    else:
        print(f"")
        print(f"⚠️ [IPN] Database update failed")
        print(f"🔄 [IPN] Returning 500 - NowPayments will retry")
        print(f"=" * 80)
        print(f"")
        abort(500, "Database update failed")


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
