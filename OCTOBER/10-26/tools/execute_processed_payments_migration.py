#!/usr/bin/env python3
"""
Execute processed_payments table migration
"""
import os
import sys
import pg8000
from google.cloud.sql.connector import Connector

# Database configuration
CLOUD_SQL_CONNECTION_NAME = "telepay-459221:us-central1:telepaypsql"
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
    print("🔧 [MIGRATION] Connecting to Cloud SQL...")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("✅ [MIGRATION] Connected successfully")
        print("")
        print("🚀 [MIGRATION] Creating processed_payments table...")

        # Create table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_payments (
                -- Primary key: NowPayments payment_id (unique identifier)
                payment_id BIGINT PRIMARY KEY,

                -- Reference data for lookups and debugging
                user_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,

                -- Processing state flags
                gcwebhook1_processed BOOLEAN DEFAULT FALSE,
                gcwebhook1_processed_at TIMESTAMP,

                -- Telegram invite state
                telegram_invite_sent BOOLEAN DEFAULT FALSE,
                telegram_invite_sent_at TIMESTAMP,
                telegram_invite_link TEXT,

                -- Audit fields
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                -- Constraints
                CONSTRAINT payment_id_positive CHECK (payment_id > 0),
                CONSTRAINT user_id_positive CHECK (user_id > 0)
            );
        """)
        print("✅ [MIGRATION] Table created")

        # Create indexes
        print("🔧 [MIGRATION] Creating indexes...")

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_processed_payments_user_channel
            ON processed_payments(user_id, channel_id);
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_processed_payments_invite_status
            ON processed_payments(telegram_invite_sent);
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_processed_payments_webhook1_status
            ON processed_payments(gcwebhook1_processed);
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_processed_payments_created_at
            ON processed_payments(created_at DESC);
        """)
        print("✅ [MIGRATION] Indexes created")

        # Add comments
        print("🔧 [MIGRATION] Adding table documentation...")

        cursor.execute("""
            COMMENT ON TABLE processed_payments IS 'Tracks payment processing state for idempotency - prevents duplicate Telegram invites and payment accumulation';
        """)

        cursor.execute("""
            COMMENT ON COLUMN processed_payments.payment_id IS 'NowPayments payment_id (unique identifier from IPN callback)';
        """)

        cursor.execute("""
            COMMENT ON COLUMN processed_payments.gcwebhook1_processed IS 'Flag indicating if GCWebhook1 successfully processed this payment';
        """)

        cursor.execute("""
            COMMENT ON COLUMN processed_payments.telegram_invite_sent IS 'Flag indicating if Telegram invite successfully sent to user';
        """)

        cursor.execute("""
            COMMENT ON COLUMN processed_payments.telegram_invite_link IS 'The actual one-time invite link sent to user (for reference/debugging)';
        """)
        print("✅ [MIGRATION] Documentation added")

        # Commit transaction
        conn.commit()
        print("✅ [MIGRATION] Transaction committed")

        # Verify table structure
        print("")
        print("📊 [VERIFICATION] Verifying table structure...")
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'processed_payments'
            ORDER BY ordinal_position;
        """)

        columns = cursor.fetchall()
        print("Columns:")
        for col in columns:
            print(f"  - {col[0]}: {col[1]} (nullable: {col[2]}, default: {col[3]})")

        # Verify indexes
        print("")
        print("📊 [VERIFICATION] Verifying indexes...")
        cursor.execute("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'processed_payments'
            ORDER BY indexname;
        """)

        indexes = cursor.fetchall()
        print("Indexes:")
        for idx in indexes:
            print(f"  - {idx[0]}")

        # Check initial count
        print("")
        print("📊 [VERIFICATION] Checking initial record count...")
        cursor.execute("SELECT COUNT(*) FROM processed_payments;")
        count = cursor.fetchone()[0]
        print(f"Initial count: {count} records")

        cursor.close()
        conn.close()

        print("")
        print("🎉 [MIGRATION] Migration completed successfully!")
        return 0

    except Exception as e:
        print(f"❌ [MIGRATION] Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
