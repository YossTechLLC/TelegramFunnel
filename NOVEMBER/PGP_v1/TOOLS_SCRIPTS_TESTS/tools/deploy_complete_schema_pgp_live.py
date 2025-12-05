#!/usr/bin/env python3
"""
Deploy complete PayGatePrime database schema to pgp-live.

This script:
1. Creates all custom ENUM types
2. Creates all 15 tables with proper constraints
3. Creates all indexes
4. Inserts legacy user
5. Populates currency_to_network data (87 mappings)

WARNING: This will create tables in pgp-live project.
Make sure to verify you're deploying to the correct project!
"""
import sys
import os
from pathlib import Path
from google.cloud.sql.connector import Connector
from google.cloud import secretmanager

# Target project configuration
PROJECT_ID = "pgp-live"
INSTANCE_CONNECTION_NAME = "pgp-live:us-central1:pgp-telepaypsql"

def get_secret(secret_name):
    """Fetch secret from Google Secret Manager"""
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode('UTF-8').strip()

def get_db_connection():
    """Create database connection using Cloud SQL Connector"""
    connector = Connector()

    conn = connector.connect(
        INSTANCE_CONNECTION_NAME,
        "pg8000",
        user=get_secret("DATABASE_USER_SECRET"),
        password=get_secret("DATABASE_PASSWORD_SECRET"),
        db=get_secret("DATABASE_NAME_SECRET"),
    )

    return conn

def execute_sql_file(conn, file_path, description):
    """Execute SQL file and return success/failure"""
    print(f"\n{'=' * 80}")
    print(f"📝 {description}")
    print(f"   File: {file_path}")
    print('=' * 80)

    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return False

    with open(file_path, 'r') as f:
        sql = f.read()

    cursor = conn.cursor()
    try:
        cursor.execute(sql)
        conn.commit()
        print(f"✅ {description} - SUCCESS")
        return True
    except Exception as e:
        print(f"❌ {description} - FAILED")
        print(f"   Error: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()

def verify_schema(conn):
    """Verify schema was created correctly"""
    print(f"\n{'=' * 80}")
    print("🔍 VERIFICATION: Checking created schema")
    print('=' * 80)

    cursor = conn.cursor()

    # Check tables
    cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    tables = [row[0] for row in cursor.fetchall()]

    print(f"\n✅ Found {len(tables)} tables:")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"   • {table:40s} ({count:,} rows)")

    # Check ENUM types
    cursor.execute("""
        SELECT typname
        FROM pg_type
        WHERE typtype = 'e'
        ORDER BY typname
    """)
    enums = [row[0] for row in cursor.fetchall()]

    print(f"\n✅ Found {len(enums)} custom ENUM types:")
    for enum in enums:
        print(f"   • {enum}")

    # Check registered_users
    cursor.execute("""
        SELECT username, email, is_active
        FROM registered_users
        WHERE user_id = '00000000-0000-0000-0000-000000000000'
    """)
    legacy_user = cursor.fetchone()

    if legacy_user:
        print(f"\n✅ Legacy user created:")
        print(f"   • Username: {legacy_user[0]}")
        print(f"   • Email: {legacy_user[1]}")
        print(f"   • Active: {legacy_user[2]}")
    else:
        print(f"\n⚠️  Legacy user NOT found!")

    # Check currency_to_network
    cursor.execute("SELECT COUNT(*) FROM currency_to_network")
    currency_count = cursor.fetchone()[0]

    print(f"\n✅ Currency/Network mappings: {currency_count}")

    cursor.close()

    # Verify expected counts
    expected_tables = 15
    expected_enums = 4
    expected_currencies = 87

    all_good = True
    if len(tables) != expected_tables:
        print(f"\n⚠️  Expected {expected_tables} tables, found {len(tables)}")
        all_good = False
    if len(enums) != expected_enums:
        print(f"\n⚠️  Expected {expected_enums} ENUMs, found {len(enums)}")
        all_good = False
    if currency_count != expected_currencies:
        print(f"\n⚠️  Expected {expected_currencies} currency mappings, found {currency_count}")
        all_good = False

    return all_good

def main():
    print("=" * 80)
    print("🚀 PayGatePrime Database Schema Deployment")
    print("=" * 80)
    print(f"📍 Project: {PROJECT_ID}")
    print(f"📍 Instance: {INSTANCE_CONNECTION_NAME}")
    print(f"📍 Database: telepaydb")
    print("=" * 80)

    # Confirm deployment
    confirm = input("\n⚠️  Deploy to pgp-live? (type 'yes' to confirm): ")
    if confirm.lower() != 'yes':
        print("\n❌ Deployment cancelled")
        sys.exit(1)

    # Connect to database
    print("\n📡 Connecting to database...")
    try:
        conn = get_db_connection()
        print("✅ Connected successfully")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

    # Get script directory
    script_dir = Path(__file__).parent.parent / "migrations"

    # Execute migrations in order
    migrations = [
        (script_dir / "001_create_complete_schema.sql", "Creating complete schema (15 tables, 4 ENUMs)"),
        (script_dir / "002_populate_currency_to_network.sql", "Populating currency_to_network (87 mappings)"),
    ]

    all_success = True
    for file_path, description in migrations:
        success = execute_sql_file(conn, str(file_path), description)
        if not success:
            all_success = False
            print(f"\n❌ Migration failed, stopping deployment")
            break

    if all_success:
        # Verify deployment
        verification_passed = verify_schema(conn)

        print("\n" + "=" * 80)
        if verification_passed:
            print("🎉 DEPLOYMENT SUCCESSFUL!")
            print("=" * 80)
            print("\n✅ All migrations completed successfully")
            print("✅ Schema verification passed")
            print("\nNext steps:")
            print("  1. Deploy PGP_*_v1 services to pgp-live")
            print("  2. Update Cloud Run service environment variables")
            print("  3. Test with sample transactions")
        else:
            print("⚠️  DEPLOYMENT COMPLETED WITH WARNINGS")
            print("=" * 80)
            print("\n✅ Migrations executed")
            print("⚠️  Schema verification found issues (see above)")
    else:
        print("\n" + "=" * 80)
        print("❌ DEPLOYMENT FAILED")
        print("=" * 80)
        sys.exit(1)

    # Close connection
    conn.close()
    print("\n✅ Database connection closed")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Deployment cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Deployment failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
