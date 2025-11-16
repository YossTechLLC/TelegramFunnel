#!/usr/bin/python3
"""
Execute migration to add actual_eth_amount column to split_payout_que table.

This script:
1. Connects to the telepaypsql database
2. Executes the migration SQL
3. Verifies the migration succeeded
"""

import sys
import os
from google.cloud.sql.connector import Connector
import sqlalchemy
from sqlalchemy import text

def execute_migration():
    """Execute the actual_eth_amount migration for split_payout_que."""

    print("=" * 80)
    print("🗃️  MIGRATION: Add actual_eth_amount to split_payout_que")
    print("=" * 80)

    # Database connection parameters
    INSTANCE_CONNECTION_NAME = "pgp-live:us-central1:pgp-telepaypsql"
    DB_USER = "postgres"
    DB_PASSWORD = "Chigdabeast123$"
    DB_NAME = "client_table"

    connector = Connector()

    try:
        # Create connection
        print("\n📡 [CONNECT] Connecting to Cloud SQL...")

        def getconn():
            conn = connector.connect(
                INSTANCE_CONNECTION_NAME,
                "pg8000",
                user=DB_USER,
                password=DB_PASSWORD,
                db=DB_NAME
            )
            return conn

        pool = sqlalchemy.create_engine(
            "postgresql+pg8000://",
            creator=getconn,
        )

        print("✅ [CONNECT] Connected successfully")

        # Read migration SQL
        migration_file = "/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/scripts/add_actual_eth_to_split_payout_que.sql"

        print(f"\n📖 [READ] Reading migration file: {migration_file}")

        with open(migration_file, 'r') as f:
            migration_sql = f.read()

        # Extract only the migration part (before verification queries)
        migration_part = migration_sql.split("-- ============================================================================")[0]

        print(f"✅ [READ] Migration SQL loaded ({len(migration_part)} characters)")

        # Execute migration
        print("\n🔄 [EXECUTE] Executing migration...")
        print("-" * 80)

        with pool.connect() as conn:
            # Execute the migration
            conn.execute(text(migration_part))
            conn.commit()

            print("✅ [EXECUTE] Migration executed successfully")

            # Run verification queries
            print("\n🔍 [VERIFY] Running verification queries...")
            print("-" * 80)

            # Verification 1: Check column exists
            result = conn.execute(text("""
                SELECT column_name, data_type, column_default, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'split_payout_que'
                  AND column_name = 'actual_eth_amount'
            """))

            row = result.fetchone()
            if row:
                print(f"✅ [VERIFY] Column exists:")
                print(f"   - Name: {row[0]}")
                print(f"   - Type: {row[1]}")
                print(f"   - Default: {row[2]}")
                print(f"   - Nullable: {row[3]}")
            else:
                print("❌ [VERIFY] Column NOT found!")
                return False

            # Verification 2: Check constraint exists
            result = conn.execute(text("""
                SELECT constraint_name, check_clause
                FROM information_schema.check_constraints
                WHERE constraint_name = 'actual_eth_positive_que'
            """))

            row = result.fetchone()
            if row:
                print(f"\n✅ [VERIFY] Constraint exists:")
                print(f"   - Name: {row[0]}")
                print(f"   - Clause: {row[1]}")
            else:
                print("\n⚠️  [VERIFY] Constraint NOT found (may already exist)")

            # Verification 3: Check index exists
            result = conn.execute(text("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'split_payout_que'
                  AND indexname = 'idx_split_payout_que_actual_eth'
            """))

            row = result.fetchone()
            if row:
                print(f"\n✅ [VERIFY] Index exists:")
                print(f"   - Name: {row[0]}")
                print(f"   - Definition: {row[1][:80]}...")
            else:
                print("\n⚠️  [VERIFY] Index NOT found (may already exist)")

        print("\n" + "=" * 80)
        print("✅ MIGRATION COMPLETE")
        print("=" * 80)

        return True

    except Exception as e:
        print(f"\n❌ [ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        connector.close()
        print("\n🔌 [DISCONNECT] Connection closed")

if __name__ == "__main__":
    success = execute_migration()
    sys.exit(0 if success else 1)
