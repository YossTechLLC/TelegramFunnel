#!/usr/bin/env python3
"""
Execute donation_keypad_state table migration
Reads and executes create_donation_keypad_state_table.sql on telepaypsql database
"""

import os
import sys
from pathlib import Path
from google.cloud import secretmanager
import psycopg2

def fetch_secret(secret_name):
    """Fetch secret from Secret Manager."""
    try:
        client = secretmanager.SecretManagerServiceClient()
        # Build secret path: projects/PROJECT_ID/secrets/SECRET_NAME/versions/latest
        project_id = "pgp-live"
        secret_path = f"projects/{project_id}/secrets/{secret_name}/versions/latest"

        response = client.access_secret_version(request={"name": secret_path})
        value = response.payload.data.decode("UTF-8")
        return value
    except Exception as e:
        print(f"❌ Error fetching secret {secret_name}: {e}")
        raise

def execute_migration():
    """Execute the donation_keypad_state table migration."""

    print("🚀 Starting donation_keypad_state table migration...")
    print("=" * 70)

    # Fetch database credentials from Secret Manager
    print("\n📡 Fetching database credentials from Secret Manager...")
    try:
        db_host = fetch_secret('DATABASE_HOST_SECRET')
        db_name = fetch_secret('DATABASE_NAME_SECRET')
        db_user = fetch_secret('DATABASE_USER_SECRET')
        db_password = fetch_secret('DATABASE_PASSWORD_SECRET')
        print("✅ Database credentials fetched successfully")
        print(f"   Host: {db_host}")
        print(f"   Database: {db_name}")
        print(f"   User: {db_user}")
    except Exception as e:
        print(f"❌ Failed to fetch database credentials: {e}")
        sys.exit(1)

    # Read migration SQL script
    script_path = Path(__file__).parent.parent / 'scripts' / 'create_donation_keypad_state_table.sql'
    print(f"\n📄 Reading migration script from: {script_path}")

    if not script_path.exists():
        print(f"❌ Migration script not found: {script_path}")
        sys.exit(1)

    with open(script_path, 'r') as f:
        migration_sql = f.read()

    print(f"✅ Migration script loaded ({len(migration_sql)} characters)")

    # Connect to database
    print(f"\n🔌 Connecting to database: {db_name} on {db_host}...")

    try:
        conn = psycopg2.connect(
            host=db_host,
            dbname=db_name,
            user=db_user,
            password=db_password,
            port=5432
        )
        print("✅ Database connection established")
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        sys.exit(1)

    # Execute migration
    try:
        with conn.cursor() as cur:
            print("\n⚙️  Executing migration SQL script...")
            print("-" * 70)

            # Execute the migration script
            cur.execute(migration_sql)

            # Fetch any NOTICE messages (from RAISE NOTICE)
            for notice in conn.notices:
                print(notice.strip())

            # Commit the transaction
            conn.commit()

            print("-" * 70)
            print("✅ Migration executed successfully!")

            # Verify table creation
            print("\n🔍 Verifying table creation...")
            cur.execute("""
                SELECT
                    table_name,
                    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'donation_keypad_state') as column_count,
                    (SELECT COUNT(*) FROM pg_indexes WHERE tablename = 'donation_keypad_state') as index_count
                FROM information_schema.tables
                WHERE table_name = 'donation_keypad_state'
            """)

            result = cur.fetchone()
            if result:
                table_name, column_count, index_count = result
                print(f"✅ Table: {table_name}")
                print(f"✅ Columns: {column_count}")
                print(f"✅ Indexes: {index_count}")
            else:
                print("❌ Table verification failed - table not found")
                sys.exit(1)

            # Verify trigger
            cur.execute("""
                SELECT trigger_name, event_manipulation, event_object_table
                FROM information_schema.triggers
                WHERE event_object_table = 'donation_keypad_state'
            """)

            triggers = cur.fetchall()
            print(f"\n✅ Triggers: {len(triggers)}")
            for trigger in triggers:
                print(f"  - {trigger[0]} (ON {trigger[1]} {trigger[2]})")

            # Verify cleanup function
            cur.execute("""
                SELECT proname, pronargs
                FROM pg_proc
                WHERE proname = 'cleanup_stale_donation_states'
            """)

            function = cur.fetchone()
            if function:
                print(f"\n✅ Cleanup function: {function[0]} (args: {function[1]})")
            else:
                print("\n❌ Cleanup function not found")

            # Show table structure summary
            cur.execute("""
                SELECT column_name, data_type, column_default, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'donation_keypad_state'
                ORDER BY ordinal_position
            """)

            columns = cur.fetchall()
            print(f"\n📊 Table Structure ({len(columns)} columns):")
            print("-" * 70)
            for col in columns:
                col_name, col_type, col_default, nullable = col
                default_str = f"DEFAULT {col_default[:30]}..." if col_default and len(col_default) > 30 else (f"DEFAULT {col_default}" if col_default else "")
                nullable_str = "NULL" if nullable == 'YES' else "NOT NULL"
                print(f"  {col_name:30s} {col_type:20s} {nullable_str:10s} {default_str}")

            print("-" * 70)

            # Test cleanup function
            print("\n🧪 Testing cleanup function...")
            cur.execute("SELECT cleanup_stale_donation_states()")
            deleted_count = cur.fetchone()[0]
            print(f"✅ Cleanup function works (deleted {deleted_count} stale states)")

    except psycopg2.Error as e:
        print(f"\n❌ Database error during migration: {e}")
        print(f"   SQLSTATE: {e.pgcode}")
        print(f"   Details: {e.pgerror}")
        conn.rollback()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error during migration: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()
        print("\n🔌 Database connection closed")

    print("\n" + "=" * 70)
    print("🎉 Migration completed successfully!")
    print("=" * 70)
    print("\n📋 Next steps:")
    print("  1. Update GCDonationHandler keypad_handler.py to use database state")
    print("  2. Test donation keypad flow with multiple instances")
    print("  3. Set up cron job to run cleanup_stale_donation_states() periodically")
    print("\n💡 Cleanup function usage:")
    print("  SELECT cleanup_stale_donation_states();  -- Returns count of deleted states")

if __name__ == "__main__":
    execute_migration()
