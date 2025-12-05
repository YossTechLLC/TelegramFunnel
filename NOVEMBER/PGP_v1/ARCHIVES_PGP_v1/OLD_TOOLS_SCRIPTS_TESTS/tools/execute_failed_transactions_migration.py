#!/usr/bin/env python3
"""
Execute failed_transactions table migration on telepaypsql database.
This script creates the failed_transactions table with all required indexes.
"""
import pg8000.native
from google.cloud.sql.connector import Connector
import time

print("🚀 [MIGRATION] Starting failed_transactions table migration")
print(f"⏰ [MIGRATION] Timestamp: {int(time.time())}")

# Database connection details
INSTANCE_CONNECTION_NAME = "pgp-live:us-central1:pgp-telepaypsql"
DB_NAME = "client_table"
DB_USER = "postgres"
DB_PASSWORD = "Chigdabeast123$"

# Initialize Cloud SQL Connector
connector = Connector()

try:
    print(f"🔗 [MIGRATION] Connecting to Cloud SQL instance: {INSTANCE_CONNECTION_NAME}")
    print(f"💾 [MIGRATION] Database: {DB_NAME}")

    # Create connection
    conn = connector.connect(
        INSTANCE_CONNECTION_NAME,
        "pg8000",
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME
    )

    print(f"✅ [MIGRATION] Connected successfully")

    # Read SQL migration file
    print(f"📖 [MIGRATION] Reading migration script")
    with open('create_failed_transactions_table.sql', 'r') as f:
        sql_script = f.read()

    # Extract only the main migration block (between BEGIN and COMMIT)
    # Split by "-- Verification query" to separate migration from verification
    parts = sql_script.split('-- Verification query')
    migration_sql = parts[0]
    verification_sql = parts[1].split('-- ROLLBACK SCRIPT')[0] if len(parts) > 1 else ""

    cursor = conn.cursor()

    # Execute the migration block (BEGIN...COMMIT) as one transaction
    print(f"⚙️ [MIGRATION] Executing migration transaction (CREATE TABLE + INDEXES)")
    cursor.execute(migration_sql)
    print(f"✅ [MIGRATION] Migration transaction executed successfully")

    # Execute verification query
    if verification_sql.strip():
        print(f"\n🔍 [MIGRATION] Executing verification query")
        cursor.execute(verification_sql.strip().rstrip(';'))
        rows = cursor.fetchall()
        print(f"📊 [MIGRATION] Table structure verification:")
        for row in rows:
            print(f"    {row[1]}: {row[2]} ({row[3]})")

    # Verify table exists
    print(f"\n🔍 [MIGRATION] Verifying table creation")
    cursor.execute("""
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_name = 'failed_transactions'
    """)
    table_exists = cursor.fetchone()[0]

    if table_exists:
        print(f"✅ [MIGRATION] Table 'failed_transactions' exists")
    else:
        print(f"❌ [MIGRATION] ERROR: Table 'failed_transactions' not found!")
        raise Exception("Table creation failed")

    # Verify indexes
    print(f"\n🔍 [MIGRATION] Verifying indexes")
    cursor.execute("""
        SELECT indexname
        FROM pg_indexes
        WHERE tablename = 'failed_transactions'
    """)
    indexes = cursor.fetchall()
    print(f"📊 [MIGRATION] Found {len(indexes)} indexes:")
    for idx in indexes:
        print(f"    ✅ {idx[0]}")

    # Verify row count (should be 0)
    print(f"\n🔍 [MIGRATION] Verifying row count")
    cursor.execute("SELECT COUNT(*) FROM failed_transactions")
    row_count = cursor.fetchone()[0]
    print(f"📊 [MIGRATION] Current row count: {row_count}")

    if row_count == 0:
        print(f"✅ [MIGRATION] Table is empty (expected)")
    else:
        print(f"⚠️ [MIGRATION] WARNING: Table has {row_count} existing rows")

    cursor.close()
    conn.close()
    connector.close()

    print(f"\n🎉 [MIGRATION] Migration completed successfully!")
    print(f"✅ [MIGRATION] Table 'failed_transactions' created with {len(indexes)} indexes")
    print(f"⏰ [MIGRATION] Completed at: {int(time.time())}")

except Exception as e:
    print(f"\n❌ [MIGRATION] ERROR: {e}")
    import traceback
    traceback.print_exc()

    try:
        connector.close()
    except:
        pass

    print(f"\n🔄 [MIGRATION] To rollback, run:")
    print(f"    BEGIN;")
    print(f"    DROP TABLE IF EXISTS failed_transactions CASCADE;")
    print(f"    COMMIT;")

    raise
