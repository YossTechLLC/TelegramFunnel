#!/usr/bin/env python3
"""
Database migration script for NowPayments payment_id storage.

This migration adds columns to store NowPayments payment data for fee reconciliation
and payment tracking.

Tables Modified:
1. private_channel_users_database - Adds 10 NowPayments tracking columns
2. payout_accumulation - Adds 5 NowPayments tracking columns

Run this BEFORE deploying service updates.

Usage:
    python3 execute_payment_id_migration.py
"""
import os
import sys
import subprocess
from google.cloud.sql.connector import Connector


def get_secret(secret_name):
    """Get secret from Google Cloud Secret Manager."""
    try:
        result = subprocess.run(
            ['gcloud', 'secrets', 'versions', 'access', 'latest', '--secret', secret_name],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to get secret {secret_name}: {e}")
        sys.exit(1)


def execute_migration():
    """Execute database schema migration."""
    print("=" * 80)
    print("🚀 NOWPAYMENTS PAYMENT_ID MIGRATION")
    print("=" * 80)
    print()

    # Get database credentials from Secret Manager
    print("📋 Step 1: Retrieving database credentials from Secret Manager...")
    instance_connection_name = get_secret('CLOUD_SQL_CONNECTION_NAME')
    db_name = get_secret('DATABASE_NAME_SECRET')
    db_user = get_secret('DATABASE_USER_SECRET')
    db_password = get_secret('DATABASE_PASSWORD_SECRET')

    print(f"   ✅ Instance: {instance_connection_name}")
    print(f"   ✅ Database: {db_name}")
    print(f"   ✅ User: {db_user}")
    print()

    # Initialize Cloud SQL Connector
    print("📋 Step 2: Connecting to Cloud SQL...")
    connector = Connector()

    try:
        conn = connector.connect(
            instance_connection_name,
            "pg8000",
            user=db_user,
            password=db_password,
            db=db_name
        )
        print("   ✅ Connected successfully")
        print()
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        sys.exit(1)

    cursor = conn.cursor()

    print("📋 Step 3: Executing migration SQL...")
    print()

    # Migration SQL - using IF NOT EXISTS for idempotency
    migration_sql = """
    -- ============================================================================
    -- PRIVATE_CHANNEL_USERS_DATABASE MODIFICATIONS
    -- ============================================================================

    -- Add NowPayments tracking columns
    ALTER TABLE private_channel_users_database
    ADD COLUMN IF NOT EXISTS nowpayments_payment_id VARCHAR(50);

    ALTER TABLE private_channel_users_database
    ADD COLUMN IF NOT EXISTS nowpayments_invoice_id VARCHAR(50);

    ALTER TABLE private_channel_users_database
    ADD COLUMN IF NOT EXISTS nowpayments_order_id VARCHAR(100);

    ALTER TABLE private_channel_users_database
    ADD COLUMN IF NOT EXISTS nowpayments_pay_address VARCHAR(255);

    ALTER TABLE private_channel_users_database
    ADD COLUMN IF NOT EXISTS nowpayments_payment_status VARCHAR(50);

    ALTER TABLE private_channel_users_database
    ADD COLUMN IF NOT EXISTS nowpayments_pay_amount DECIMAL(30, 18);

    ALTER TABLE private_channel_users_database
    ADD COLUMN IF NOT EXISTS nowpayments_pay_currency VARCHAR(20);

    ALTER TABLE private_channel_users_database
    ADD COLUMN IF NOT EXISTS nowpayments_outcome_amount DECIMAL(30, 18);

    ALTER TABLE private_channel_users_database
    ADD COLUMN IF NOT EXISTS nowpayments_created_at TIMESTAMP;

    ALTER TABLE private_channel_users_database
    ADD COLUMN IF NOT EXISTS nowpayments_updated_at TIMESTAMP;

    -- Create indexes for fast lookups
    CREATE INDEX IF NOT EXISTS idx_nowpayments_payment_id
    ON private_channel_users_database(nowpayments_payment_id);

    CREATE INDEX IF NOT EXISTS idx_nowpayments_order_id
    ON private_channel_users_database(nowpayments_order_id);

    -- ============================================================================
    -- PAYOUT_ACCUMULATION MODIFICATIONS
    -- ============================================================================

    -- Add NowPayments tracking columns
    ALTER TABLE payout_accumulation
    ADD COLUMN IF NOT EXISTS nowpayments_payment_id VARCHAR(50);

    ALTER TABLE payout_accumulation
    ADD COLUMN IF NOT EXISTS nowpayments_pay_address VARCHAR(255);

    ALTER TABLE payout_accumulation
    ADD COLUMN IF NOT EXISTS nowpayments_outcome_amount DECIMAL(30, 18);

    ALTER TABLE payout_accumulation
    ADD COLUMN IF NOT EXISTS nowpayments_network_fee DECIMAL(30, 18);

    ALTER TABLE payout_accumulation
    ADD COLUMN IF NOT EXISTS payment_fee_usd DECIMAL(20, 8);

    -- Create indexes for payment_id lookup and blockchain matching
    CREATE INDEX IF NOT EXISTS idx_payout_nowpayments_payment_id
    ON payout_accumulation(nowpayments_payment_id);

    CREATE INDEX IF NOT EXISTS idx_payout_pay_address
    ON payout_accumulation(nowpayments_pay_address);
    """

    try:
        # Execute migration
        cursor.execute(migration_sql)
        conn.commit()
        print("   ✅ Migration SQL executed successfully")
        print()
    except Exception as e:
        print(f"   ❌ Migration failed: {e}")
        conn.rollback()
        cursor.close()
        conn.close()
        connector.close()
        sys.exit(1)

    print("📋 Step 4: Verifying migration results...")
    print()

    # Verify columns exist in private_channel_users_database
    print("   🔍 Checking private_channel_users_database columns...")
    cursor.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'private_channel_users_database'
        AND column_name LIKE 'nowpayments_%'
        ORDER BY column_name;
    """)

    pcud_columns = cursor.fetchall()
    print(f"   ✅ Found {len(pcud_columns)} NowPayments columns:")
    for col in pcud_columns:
        print(f"      - {col[0]:35s} ({col[1]})")
    print()

    # Verify indexes in private_channel_users_database
    print("   🔍 Checking private_channel_users_database indexes...")
    cursor.execute("""
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE tablename = 'private_channel_users_database'
        AND indexname LIKE 'idx_nowpayments_%'
        ORDER BY indexname;
    """)

    pcud_indexes = cursor.fetchall()
    print(f"   ✅ Found {len(pcud_indexes)} NowPayments indexes:")
    for idx in pcud_indexes:
        print(f"      - {idx[0]}")
    print()

    # Verify columns exist in payout_accumulation
    print("   🔍 Checking payout_accumulation columns...")
    cursor.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'payout_accumulation'
        AND (column_name LIKE 'nowpayments_%' OR column_name = 'payment_fee_usd')
        ORDER BY column_name;
    """)

    pa_columns = cursor.fetchall()
    print(f"   ✅ Found {len(pa_columns)} NowPayments/fee columns:")
    for col in pa_columns:
        print(f"      - {col[0]:35s} ({col[1]})")
    print()

    # Verify indexes in payout_accumulation
    print("   🔍 Checking payout_accumulation indexes...")
    cursor.execute("""
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE tablename = 'payout_accumulation'
        AND (indexname LIKE 'idx_payout_nowpayments_%' OR indexname LIKE 'idx_payout_pay_address%')
        ORDER BY indexname;
    """)

    pa_indexes = cursor.fetchall()
    print(f"   ✅ Found {len(pa_indexes)} NowPayments indexes:")
    for idx in pa_indexes:
        print(f"      - {idx[0]}")
    print()

    # Final validation
    print("📋 Step 5: Final validation...")
    print()

    expected_pcud_columns = 10
    expected_pcud_indexes = 2
    expected_pa_columns = 5
    expected_pa_indexes = 2

    validation_passed = True

    if len(pcud_columns) != expected_pcud_columns:
        print(f"   ❌ Expected {expected_pcud_columns} columns in private_channel_users_database, found {len(pcud_columns)}")
        validation_passed = False
    else:
        print(f"   ✅ private_channel_users_database: {len(pcud_columns)}/{expected_pcud_columns} columns")

    if len(pcud_indexes) != expected_pcud_indexes:
        print(f"   ❌ Expected {expected_pcud_indexes} indexes in private_channel_users_database, found {len(pcud_indexes)}")
        validation_passed = False
    else:
        print(f"   ✅ private_channel_users_database: {len(pcud_indexes)}/{expected_pcud_indexes} indexes")

    if len(pa_columns) != expected_pa_columns:
        print(f"   ❌ Expected {expected_pa_columns} columns in payout_accumulation, found {len(pa_columns)}")
        validation_passed = False
    else:
        print(f"   ✅ payout_accumulation: {len(pa_columns)}/{expected_pa_columns} columns")

    if len(pa_indexes) != expected_pa_indexes:
        print(f"   ❌ Expected {expected_pa_indexes} indexes in payout_accumulation, found {len(pa_indexes)}")
        validation_passed = False
    else:
        print(f"   ✅ payout_accumulation: {len(pa_indexes)}/{expected_pa_indexes} indexes")

    print()

    # Cleanup
    cursor.close()
    conn.close()
    connector.close()

    # Final report
    print("=" * 80)
    if validation_passed:
        print("✅ MIGRATION COMPLETED SUCCESSFULLY")
        print("=" * 80)
        print()
        print("Next steps:")
        print("1. Deploy GCWebhook1 with IPN endpoint")
        print("2. Configure NOWPAYMENTS_IPN_SECRET in Secret Manager")
        print("3. Update TelePay bot with ipn_callback_url")
        print()
        return 0
    else:
        print("⚠️  MIGRATION COMPLETED WITH WARNINGS")
        print("=" * 80)
        print()
        print("Please review the validation errors above.")
        print()
        return 1


if __name__ == "__main__":
    try:
        exit_code = execute_migration()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n❌ Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
