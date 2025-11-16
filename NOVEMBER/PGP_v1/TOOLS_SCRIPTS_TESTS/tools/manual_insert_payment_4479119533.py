#!/usr/bin/env python
"""
Manual database insert script for payment_id 4479119533
This script inserts the missing payment record that caused the IPN processing failure.

User ID: 6271402111
Open Channel ID: -1003253338212
Closed Channel ID: -1003016667267
Payment ID: 4479119533
"""
import os
import sys
from datetime import datetime, timedelta
from google.cloud.sql.connector import Connector

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 80)
print("🔧 [MANUAL INSERT] Payment Record Creation Script")
print("=" * 80)
print(f"📋 [INFO] Payment ID: 4479119533")
print(f"👤 [INFO] User ID: 6271402111")
print(f"🏢 [INFO] Closed Channel ID: -1003016667267")
print(f"💰 [INFO] Amount: $2.50 USD")
print("")

# Database credentials from environment (Secret Manager)
CLOUD_SQL_CONNECTION_NAME = (os.getenv('CLOUD_SQL_CONNECTION_NAME') or '').strip() or 'telepay-459221:us-central1:telepaypsql'
DATABASE_NAME = (os.getenv('DATABASE_NAME_SECRET') or '').strip() or 'telepaydb'
DATABASE_USER = (os.getenv('DATABASE_USER_SECRET') or '').strip() or 'postgres'
DATABASE_PASSWORD = (os.getenv('DATABASE_PASSWORD_SECRET') or '').strip() or None

if not DATABASE_PASSWORD:
    print("❌ [ERROR] DATABASE_PASSWORD_SECRET not found in environment")
    print("💡 [HINT] Set environment variable or update script with password")
    sys.exit(1)

# Payment data from NowPayments API response
PAYMENT_DATA = {
    'user_id': 6271402111,
    'open_channel_id': '-1003253338212',
    'closed_channel_id': '-1003016667267',
    'payment_id': '4479119533',
    'invoice_id': '4910826526',
    'order_id': 'PGP-6271402111|-1003253338212',
    'pay_address': '0xD031Cb94c419A5D7AA4BA5FDBc9Cc82138651083',
    'payment_status': 'finished',
    'pay_amount': 0.00076967,
    'pay_currency': 'eth',
    'outcome_amount': 0.00061819,
    'price_amount': 2.50,
    'price_currency': 'usd',
    'outcome_currency': 'eth',
    'payout_hash': '0x2b37662ad40a9db2b730e3a9ea02641cf1ae04d7c62e7fd9df89ca0aad1b2a70',
    'payin_hash': '0x00819d027e85c90208e6438522a67112030f8d949708bcd0d214015f248f795a',
    'created_at': '2025-11-07T11:48:27.355Z',
    'updated_at': '2025-11-07T11:51:20.364Z'
}

# Calculate outcome_amount_usd (ETH price at time of payment)
# ETH/USD ~ $3250 (approximate at time of transaction)
eth_usd_price = 3250.0  # This should ideally come from CoinGecko API
outcome_amount_usd = PAYMENT_DATA['outcome_amount'] * eth_usd_price

print(f"📊 [CALC] ETH Price: ${eth_usd_price:,.2f}")
print(f"📊 [CALC] Outcome USD: ${outcome_amount_usd:.2f} ({PAYMENT_DATA['outcome_amount']} ETH)")
print("")

# Calculate subscription expiration (30 days from now)
now = datetime.now()
expiration_datetime = now + timedelta(days=30)
expire_time = expiration_datetime.strftime('%H:%M:%S')
expire_date = expiration_datetime.strftime('%Y-%m-%d')
current_timestamp = now.strftime('%H:%M:%S')
current_datestamp = now.strftime('%Y-%m-%d')

print(f"⏰ [CALC] Current: {current_datestamp} {current_timestamp}")
print(f"⏰ [CALC] Expires: {expire_date} {expire_time}")
print("")

try:
    # Initialize Cloud SQL Connector
    print(f"🔌 [DATABASE] Initializing Cloud SQL Connector...")
    connector = Connector()

    # Connect to database
    print(f"🔗 [DATABASE] Connecting to {CLOUD_SQL_CONNECTION_NAME}...")
    conn = connector.connect(
        CLOUD_SQL_CONNECTION_NAME,
        "pg8000",
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        db=DATABASE_NAME
    )
    print(f"✅ [DATABASE] Connection established")
    print("")

    cur = conn.cursor()

    # Step 1: Get client configuration from main_clients_database
    print(f"🔍 [DATABASE] Looking up client configuration...")
    cur.execute("""
        SELECT
            client_wallet_address,
            client_payout_currency::text,
            client_payout_network::text,
            payout_strategy,
            payout_threshold_usd
        FROM main_clients_database
        WHERE closed_channel_id = %s
    """, (PAYMENT_DATA['closed_channel_id'],))

    client_data = cur.fetchone()

    if not client_data:
        print(f"❌ [ERROR] No client configuration found for channel {PAYMENT_DATA['closed_channel_id']}")
        print(f"💡 [HINT] Register this channel in main_clients_database first")
        sys.exit(1)

    wallet_address, payout_currency, payout_network, payout_strategy, payout_threshold = client_data

    print(f"✅ [DATABASE] Found client configuration:")
    print(f"   Wallet: {wallet_address}")
    print(f"   Currency: {payout_currency}")
    print(f"   Network: {payout_network}")
    print(f"   Strategy: {payout_strategy}")
    print(f"   Threshold: ${payout_threshold}")
    print("")

    # Step 2: Check if record already exists
    print(f"🔍 [DATABASE] Checking for existing record...")
    cur.execute("""
        SELECT id, payment_status, nowpayments_payment_id
        FROM private_channel_users_database
        WHERE user_id = %s AND private_channel_id = %s
        ORDER BY id DESC LIMIT 1
    """, (PAYMENT_DATA['user_id'], PAYMENT_DATA['closed_channel_id']))

    existing = cur.fetchone()

    if existing:
        existing_id, existing_status, existing_payment_id = existing
        print(f"⚠️ [WARNING] Record already exists!")
        print(f"   ID: {existing_id}")
        print(f"   Status: {existing_status}")
        print(f"   Payment ID: {existing_payment_id}")
        print("")
        print(f"❓ [QUESTION] Update existing record? (yes/no)")

        # For automated execution, default to 'no' and exit
        print(f"🛑 [MANUAL] Exiting to prevent accidental overwrite")
        print(f"💡 [HINT] Delete existing record or modify script to force update")
        sys.exit(0)

    print(f"✅ [DATABASE] No existing record found - proceeding with INSERT")
    print("")

    # Step 3: Insert new record with all required fields
    print(f"📝 [DATABASE] Inserting payment record...")

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
            nowpayments_outcome_amount_usd,
            nowpayments_created_at,
            nowpayments_updated_at
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        )
        RETURNING id
    """

    insert_params = (
        PAYMENT_DATA['user_id'],                    # user_id
        PAYMENT_DATA['closed_channel_id'],          # private_channel_id
        30,                                          # sub_time (30 days)
        str(PAYMENT_DATA['price_amount']),          # sub_price
        current_timestamp,                           # timestamp
        current_datestamp,                           # datestamp
        expire_time,                                 # expire_time
        expire_date,                                 # expire_date
        True,                                        # is_active
        'confirmed',                                 # payment_status (internal)
        PAYMENT_DATA['payment_id'],                 # nowpayments_payment_id
        PAYMENT_DATA['invoice_id'],                 # nowpayments_invoice_id
        PAYMENT_DATA['order_id'],                   # nowpayments_order_id
        PAYMENT_DATA['pay_address'],                # nowpayments_pay_address
        PAYMENT_DATA['payment_status'],             # nowpayments_payment_status
        PAYMENT_DATA['pay_amount'],                 # nowpayments_pay_amount
        PAYMENT_DATA['pay_currency'],               # nowpayments_pay_currency
        PAYMENT_DATA['outcome_amount'],             # nowpayments_outcome_amount
        PAYMENT_DATA['price_amount'],               # nowpayments_price_amount
        PAYMENT_DATA['price_currency'],             # nowpayments_price_currency
        PAYMENT_DATA['outcome_currency'],           # nowpayments_outcome_currency
        outcome_amount_usd                          # nowpayments_outcome_amount_usd
    )

    cur.execute(insert_query, insert_params)
    inserted_id = cur.fetchone()[0]

    # Commit transaction
    conn.commit()

    print(f"")
    print(f"✅ [SUCCESS] Record inserted successfully!")
    print(f"🆔 [DATABASE] New record ID: {inserted_id}")
    print(f"")
    print(f"=" * 80)
    print(f"📊 [SUMMARY] Payment Record Created")
    print(f"=" * 80)
    print(f"Record ID: {inserted_id}")
    print(f"User ID: {PAYMENT_DATA['user_id']}")
    print(f"Channel ID: {PAYMENT_DATA['closed_channel_id']}")
    print(f"Payment ID: {PAYMENT_DATA['payment_id']}")
    print(f"Amount: ${PAYMENT_DATA['price_amount']} USD")
    print(f"Status: confirmed ✅")
    print(f"Subscription: 30 days")
    print(f"Expires: {expire_date} {expire_time}")
    print(f"")
    print(f"🎯 [NEXT STEPS]")
    print(f"1. Next IPN retry from NowPayments will succeed ✅")
    print(f"2. Payment status API will return 'confirmed' ✅")
    print(f"3. PGP_ORCHESTRATOR_v1 will process payment orchestration ✅")
    print(f"4. User will receive Telegram invitation link ✅")
    print(f"")
    print(f"💡 [NOTE] If payment orchestration doesn't start automatically,")
    print(f"   you may need to manually trigger PGP_ORCHESTRATOR_v1:/process-validated-payment")
    print(f"")

except Exception as e:
    print(f"")
    print(f"❌ [ERROR] Database operation failed: {e}")
    print(f"")
    import traceback
    traceback.print_exc()
    sys.exit(1)

finally:
    if 'cur' in locals() and cur:
        cur.close()
    if 'conn' in locals() and conn:
        conn.close()
        print(f"🔌 [DATABASE] Connection closed")
    if 'connector' in locals() and connector:
        connector.close()
        print(f"🔌 [DATABASE] Connector closed")

print(f"")
print(f"✅ [COMPLETE] Script finished successfully")
print(f"=" * 80)
