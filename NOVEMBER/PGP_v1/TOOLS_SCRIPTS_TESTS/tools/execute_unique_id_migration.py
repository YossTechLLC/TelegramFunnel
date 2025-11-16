#!/usr/bin/env python3
"""
Execute split_payout_hostpay unique_id column extension migration.
Extends VARCHAR(16) to VARCHAR(64) to support batch conversion IDs.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, '/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/PGP_HOSTPAY1_v1')

try:
    from google.cloud.sql.connector import Connector
    print("✅ Cloud SQL Connector imported successfully")
except ImportError as e:
    print(f"❌ Failed to import Cloud SQL Connector: {e}")
    sys.exit(1)

# Database credentials
INSTANCE_CONNECTION_NAME = "telepay-459221:us-central1:telepaypsql"
DB_NAME = "client_table"  # Corrected from "telepaydb"
DB_USER = "postgres"
DB_PASSWORD = "Chigdabeast123$"

def get_connection():
    """Create database connection."""
    connector = Connector()
    conn = connector.connect(
        INSTANCE_CONNECTION_NAME,
        "pg8000",
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME
    )
    return conn

def execute_migration():
    """Execute the unique_id column extension migration."""
    print("=" * 80)
    print("MIGRATION: Extend split_payout_hostpay.unique_id VARCHAR(16) → VARCHAR(64)")
    print("=" * 80)
    print()

    conn = None
    cur = None

    try:
        # Connect to database
        print("📡 Connecting to database...")
        conn = get_connection()
        cur = conn.cursor()
        print("✅ Connected to telepaypsql successfully")
        print()

        # Step 1: Check current schema
        print("📋 Step 1: Checking current schema...")
        cur.execute("""
            SELECT column_name, data_type, character_maximum_length, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'split_payout_hostpay'
              AND column_name = 'unique_id'
        """)

        current_schema = cur.fetchone()
        if current_schema:
            print(f"   Column: {current_schema[0]}")
            print(f"   Type: {current_schema[1]}")
            print(f"   Max Length: {current_schema[2]}")
            print(f"   Nullable: {current_schema[3]}")

            if current_schema[2] == 64:
                print()
                print("⚠️  Column is already VARCHAR(64) - migration already applied!")
                print("   No changes needed.")
                return True
        else:
            print("   ❌ Column not found!")
            return False
        print()

        # Step 2: Check for existing truncated batch records
        print("📋 Step 2: Checking for truncated batch records...")
        cur.execute("""
            SELECT unique_id, LENGTH(unique_id) as len, created_at
            FROM split_payout_hostpay
            WHERE unique_id LIKE 'batch_%'
            ORDER BY created_at DESC
            LIMIT 5
        """)

        truncated_records = cur.fetchall()
        if truncated_records:
            print(f"   Found {len(truncated_records)} batch record(s):")
            for record in truncated_records:
                status = "✅ FULL" if record[1] >= 42 else "❌ TRUNCATED"
                print(f"   {status} - '{record[0]}' (len: {record[1]})")
        else:
            print("   No batch records found yet")
        print()

        # Step 3: Execute migration
        print("🔄 Step 3: Executing migration...")
        print("   ALTER TABLE split_payout_hostpay")
        print("   ALTER COLUMN unique_id TYPE VARCHAR(64);")

        cur.execute("""
            ALTER TABLE split_payout_hostpay
            ALTER COLUMN unique_id TYPE VARCHAR(64)
        """)

        conn.commit()
        print("   ✅ Migration executed successfully!")
        print()

        # Step 4: Verify changes
        print("✅ Step 4: Verifying migration...")
        cur.execute("""
            SELECT column_name, data_type, character_maximum_length, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'split_payout_hostpay'
              AND column_name = 'unique_id'
        """)

        new_schema = cur.fetchone()
        if new_schema:
            print(f"   Column: {new_schema[0]}")
            print(f"   Type: {new_schema[1]}")
            print(f"   Max Length: {new_schema[2]} ✅")
            print(f"   Nullable: {new_schema[3]}")

            if new_schema[2] == 64:
                print()
                print("=" * 80)
                print("🎉 MIGRATION SUCCESSFUL!")
                print("=" * 80)
                print()
                print("✅ split_payout_hostpay.unique_id extended to VARCHAR(64)")
                print("✅ Batch conversions will now work correctly")
                print("✅ Can store full 'batch_{uuid}' format (42 chars)")
                print()
                return True
            else:
                print()
                print("❌ Migration verification failed - length is not 64")
                return False
        else:
            print("   ❌ Column not found after migration!")
            return False

    except Exception as e:
        print()
        print(f"❌ Migration failed: {e}")
        if conn:
            conn.rollback()
            print("   Transaction rolled back")
        return False

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
            print()
            print("🔌 Database connection closed")

if __name__ == "__main__":
    print()
    success = execute_migration()
    print()

    if success:
        print("=" * 80)
        print("NEXT STEPS:")
        print("=" * 80)
        print("1. Redeploy PGP_HOSTPAY1_v1 with updated validation code")
        print("2. Test batch conversion end-to-end")
        print("3. Monitor logs for full 42-character unique_id values")
        print("=" * 80)
        sys.exit(0)
    else:
        print("=" * 80)
        print("MIGRATION FAILED - Manual intervention required")
        print("=" * 80)
        sys.exit(1)
