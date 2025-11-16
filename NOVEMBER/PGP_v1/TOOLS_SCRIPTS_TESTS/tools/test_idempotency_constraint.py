#!/usr/bin/env python3
"""
Test ON CONFLICT idempotency behavior for processed_payments table
"""
import sys
import pg8000
from google.cloud.sql.connector import Connector

# Database configuration
CLOUD_SQL_CONNECTION_NAME = "pgp-live:us-central1:pgp-psql"
DATABASE_NAME = "client_table"
DATABASE_USER = "postgres"
DATABASE_PASSWORD = "Chigdabeast123$"

def get_connection():
    """Get Cloud SQL connection"""
    connector = Connector()
    conn = connector.connect(
        CLOUD_SQL_CONNECTION_NAME,
        "pg8000",
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        db=DATABASE_NAME
    )
    return conn

def main():
    print("🧪 [TEST] Testing ON CONFLICT idempotency behavior...")
    print("")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Test 1: Insert new record
        print("📝 [TEST] Test 1: Inserting new record...")
        cursor.execute("""
            INSERT INTO processed_payments (payment_id, user_id, channel_id)
            VALUES (999999999, 123456, -1001234567890);
        """)
        conn.commit()
        print("✅ [TEST] First insert successful")

        # Test 2: Try to insert duplicate (should do nothing)
        print("")
        print("📝 [TEST] Test 2: Attempting duplicate insert with ON CONFLICT DO NOTHING...")
        cursor.execute("""
            INSERT INTO processed_payments (payment_id, user_id, channel_id)
            VALUES (999999999, 123456, -1001234567890)
            ON CONFLICT (payment_id) DO NOTHING;
        """)
        conn.commit()
        print("✅ [TEST] ON CONFLICT worked - no error raised")

        # Test 3: Verify only one record exists
        print("")
        print("📝 [TEST] Test 3: Verifying record count...")
        cursor.execute("""
            SELECT COUNT(*) FROM processed_payments WHERE payment_id = 999999999;
        """)
        count = cursor.fetchone()[0]
        print(f"Record count: {count}")

        if count == 1:
            print("✅ [TEST] PASS - Only one record exists (idempotency working)")
        else:
            print(f"❌ [TEST] FAIL - Expected 1 record, found {count}")
            return 1

        # Clean up test data
        print("")
        print("🧹 [TEST] Cleaning up test data...")
        cursor.execute("DELETE FROM processed_payments WHERE payment_id = 999999999;")
        conn.commit()
        print("✅ [TEST] Test data removed")

        cursor.close()
        conn.close()

        print("")
        print("🎉 [TEST] All idempotency tests passed!")
        return 0

    except Exception as e:
        print(f"❌ [TEST] Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
