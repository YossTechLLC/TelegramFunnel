#!/usr/bin/env python3
"""
Fix payout_accumulation schema to allow NULL for conversion fields.

PROBLEM:
- eth_to_usdt_rate is NOT NULL but should be NULL for pending conversions
- conversion_timestamp is NOT NULL but should be NULL for pending conversions

ARCHITECTURE:
1. PGP_ACCUMULATOR stores payments in "pending" state WITHOUT conversion data
2. PGP_MICROBATCHPROCESSOR later fills in conversion data when processing

SOLUTION:
Make both fields NULLABLE since they're only populated during conversion.
"""
import sys
from google.cloud.sql.connector import Connector
from google.cloud import secretmanager

def get_secret(secret_name):
    """Fetch secret from Google Secret Manager"""
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/pgp-live/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode('UTF-8').strip()

def main():
    print("🚀 Starting payout_accumulation schema fix")
    print("="*80)

    connector = Connector()
    conn = connector.connect(
        "pgp-live:us-central1:pgp-telepaypsql",
        "pg8000",
        user=get_secret("DATABASE_USER_SECRET"),
        password=get_secret("DATABASE_PASSWORD_SECRET"),
        db=get_secret("DATABASE_NAME_SECRET"),
    )

    cursor = conn.cursor()

    # Check current constraints
    print("\n📋 Checking current schema...")
    cursor.execute("""
        SELECT column_name, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'payout_accumulation'
          AND column_name IN ('eth_to_usdt_rate', 'conversion_timestamp')
        ORDER BY column_name
    """)

    for row in cursor.fetchall():
        nullable = "NULL" if row[1] == "YES" else "NOT NULL"
        print(f"  {row[0]:30s} {nullable}")

    # Fix eth_to_usdt_rate
    print("\n🔧 Making eth_to_usdt_rate NULLABLE...")
    try:
        cursor.execute("""
            ALTER TABLE payout_accumulation
            ALTER COLUMN eth_to_usdt_rate DROP NOT NULL
        """)
        conn.commit()
        print("  ✅ eth_to_usdt_rate is now NULLABLE")
    except Exception as e:
        print(f"  ⚠️  Error (may already be nullable): {e}")

    # Fix conversion_timestamp
    print("\n🔧 Making conversion_timestamp NULLABLE...")
    try:
        cursor.execute("""
            ALTER TABLE payout_accumulation
            ALTER COLUMN conversion_timestamp DROP NOT NULL
        """)
        conn.commit()
        print("  ✅ conversion_timestamp is now NULLABLE")
    except Exception as e:
        print(f"  ⚠️  Error (may already be nullable): {e}")

    # Verify changes
    print("\n📋 Verifying updated schema...")
    cursor.execute("""
        SELECT column_name, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'payout_accumulation'
          AND column_name IN ('eth_to_usdt_rate', 'conversion_timestamp')
        ORDER BY column_name
    """)

    for row in cursor.fetchall():
        nullable = "NULL" if row[1] == "YES" else "NOT NULL"
        print(f"  {row[0]:30s} {nullable}")

    # Check for any existing records with NULL values
    print("\n📊 Checking existing records...")
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN eth_to_usdt_rate IS NULL THEN 1 ELSE 0 END) as null_rate,
            SUM(CASE WHEN conversion_timestamp IS NULL THEN 1 ELSE 0 END) as null_timestamp,
            SUM(CASE WHEN conversion_status = 'pending' THEN 1 ELSE 0 END) as pending_count
        FROM payout_accumulation
    """)

    result = cursor.fetchone()
    print(f"  Total records: {result[0]}")
    print(f"  Records with NULL eth_to_usdt_rate: {result[1]}")
    print(f"  Records with NULL conversion_timestamp: {result[2]}")
    print(f"  Records with pending status: {result[3]}")

    cursor.close()
    conn.close()

    print("\n" + "="*80)
    print("✅ Schema fix completed successfully!")
    print("="*80)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
