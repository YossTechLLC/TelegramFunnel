#!/usr/bin/env python3
"""
Execute broadcast_manager table migration
Reads and executes create_broadcast_manager_table.sql on telepaypsql database
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
    """Execute the broadcast_manager table migration."""

    print("🚀 Starting broadcast_manager table migration...")
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
    script_path = Path(__file__).parent.parent / 'scripts' / 'create_broadcast_manager_table.sql'
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
                    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'broadcast_manager') as column_count,
                    (SELECT COUNT(*) FROM pg_indexes WHERE tablename = 'broadcast_manager') as index_count
                FROM information_schema.tables
                WHERE table_name = 'broadcast_manager'
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
                WHERE event_object_table = 'broadcast_manager'
            """)

            triggers = cur.fetchall()
            print(f"\n✅ Triggers: {len(triggers)}")
            for trigger in triggers:
                print(f"  - {trigger[0]} (ON {trigger[1]} {trigger[2]})")

            # Show table structure summary
            cur.execute("""
                SELECT column_name, data_type, column_default, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'broadcast_manager'
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
    print("  1. Run populate_broadcast_manager.py to populate initial data")
    print("  2. Verify data with: SELECT COUNT(*) FROM broadcast_manager;")
    print("\n💡 To rollback: run rollback_broadcast_manager_table.sql")

if __name__ == "__main__":
    execute_migration()
