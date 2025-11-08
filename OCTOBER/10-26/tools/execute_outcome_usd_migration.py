#!/usr/bin/env python3
"""
Execute Database Migration: Add nowpayments_outcome_amount_usd Column
Part of: NowPayments Outcome Amount - GCWebhook1 Architecture Implementation
"""
import os
import sys
from google.cloud.sql.connector import Connector
import pg8000

def get_db_connection():
    """Create database connection using Cloud SQL Connector."""
    connector = Connector()

    # Database credentials
    instance_connection_name = "telepay-459221:us-central1:telepaypsql"
    db_user = "postgres"
    db_pass = "Chigdabeast123$"
    db_name = "client_table"

    conn = connector.connect(
        instance_connection_name,
        "pg8000",
        user=db_user,
        password=db_pass,
        db=db_name
    )

    return conn, connector

def execute_migration():
    """Execute the database migration."""
    print("=" * 80)
    print("🗄️ Database Migration: Add nowpayments_outcome_amount_usd Column")
    print("=" * 80)
    print("")

    try:
        # Connect to database
        print("🔗 Connecting to database...")
        conn, connector = get_db_connection()
        cur = conn.cursor()
        print("✅ Connected to database: telepaypsql")
        print("")

        # Step 1.1: Add column
        print("📋 Step 1.1: Adding nowpayments_outcome_amount_usd column...")
        cur.execute("""
            ALTER TABLE private_channel_users_database
            ADD COLUMN IF NOT EXISTS nowpayments_outcome_amount_usd DECIMAL(20, 8)
        """)
        conn.commit()
        print("✅ Column added successfully")
        print("")

        # Verify column exists
        cur.execute("""
            SELECT column_name, data_type, numeric_precision, numeric_scale
            FROM information_schema.columns
            WHERE table_name = 'private_channel_users_database'
            AND column_name = 'nowpayments_outcome_amount_usd'
        """)
        result = cur.fetchone()

        if result:
            print("📊 Column Details:")
            print(f"   Name: {result[0]}")
            print(f"   Type: {result[1]}")
            print(f"   Precision: {result[2]}")
            print(f"   Scale: {result[3]}")
            print("")
        else:
            print("❌ ERROR: Column not found after creation!")
            return False

        # Step 1.2: Add index
        print("📋 Step 1.2: Creating index on nowpayments_payment_id...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_nowpayments_payment_id
            ON private_channel_users_database(nowpayments_payment_id)
        """)
        conn.commit()
        print("✅ Index created successfully")
        print("")

        # Verify index exists
        cur.execute("""
            SELECT indexname, tablename
            FROM pg_indexes
            WHERE indexname = 'idx_nowpayments_payment_id'
        """)
        index_result = cur.fetchone()

        if index_result:
            print("📊 Index Details:")
            print(f"   Name: {index_result[0]}")
            print(f"   Table: {index_result[1]}")
            print("")
        else:
            print("❌ ERROR: Index not found after creation!")
            return False

        # Step 1.3: Add comment
        print("📋 Step 1.3: Adding column documentation...")
        cur.execute("""
            COMMENT ON COLUMN private_channel_users_database.nowpayments_outcome_amount_usd IS
            'Actual USD value of outcome_amount calculated via CoinGecko API at time of IPN callback. This is the REAL amount received, not the declared subscription price.'
        """)
        conn.commit()
        print("✅ Comment added successfully")
        print("")

        # Verify comment
        cur.execute("""
            SELECT
                a.attname as column_name,
                col_description(a.attrelid, a.attnum) as column_comment
            FROM pg_attribute a
            JOIN pg_class c ON a.attrelid = c.oid
            WHERE c.relname = 'private_channel_users_database'
            AND a.attname = 'nowpayments_outcome_amount_usd'
        """)
        comment_result = cur.fetchone()

        if comment_result and comment_result[1]:
            print("📊 Column Comment:")
            print(f"   {comment_result[1]}")
            print("")
        else:
            print("⚠️ WARNING: Comment not found (may not be critical)")
            print("")

        # Close connection
        cur.close()
        conn.close()
        connector.close()

        print("=" * 80)
        print("🎉 Database migration completed successfully!")
        print("=" * 80)
        print("")
        print("✅ Summary:")
        print("   - Column 'nowpayments_outcome_amount_usd' added (DECIMAL 20,8)")
        print("   - Index 'idx_nowpayments_payment_id' created")
        print("   - Column documentation added")
        print("")

        return True

    except Exception as e:
        print(f"❌ ERROR during migration: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = execute_migration()
    sys.exit(0 if success else 1)
