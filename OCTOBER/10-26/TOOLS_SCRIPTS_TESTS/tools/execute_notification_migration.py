#!/usr/bin/env python3
"""
📊 Execute notification columns migration for main_clients_database
Purpose: Add notification_status and notification_id columns to enable owner notifications
Version: 1.0
Date: 2025-11-11
"""
import os
import sys
from pathlib import Path
import pg8000
from google.cloud.sql.connector import Connector

def get_db_connection():
    """
    Create database connection via Cloud SQL Connector

    Returns:
        Database connection object
    """
    try:
        print("🔌 [MIGRATION] Initializing Cloud SQL Connector...")
        connector = Connector()

        conn = connector.connect(
            os.getenv('CLOUD_SQL_CONNECTION_NAME', 'telepay-459221:us-central1:telepaypsql'),
            "pg8000",
            user=os.getenv('DATABASE_USER_SECRET', 'postgres'),
            password=os.getenv('DATABASE_PASSWORD_SECRET'),
            db=os.getenv('DATABASE_NAME_SECRET', 'telepaydb')
        )

        print("✅ [MIGRATION] Database connection established")
        return conn

    except Exception as e:
        print(f"❌ [MIGRATION] Database connection failed: {e}")
        raise

def execute_migration():
    """
    Execute the notification columns migration

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        print("")
        print("=" * 70)
        print("🚀 [MIGRATION] Starting notification columns migration")
        print("=" * 70)
        print("")

        # Get script directory
        script_dir = Path(__file__).parent.parent / 'scripts'
        migration_file = script_dir / 'add_notification_columns.sql'

        if not migration_file.exists():
            print(f"❌ [MIGRATION] Migration file not found: {migration_file}")
            return False

        print(f"📝 [MIGRATION] Reading migration SQL from: {migration_file}")

        # Read migration SQL
        with open(migration_file, 'r') as f:
            migration_sql = f.read()

        print(f"📄 [MIGRATION] Migration SQL loaded ({len(migration_sql)} characters)")

        # Connect to database
        conn = get_db_connection()
        cursor = conn.cursor()

        print("")
        print("⚡ [MIGRATION] Executing migration SQL...")
        print("")

        # Execute migration
        cursor.execute(migration_sql)
        conn.commit()

        print("")
        print("✅ [MIGRATION] Migration SQL executed successfully!")
        print("")

        # Verify columns exist
        print("🔍 [MIGRATION] Verifying columns were created...")
        cursor.execute("""
            SELECT column_name, data_type, column_default, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'main_clients_database'
            AND column_name IN ('notification_status', 'notification_id')
            ORDER BY column_name;
        """)

        results = cursor.fetchall()

        if len(results) != 2:
            print(f"❌ [MIGRATION] Verification failed: Expected 2 columns, found {len(results)}")
            cursor.close()
            conn.close()
            return False

        print("✅ [MIGRATION] Columns verified:")
        print("")
        for row in results:
            column_name, data_type, column_default, is_nullable = row
            print(f"   • {column_name}")
            print(f"     └─ Type: {data_type}")
            print(f"     └─ Default: {column_default}")
            print(f"     └─ Nullable: {is_nullable}")
            print("")

        # Close connection
        cursor.close()
        conn.close()

        print("=" * 70)
        print("✅ [MIGRATION] Notification columns migration completed successfully!")
        print("=" * 70)
        print("")
        print("📊 Summary:")
        print("   ✅ Added column: notification_status (BOOLEAN, DEFAULT false, NOT NULL)")
        print("   ✅ Added column: notification_id (BIGINT, DEFAULT NULL)")
        print("")

        return True

    except Exception as e:
        print("")
        print("=" * 70)
        print(f"❌ [MIGRATION] Migration failed: {e}")
        print("=" * 70)
        print("")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("")
    print("🔧 Notification Columns Migration Script")
    print("   Database: telepaypsql")
    print("   Table: main_clients_database")
    print("")

    success = execute_migration()

    if success:
        print("✅ Migration completed successfully!")
        sys.exit(0)
    else:
        print("❌ Migration failed!")
        sys.exit(1)
