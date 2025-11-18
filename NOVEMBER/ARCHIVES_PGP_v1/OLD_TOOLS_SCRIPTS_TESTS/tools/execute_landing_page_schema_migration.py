#!/usr/bin/env python3
"""
Database Migration: Add payment_status for Landing Page Polling
Date: 2025-11-02
Purpose: Enable landing page to poll payment confirmation status via API

Changes:
1. Add payment_status column to private_channel_users_database
2. Create index on (order_id, payment_status) for fast lookups
3. Backfill existing records with 'confirmed' status if payment_id exists
"""

import os
import sys
from google.cloud.sql.connector import Connector
import pg8000
from google.cloud import secretmanager

def get_secret(secret_id):
    """Fetch secret from Secret Manager"""
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/pgp-live/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode('UTF-8')

def get_db_connection():
    """Create database connection using Cloud SQL Connector"""
    connector = Connector()

    # Get credentials from Secret Manager
    connection_name = get_secret("CLOUD_SQL_CONNECTION_NAME")
    db_name = get_secret("DATABASE_NAME_SECRET")
    db_user = get_secret("DATABASE_USER_SECRET")
    db_password = get_secret("DATABASE_PASSWORD_SECRET")

    conn = connector.connect(
        connection_name,
        "pg8000",
        user=db_user,
        password=db_password,
        db=db_name
    )
    return conn

def execute_migration():
    """Execute the landing page schema migration"""

    print("=" * 80)
    print("🚀 [MIGRATION] Starting Landing Page Schema Migration")
    print("=" * 80)

    try:
        # Connect to database
        print("\n📊 [CONNECT] Connecting to telepaydb...")
        conn = get_db_connection()
        conn.autocommit = False
        cur = conn.cursor()

        print("✅ [CONNECT] Connected successfully")

        # ========================================================================
        # Step 1: Add payment_status column
        # ========================================================================
        print("\n" + "=" * 80)
        print("📝 [STEP 1] Adding payment_status column to private_channel_users_database")
        print("=" * 80)

        cur.execute("""
            ALTER TABLE private_channel_users_database
            ADD COLUMN IF NOT EXISTS payment_status VARCHAR(20) DEFAULT 'pending';
        """)

        print("✅ [STEP 1] payment_status column added successfully")

        # Add comment
        cur.execute("""
            COMMENT ON COLUMN private_channel_users_database.payment_status IS
              'Payment confirmation status: pending (initial) | confirmed (IPN validated) | failed (payment failed)';
        """)

        print("✅ [STEP 1] Column comment added")

        # ========================================================================
        # Step 2: Create index on (order_id, payment_status)
        # ========================================================================
        print("\n" + "=" * 80)
        print("📝 [STEP 2] Creating index idx_order_id_status")
        print("=" * 80)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_nowpayments_order_id_status
            ON private_channel_users_database(nowpayments_order_id, payment_status);
        """)

        print("✅ [STEP 2] Index idx_nowpayments_order_id_status created successfully")

        # Add comment
        cur.execute("""
            COMMENT ON INDEX idx_nowpayments_order_id_status IS
              'Composite index for fast payment status lookups by nowpayments_order_id';
        """)

        print("✅ [STEP 2] Index comment added")

        # ========================================================================
        # Step 3: Backfill existing records
        # ========================================================================
        print("\n" + "=" * 80)
        print("📝 [STEP 3] Backfilling payment_status for existing records")
        print("=" * 80)

        # Update existing records with payment_id as confirmed
        cur.execute("""
            UPDATE private_channel_users_database
            SET payment_status = 'confirmed'
            WHERE nowpayments_payment_id IS NOT NULL
              AND payment_status = 'pending';
        """)

        backfilled_count = cur.rowcount
        print(f"✅ [STEP 3] Backfilled {backfilled_count} records with 'confirmed' status")

        # ========================================================================
        # Step 4: Verification
        # ========================================================================
        print("\n" + "=" * 80)
        print("📝 [STEP 4] Verifying migration")
        print("=" * 80)

        # Verify column exists
        cur.execute("""
            SELECT column_name, data_type, column_default
            FROM information_schema.columns
            WHERE table_name = 'private_channel_users_database'
              AND column_name = 'payment_status';
        """)

        column_info = cur.fetchone()
        if column_info:
            print(f"✅ [VERIFY] Column 'payment_status' exists:")
            print(f"   - Type: {column_info[1]}")
            print(f"   - Default: {column_info[2]}")
        else:
            raise Exception("❌ Column 'payment_status' not found after migration!")

        # Verify index exists
        cur.execute("""
            SELECT indexname
            FROM pg_indexes
            WHERE tablename = 'private_channel_users_database'
              AND indexname = 'idx_nowpayments_order_id_status';
        """)

        index_info = cur.fetchone()
        if index_info:
            print(f"✅ [VERIFY] Index 'idx_nowpayments_order_id_status' exists")
        else:
            raise Exception("❌ Index 'idx_nowpayments_order_id_status' not found after migration!")

        # Get statistics
        cur.execute("""
            SELECT
                COUNT(*) as total_records,
                COUNT(CASE WHEN payment_status = 'confirmed' THEN 1 END) as confirmed,
                COUNT(CASE WHEN payment_status = 'pending' THEN 1 END) as pending
            FROM private_channel_users_database;
        """)

        stats = cur.fetchone()
        print(f"\n📊 [STATS] Migration Statistics:")
        print(f"   - Total Records: {stats[0]}")
        print(f"   - Confirmed: {stats[1]}")
        print(f"   - Pending: {stats[2]}")

        # ========================================================================
        # Commit transaction
        # ========================================================================
        print("\n" + "=" * 80)
        print("💾 [COMMIT] Committing transaction...")
        print("=" * 80)

        conn.commit()

        print("✅ [COMMIT] Transaction committed successfully")

        # Close connection
        cur.close()
        conn.close()

        print("\n" + "=" * 80)
        print("✅ [SUCCESS] Landing Page Schema Migration Completed")
        print("=" * 80)
        print("\n📋 [SUMMARY] Changes Applied:")
        print("   1. ✅ Added payment_status column (VARCHAR(20), DEFAULT 'pending')")
        print("   2. ✅ Created idx_nowpayments_order_id_status index")
        print(f"   3. ✅ Backfilled {backfilled_count} existing records")
        print(f"   4. ✅ Verified schema changes")
        print("\n🎯 [NEXT STEPS]:")
        print("   - Update np-webhook to set payment_status='confirmed' on IPN")
        print("   - Add /api/payment-status endpoint to np-webhook")
        print("   - Deploy static landing page to Cloud Storage")

        return True

    except Exception as e:
        print(f"\n❌ [ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()

        if 'conn' in locals():
            print("\n🔄 [ROLLBACK] Rolling back transaction...")
            conn.rollback()
            print("✅ [ROLLBACK] Transaction rolled back")

        return False

if __name__ == "__main__":
    success = execute_migration()
    sys.exit(0 if success else 1)
