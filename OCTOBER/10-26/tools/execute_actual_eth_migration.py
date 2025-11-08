#!/usr/bin/env python3
"""
Execute actual_eth_amount database migration.
Adds actual_eth_amount columns to split_payout_request and split_payout_hostpay tables.
"""

import os
import sys
from google.cloud.sql.connector import Connector
import sqlalchemy

# Database configuration
INSTANCE_CONNECTION_NAME = "telepay-459221:us-central1:telepaypsql"
DB_USER = "postgres"
DB_PASS = "Chigdabeast123$"
DB_NAME = "client_table"

def get_connection():
    """Create database connection using Cloud SQL Python Connector."""
    connector = Connector()

    conn = connector.connect(
        INSTANCE_CONNECTION_NAME,
        "pg8000",
        user=DB_USER,
        password=DB_PASS,
        db=DB_NAME
    )

    return conn

def execute_migration():
    """Execute the actual_eth_amount migration."""
    print("🚀 Starting actual_eth_amount migration...")
    print("")

    try:
        # Create SQLAlchemy engine
        pool = sqlalchemy.create_engine(
            "postgresql+pg8000://",
            creator=get_connection,
        )

        with pool.connect() as conn:
            print("✅ Database connection established")
            print("")

            # Start transaction
            trans = conn.begin()

            try:
                # Step 1: Add column to split_payout_request
                print("📝 [1/6] Adding actual_eth_amount column to split_payout_request...")
                conn.execute(sqlalchemy.text("""
                    ALTER TABLE split_payout_request
                    ADD COLUMN IF NOT EXISTS actual_eth_amount NUMERIC(20,18) DEFAULT 0
                """))
                print("✅ Column added to split_payout_request")
                print("")

                # Step 2: Add column to split_payout_hostpay
                print("📝 [2/6] Adding actual_eth_amount column to split_payout_hostpay...")
                conn.execute(sqlalchemy.text("""
                    ALTER TABLE split_payout_hostpay
                    ADD COLUMN IF NOT EXISTS actual_eth_amount NUMERIC(20,18) DEFAULT 0
                """))
                print("✅ Column added to split_payout_hostpay")
                print("")

                # Step 3: Add constraint to split_payout_request
                print("📝 [3/6] Adding validation constraint to split_payout_request...")
                try:
                    conn.execute(sqlalchemy.text("""
                        ALTER TABLE split_payout_request
                        ADD CONSTRAINT actual_eth_positive CHECK (actual_eth_amount >= 0)
                    """))
                    print("✅ Constraint added to split_payout_request")
                except Exception as e:
                    if "already exists" in str(e):
                        print("⚠️  Constraint already exists (skipping)")
                    else:
                        raise
                print("")

                # Step 4: Add constraint to split_payout_hostpay
                print("📝 [4/6] Adding validation constraint to split_payout_hostpay...")
                try:
                    conn.execute(sqlalchemy.text("""
                        ALTER TABLE split_payout_hostpay
                        ADD CONSTRAINT actual_eth_positive CHECK (actual_eth_amount >= 0)
                    """))
                    print("✅ Constraint added to split_payout_hostpay")
                except Exception as e:
                    if "already exists" in str(e):
                        print("⚠️  Constraint already exists (skipping)")
                    else:
                        raise
                print("")

                # Step 5: Create index on split_payout_request
                print("📝 [5/6] Creating index on split_payout_request.actual_eth_amount...")
                conn.execute(sqlalchemy.text("""
                    CREATE INDEX IF NOT EXISTS idx_split_payout_request_actual_eth
                    ON split_payout_request(actual_eth_amount)
                    WHERE actual_eth_amount > 0
                """))
                print("✅ Index created on split_payout_request")
                print("")

                # Step 6: Create index on split_payout_hostpay
                print("📝 [6/6] Creating index on split_payout_hostpay.actual_eth_amount...")
                conn.execute(sqlalchemy.text("""
                    CREATE INDEX IF NOT EXISTS idx_split_payout_hostpay_actual_eth
                    ON split_payout_hostpay(actual_eth_amount)
                    WHERE actual_eth_amount > 0
                """))
                print("✅ Index created on split_payout_hostpay")
                print("")

                # Commit transaction
                trans.commit()
                print("✅ Transaction committed successfully")
                print("")

                # Verify migration
                print("🔍 Verifying migration...")
                print("")

                result = conn.execute(sqlalchemy.text("""
                    SELECT column_name, data_type, column_default
                    FROM information_schema.columns
                    WHERE table_name = 'split_payout_request'
                      AND column_name = 'actual_eth_amount'
                """))
                row = result.fetchone()
                if row:
                    print(f"✅ split_payout_request.actual_eth_amount:")
                    print(f"   Column: {row[0]}")
                    print(f"   Type: {row[1]}")
                    print(f"   Default: {row[2]}")
                else:
                    print(f"❌ split_payout_request.actual_eth_amount not found!")
                print("")

                result = conn.execute(sqlalchemy.text("""
                    SELECT column_name, data_type, column_default
                    FROM information_schema.columns
                    WHERE table_name = 'split_payout_hostpay'
                      AND column_name = 'actual_eth_amount'
                """))
                row = result.fetchone()
                if row:
                    print(f"✅ split_payout_hostpay.actual_eth_amount:")
                    print(f"   Column: {row[0]}")
                    print(f"   Type: {row[1]}")
                    print(f"   Default: {row[2]}")
                else:
                    print(f"❌ split_payout_hostpay.actual_eth_amount not found!")
                print("")

                print("🎉 Migration completed successfully!")
                return True

            except Exception as e:
                trans.rollback()
                print(f"❌ Migration failed: {e}")
                print("")
                print("⏮️  Transaction rolled back")
                return False

    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

if __name__ == "__main__":
    success = execute_migration()
    sys.exit(0 if success else 1)
