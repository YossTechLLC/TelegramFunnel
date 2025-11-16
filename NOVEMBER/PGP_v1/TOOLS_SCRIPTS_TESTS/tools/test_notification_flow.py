#!/usr/bin/env python3
"""
Test notification flow by:
1. Querying notification settings for a channel
2. Sending test IPN to trigger notification
"""
import os
import sys
import hmac
import hashlib
import json
import requests
from datetime import datetime
from google.cloud.sql.connector import Connector
from sqlalchemy import create_engine, text, pool

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configuration
PROJECT_ID = "pgp-live"
INSTANCE_CONNECTION_NAME = "pgp-live:us-central1:pgp-telepaypsql"
DB_USER = "postgres"
DB_NAME = "client_table"
TEST_CHANNEL_ID = "-1003202734748"

# Service URLs
NP_WEBHOOK_URL = "https://PGP_NP_IPN_v1-291176869049.us-central1.run.app"

def get_database_connection():
    """Initialize database connection with SQLAlchemy"""
    connector = Connector()

    def getconn():
        return connector.connect(
            INSTANCE_CONNECTION_NAME,
            "pg8000",
            user=DB_USER,
            password=os.getenv("DB_PASSWORD"),
            db=DB_NAME
        )

    engine = create_engine(
        "postgresql+pg8000://",
        creator=getconn,
        poolclass=pool.NullPool
    )

    return engine

def check_notification_settings(engine, open_channel_id):
    """Check if notifications are enabled for a channel"""
    print(f"\n🔍 [QUERY] Checking notification settings for channel: {open_channel_id}")

    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT
                    open_channel_id,
                    closed_channel_id,
                    open_channel_title,
                    closed_channel_title,
                    notification_status,
                    notification_id,
                    sub_1_price,
                    sub_1_time
                FROM main_clients_database
                WHERE open_channel_id = :open_channel_id
            """),
            {"open_channel_id": str(open_channel_id)}
        )

        row = result.fetchone()

        if not row:
            print(f"❌ [ERROR] Channel {open_channel_id} not found in database")
            return None

        channel_data = {
            "open_channel_id": row[0],
            "closed_channel_id": row[1],
            "open_channel_title": row[2],
            "closed_channel_title": row[3],
            "notification_status": row[4],
            "notification_id": row[5],
            "sub_1_price": float(row[6]) if row[6] else None,
            "sub_1_time": int(row[7]) if row[7] else None
        }

        print(f"\n📋 [RESULT] Channel Details:")
        print(f"   Open Channel: {channel_data['open_channel_id']} - {channel_data['open_channel_title']}")
        print(f"   Closed Channel: {channel_data['closed_channel_id']} - {channel_data['closed_channel_title']}")
        print(f"   Notification Status: {'✅ ENABLED' if channel_data['notification_status'] else '❌ DISABLED'}")
        print(f"   Notification ID: {channel_data['notification_id']}")
        print(f"   Tier 1: ${channel_data['sub_1_price']} USD for {channel_data['sub_1_time']} days")

        return channel_data

def create_test_ipn_payload(channel_data):
    """Create a test IPN payload mimicking NowPayments"""
    # Use a test user ID
    test_user_id = 6271402111  # Example test user

    # Create order_id in expected format: PGP-{user_id}|{open_channel_id}
    order_id = f"PGP-{test_user_id}|{channel_data['open_channel_id']}"

    # Generate numeric payment_id (timestamp-based, 10 digits like NowPayments)
    # Use timestamp in seconds to create a unique numeric ID
    import time
    payment_id = str(int(time.time()))  # e.g., "1731589962"

    # Subscription payment payload
    payload = {
        "payment_id": payment_id,  # Numeric string
        "invoice_id": f"INV_{payment_id}",  # Invoice ID with prefix
        "order_id": order_id,
        "payment_status": "finished",  # Critical: must be 'finished' to trigger notification
        "pay_address": "0x742d35Cc6634C0532925a3b844C6C4C",  # Test address
        "pay_amount": "0.00034",
        "pay_currency": "ETH",
        "outcome_amount": "0.00034",
        "outcome_currency": "ETH",
        "price_amount": str(channel_data['sub_1_price']),
        "price_currency": "USD",
        "created_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        # Subscription-specific fields
        "subscription_price": channel_data['sub_1_price'],
        "subscription_time_days": channel_data['sub_1_time']
    }

    return payload

def calculate_ipn_signature(payload_json, ipn_secret):
    """Calculate HMAC-SHA512 signature for IPN payload"""
    signature = hmac.new(
        ipn_secret.encode('utf-8'),
        payload_json.encode('utf-8'),
        hashlib.sha512
    ).hexdigest()
    return signature

def send_test_ipn(payload, ipn_secret=None):
    """Send test IPN to np-webhook"""
    print(f"\n📤 [IPN] Preparing to send test IPN...")
    print(f"   Target: {NP_WEBHOOK_URL}")
    print(f"   Order ID: {payload['order_id']}")
    print(f"   Payment Status: {payload['payment_status']}")

    # Convert payload to JSON
    payload_json = json.dumps(payload, sort_keys=True)

    headers = {
        "Content-Type": "application/json"
    }

    # Add signature if IPN secret is provided
    if ipn_secret:
        signature = calculate_ipn_signature(payload_json, ipn_secret)
        headers["x-nowpayments-sig"] = signature
        print(f"   Signature: {signature[:20]}...")
    else:
        print(f"   ⚠️  Warning: No IPN secret provided, signature verification may fail")

    # Send POST request
    try:
        print(f"\n🚀 [IPN] Sending POST request...")
        response = requests.post(
            NP_WEBHOOK_URL,
            data=payload_json,
            headers=headers,
            timeout=30
        )

        print(f"\n📬 [RESPONSE] Status Code: {response.status_code}")
        print(f"   Response Body:")

        try:
            response_data = response.json()
            print(json.dumps(response_data, indent=2))
        except:
            print(response.text)

        return response

    except requests.exceptions.Timeout:
        print(f"❌ [ERROR] Request timeout (30s)")
        return None
    except requests.exceptions.ConnectionError as e:
        print(f"❌ [ERROR] Connection error: {e}")
        return None
    except Exception as e:
        print(f"❌ [ERROR] Unexpected error: {e}")
        return None

def main():
    """Main test flow"""
    print("=" * 80)
    print("🧪 NOTIFICATION FLOW TEST")
    print("=" * 80)

    # Check for database password
    db_password = os.getenv("DB_PASSWORD")
    if not db_password:
        print("❌ [ERROR] DB_PASSWORD environment variable not set")
        print("   Usage: DB_PASSWORD='your_password' python test_notification_flow.py")
        sys.exit(1)

    try:
        # Step 1: Connect to database
        print("\n📊 [DATABASE] Connecting to Cloud SQL...")
        engine = get_database_connection()
        print("✅ [DATABASE] Connected successfully")

        # Step 2: Check notification settings
        channel_data = check_notification_settings(engine, TEST_CHANNEL_ID)

        if not channel_data:
            sys.exit(1)

        # Check if notifications are enabled
        if not channel_data['notification_status']:
            print(f"\n⚠️  [WARNING] Notifications are DISABLED for this channel")
            print(f"   No notification will be sent even if IPN is processed successfully")
            print(f"   Continuing anyway for testing...")

        if not channel_data['notification_id']:
            print(f"\n⚠️  [WARNING] No notification_id set for this channel")
            print(f"   Cannot send notification without a Telegram user ID")
            sys.exit(1)

        # Step 3: Create test IPN payload
        print(f"\n🛠️  [BUILD] Creating test IPN payload...")
        test_payload = create_test_ipn_payload(channel_data)

        print(f"\n📋 [PAYLOAD] Test IPN:")
        print(json.dumps(test_payload, indent=2))

        # Step 4: Get IPN secret (optional)
        ipn_secret = os.getenv("NOWPAYMENTS_IPN_SECRET")
        if not ipn_secret:
            print(f"\n⚠️  [WARNING] NOWPAYMENTS_IPN_SECRET not set")
            print(f"   IPN signature verification will fail")
            print(f"   Continuing without signature for testing...")

        # Step 5: Send test IPN
        response = send_test_ipn(test_payload, ipn_secret)

        if response and response.status_code == 200:
            print(f"\n✅ [SUCCESS] IPN sent successfully!")
            print(f"\n📬 [NEXT STEPS]")
            print(f"   1. Check np-webhook logs:")
            print(f"      gcloud logging read 'resource.labels.service_name=\"PGP_NP_IPN_v1\"' --limit 20")
            print(f"   2. Check PGP_NOTIFICATIONS logs:")
            print(f"      gcloud logging read 'resource.labels.service_name=\"pgp_notificationservice-10-26\"' --limit 20")
            print(f"   3. Check if notification was sent to Telegram user {channel_data['notification_id']}")
        else:
            print(f"\n❌ [FAILED] IPN request failed")

    except Exception as e:
        print(f"\n❌ [ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n" + "=" * 80)
    print("🏁 TEST COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()
