#!/usr/bin/env python3
"""
Execute migration to add closed_channel_donation_message column
Created: 2025-11-11
Reference: DONATION_MESSAGE_ARCHITECTURE.md
"""

import sys
import os
from google.cloud.sql.connector import Connector
import pg8000

# Database configuration
PROJECT_ID = "pgp-live"
REGION = "us-central1"
INSTANCE_NAME = "telepaypsql"
DATABASE_NAME = "client_table"
DB_USER = "postgres"
DB_PASS = "Chigdabeast123$"

DEFAULT_DONATION_MESSAGE = (
    "Enjoying the content? Consider making a donation to help us "
    "continue providing quality content. Click the button below to "
    "donate any amount you choose."
)

def get_connection():
    """Create database connection via Cloud SQL Connector"""
    connector = Connector()

    conn = connector.connect(
        f"{PROJECT_ID}:{REGION}:{INSTANCE_NAME}",
        "pg8000",
        user=DB_USER,
        password=DB_PASS,
        db=DATABASE_NAME
    )
    return conn

def execute_migration():
    """Execute the donation message migration"""
    print("🚀 Starting donation message migration...")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Step 1: Add column with NULL constraint
        print("📝 Step 1: Adding column...")
        cursor.execute("""
            ALTER TABLE main_clients_database
            ADD COLUMN IF NOT EXISTS closed_channel_donation_message VARCHAR(256);
        """)
        conn.commit()
        print("✅ Column added")

        # Step 2: Set default message for existing channels
        print("📝 Step 2: Setting default message for existing channels...")
        cursor.execute("""
            UPDATE main_clients_database
            SET closed_channel_donation_message = %s
            WHERE closed_channel_donation_message IS NULL;
        """, (DEFAULT_DONATION_MESSAGE,))

        updated_count = cursor.rowcount
        conn.commit()
        print(f"✅ Updated {updated_count} existing channels with default message")

        # Step 3: Add NOT NULL constraint
        print("📝 Step 3: Adding NOT NULL constraint...")
        cursor.execute("""
            ALTER TABLE main_clients_database
            ALTER COLUMN closed_channel_donation_message SET NOT NULL;
        """)
        conn.commit()
        print("✅ NOT NULL constraint added")

        # Step 4: Add check constraint
        print("📝 Step 4: Adding check constraint...")
        cursor.execute("""
            ALTER TABLE main_clients_database
            ADD CONSTRAINT check_donation_message_not_empty
            CHECK (LENGTH(TRIM(closed_channel_donation_message)) > 0);
        """)
        conn.commit()
        print("✅ Check constraint added")

        # Verification
        print("\n📊 Verification:")
        cursor.execute("""
            SELECT
                COUNT(*) as total_channels,
                COUNT(closed_channel_donation_message) as channels_with_message,
                AVG(LENGTH(closed_channel_donation_message)) as avg_message_length,
                MIN(LENGTH(closed_channel_donation_message)) as min_length,
                MAX(LENGTH(closed_channel_donation_message)) as max_length
            FROM main_clients_database;
        """)

        stats = cursor.fetchone()
        print(f"  Total channels: {stats[0]}")
        print(f"  Channels with message: {stats[1]}")
        print(f"  Average message length: {float(stats[2]):.2f} characters")
        print(f"  Min message length: {stats[3]} characters")
        print(f"  Max message length: {stats[4]} characters")

        # Sample data
        print("\n📋 Sample channels:")
        cursor.execute("""
            SELECT
                open_channel_id,
                closed_channel_title,
                LEFT(closed_channel_donation_message, 60) || '...' as message_preview
            FROM main_clients_database
            LIMIT 3;
        """)

        samples = cursor.fetchall()
        for sample in samples:
            print(f"  - {sample[1]} ({sample[0]})")
            print(f"    Message: {sample[2]}")

        cursor.close()
        conn.close()

        print("\n✅ Migration completed successfully!")
        return True

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

if __name__ == "__main__":
    success = execute_migration()
    sys.exit(0 if success else 1)
