#!/usr/bin/env python
"""
Execute migration for user_conversation_state table
Migration: 001_conversation_state_table.sql
Date: 2025-11-12
"""
import os
import sys
import psycopg2
from google.cloud import secretmanager

def fetch_secret(secret_path):
    """Fetch secret from Google Secret Manager"""
    try:
        client = secretmanager.SecretManagerServiceClient()
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"❌ Error fetching secret {secret_path}: {e}")
        return None

def get_db_connection():
    """Get database connection"""
    host = fetch_secret("projects/telepay-459221/secrets/DATABASE_HOST_SECRET/versions/latest")
    dbname = fetch_secret("projects/telepay-459221/secrets/DATABASE_NAME_SECRET/versions/latest")
    user = fetch_secret("projects/telepay-459221/secrets/DATABASE_USER_SECRET/versions/latest")
    password = fetch_secret("projects/telepay-459221/secrets/DATABASE_PASSWORD_SECRET/versions/latest")

    if not all([host, dbname, user, password]):
        raise RuntimeError("❌ Failed to fetch required database credentials")

    return psycopg2.connect(
        dbname=dbname,
        user=user,
        password=password,
        host=host,
        port=5432
    )

def execute_migration():
    """Execute the conversation_state_table migration"""
    print("🚀 Starting migration: 001_conversation_state_table.sql")

    # Read migration file
    migration_path = "/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCBotCommand-10-26/migrations/001_conversation_state_table.sql"

    try:
        with open(migration_path, 'r') as f:
            migration_sql = f.read()
        print("✅ Migration file read successfully")
    except Exception as e:
        print(f"❌ Failed to read migration file: {e}")
        return False

    # Connect to database
    try:
        conn = get_db_connection()
        print("✅ Database connection established")
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        return False

    # Execute migration
    try:
        with conn.cursor() as cur:
            # Execute migration SQL
            cur.execute(migration_sql)
            conn.commit()
            print("✅ Migration executed successfully")

            # Verify table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'user_conversation_state'
                );
            """)
            table_exists = cur.fetchone()[0]

            if table_exists:
                print("✅ Table 'user_conversation_state' verified to exist")

                # Get table structure
                cur.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = 'user_conversation_state'
                    ORDER BY ordinal_position;
                """)

                print("\n📋 Table Structure:")
                print("-" * 60)
                for row in cur.fetchall():
                    print(f"  {row[0]:<25} {row[1]:<20} {'NULL' if row[2] == 'YES' else 'NOT NULL'}")
                print("-" * 60)

                # Check indexes
                cur.execute("""
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE tablename = 'user_conversation_state';
                """)

                print("\n🔑 Indexes:")
                print("-" * 60)
                for row in cur.fetchall():
                    print(f"  {row[0]}")
                    print(f"    {row[1]}")
                print("-" * 60)

            else:
                print("❌ Table 'user_conversation_state' was not created")
                return False

        conn.close()
        print("\n✅ Migration completed successfully!")
        return True

    except Exception as e:
        print(f"❌ Error executing migration: {e}")
        conn.rollback()
        conn.close()
        return False

if __name__ == "__main__":
    success = execute_migration()
    sys.exit(0 if success else 1)
