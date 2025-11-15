#!/usr/bin/env python3
"""
Add price_amount and currency tracking to private_channel_users_database.

This migration adds:
- nowpayments_price_amount: Original USD invoice amount
- nowpayments_price_currency: Original currency (typically USD)
- nowpayments_outcome_currency: Currency of outcome_amount

These fields enable proper USD-to-USD validation instead of comparing
crypto amounts to USD.
"""
import subprocess
from google.cloud.sql.connector import Connector


def get_secret(secret_name):
    """Fetch secret from Google Cloud Secret Manager."""
    result = subprocess.run(
        ['gcloud', 'secrets', 'versions', 'access', 'latest', '--secret', secret_name],
        capture_output=True, text=True
    )
    return result.stdout.strip()


def main():
    print("=" * 80)
    print("PRICE AMOUNT MIGRATION - Add USD tracking fields")
    print("=" * 80)
    print()

    # Get database credentials
    print("📋 [SETUP] Fetching database credentials...")
    instance_connection_name = get_secret('CLOUD_SQL_CONNECTION_NAME')
    db_name = get_secret('DATABASE_NAME_SECRET')
    db_user = get_secret('DATABASE_USER_SECRET')
    db_password = get_secret('DATABASE_PASSWORD_SECRET')
    print(f"✅ [SETUP] Connected to: {instance_connection_name}")
    print()

    # Connect to database
    print("🔌 [DATABASE] Connecting to Cloud SQL...")
    connector = Connector()
    conn = connector.connect(
        instance_connection_name,
        "pg8000",
        user=db_user,
        password=db_password,
        db=db_name
    )
    cursor = conn.cursor()
    print("✅ [DATABASE] Connection established")
    print()

    # Migration SQL
    migration_sql = """
    -- Add price amount and currency fields to private_channel_users_database
    ALTER TABLE private_channel_users_database
    ADD COLUMN IF NOT EXISTS nowpayments_price_amount DECIMAL(20, 8);

    ALTER TABLE private_channel_users_database
    ADD COLUMN IF NOT EXISTS nowpayments_price_currency VARCHAR(10);

    ALTER TABLE private_channel_users_database
    ADD COLUMN IF NOT EXISTS nowpayments_outcome_currency VARCHAR(10);

    -- Add helpful comments
    COMMENT ON COLUMN private_channel_users_database.nowpayments_price_amount IS
      'Original invoice amount from NowPayments (typically in USD) - used for payment validation';

    COMMENT ON COLUMN private_channel_users_database.nowpayments_price_currency IS
      'Original invoice currency (typically USD)';

    COMMENT ON COLUMN private_channel_users_database.nowpayments_outcome_currency IS
      'Currency of outcome_amount field (e.g., eth, usdt, btc)';
    """

    try:
        print("🔄 [MIGRATION] Executing schema changes...")
        cursor.execute(migration_sql)
        conn.commit()
        print("✅ [MIGRATION] Schema updated successfully")
        print()
    except Exception as e:
        print(f"❌ [MIGRATION] Failed: {e}")
        conn.rollback()
        cursor.close()
        conn.close()
        return

    # Verify columns
    print("🔍 [VERIFY] Checking new columns...")
    cursor.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'private_channel_users_database'
        AND (column_name = 'nowpayments_price_amount'
             OR column_name = 'nowpayments_price_currency'
             OR column_name = 'nowpayments_outcome_currency')
        ORDER BY column_name;
    """)

    columns = cursor.fetchall()
    if columns:
        print("✅ [VERIFY] Found new columns:")
        for col in columns:
            print(f"   - {col[0]}: {col[1]} (nullable: {col[2]})")
    else:
        print("❌ [VERIFY] Columns not found!")

    print()
    print("=" * 80)
    print("✅ MIGRATION COMPLETE")
    print("=" * 80)
    print()
    print("Next steps:")
    print("1. Deploy updated PGP_NP_IPN_v1 service")
    print("2. Deploy updated PGP_INVITE_v1 service")
    print("3. Test with new payment")
    print("4. Verify price_amount is captured and validated correctly")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
