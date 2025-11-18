#!/usr/bin/env python3
"""
PayGatePrime PGP-LIVE Schema Rollback Tool
=========================================
Project: pgp-live
Database: telepaydb
Instance: pgp-live:us-central1:pgp-telepaypsql

⚠️⚠️⚠️ WARNING: THIS WILL DELETE ALL DATA ⚠️⚠️⚠️

This script rolls back the pgp-live database schema by dropping all 13 tables.

Usage:
    python3 rollback_pgp_live_schema.py

Safety:
    • Requires typing "DELETE ALL DATA" to confirm
    • Triple confirmation prompt
    • No dry-run mode (too dangerous)
"""

import sys
from pathlib import Path
from datetime import datetime
from google.cloud import secretmanager
from google.cloud.sql.connector import Connector
import sqlalchemy
from sqlalchemy import text

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

# Project Configuration
PROJECT_ID = "pgp-live"
INSTANCE_CONNECTION_NAME = "pgp-live:us-central1:pgp-telepaypsql"
DATABASE_NAME = "telepaydb"

# Migration Files
MIGRATION_DIR = Path(__file__).parent.parent / "migrations" / "pgp-live"
ROLLBACK_FILE = MIGRATION_DIR / "001_pgp_live_rollback.sql"


def print_banner(message: str, emoji: str = "🔧"):
    """Print a formatted banner message"""
    print(f"\n{'=' * 80}")
    print(f"{emoji}  {message}")
    print('=' * 80)


def get_secret(secret_id: str) -> str:
    """Retrieve secret from Google Secret Manager"""
    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"❌ Error retrieving secret {secret_id}: {e}")
        sys.exit(1)


def get_database_connection():
    """Create database connection using Cloud SQL Python Connector"""
    print("⏳ Establishing database connection...")

    try:
        # Get database credentials from Secret Manager
        db_user = get_secret("DATABASE_USER_SECRET")
        db_password = get_secret("DATABASE_PASSWORD_SECRET")

        # Initialize Cloud SQL Python Connector
        connector = Connector()

        def getconn():
            return connector.connect(
                INSTANCE_CONNECTION_NAME,
                "pg8000",
                user=db_user,
                password=db_password,
                db=DATABASE_NAME
            )

        # Create SQLAlchemy engine
        engine = sqlalchemy.create_engine(
            "postgresql+pg8000://",
            creator=getconn,
        )

        print("✅ Database connection established")
        return engine, connector

    except Exception as e:
        print(f"❌ Error connecting to database: {e}")
        sys.exit(1)


def read_sql_file(file_path: Path) -> str:
    """Read SQL file and return contents"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"❌ Error: SQL file not found: {file_path}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error reading SQL file {file_path}: {e}")
        sys.exit(1)


def get_table_count(engine) -> int:
    """Get current table count"""
    try:
        with engine.connect() as connection:
            result = connection.execute(text("""
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
            """))
            return result.scalar()
    except Exception as e:
        print(f"⚠️  Warning: Could not count tables: {e}")
        return 0


def triple_confirmation() -> bool:
    """Require triple confirmation before rollback"""
    print_banner("⚠️⚠️⚠️ DANGER ZONE ⚠️⚠️⚠️", "🚨")

    print("\n🔥 THIS WILL DELETE ALL DATA IN THE DATABASE 🔥")
    print("\nThe following will be PERMANENTLY DELETED:")
    print("  • 13 tables (all data)")
    print("  • 4 ENUM types")
    print("  • 5 sequences")
    print("  • All indexes")
    print("  • All foreign keys")
    print("\n⚠️  THIS CANNOT BE UNDONE ⚠️")

    # First confirmation
    print("\n" + "─" * 80)
    response1 = input("❓ Do you really want to delete all data? (yes/no): ").strip().lower()
    if response1 not in ['yes', 'y']:
        return False

    # Second confirmation
    print("\n" + "─" * 80)
    print("⚠️  SECOND WARNING: This will delete ALL data in pgp-live database")
    response2 = input("❓ Are you absolutely sure? (yes/no): ").strip().lower()
    if response2 not in ['yes', 'y']:
        return False

    # Third confirmation - must type exact phrase
    print("\n" + "─" * 80)
    print("⚠️  FINAL WARNING: Type 'DELETE ALL DATA' (exact match, case-sensitive)")
    response3 = input("❓ Confirmation phrase: ").strip()
    if response3 != "DELETE ALL DATA":
        print(f"\n❌ Incorrect phrase: '{response3}'")
        print("   Expected: 'DELETE ALL DATA'")
        return False

    return True


def rollback_schema():
    """Main rollback function"""
    print_banner("PayGatePrime PGP-LIVE Schema Rollback", "🔙")

    print(f"\n📋 Rollback Configuration:")
    print(f"   Project ID: {PROJECT_ID}")
    print(f"   Instance: {INSTANCE_CONNECTION_NAME}")
    print(f"   Database: {DATABASE_NAME}")
    print(f"   Rollback File: {ROLLBACK_FILE.name}")

    # Verify rollback file exists
    if not ROLLBACK_FILE.exists():
        print(f"\n❌ Error: Rollback file not found: {ROLLBACK_FILE}")
        sys.exit(1)

    print("\n✅ Rollback file validated")

    # Get triple confirmation
    if not triple_confirmation():
        print("\n❌ Rollback cancelled by user")
        print("   No changes were made to the database")
        sys.exit(0)

    # Connect to database
    engine, connector = get_database_connection()

    try:
        # Get table count before rollback
        table_count_before = get_table_count(engine)
        print(f"\n📊 Current table count: {table_count_before}")

        if table_count_before == 0:
            print("\n⚠️  No tables found - database may already be empty")
            response = input("❓ Continue anyway? (yes/no): ").strip().lower()
            if response not in ['yes', 'y']:
                print("❌ Rollback cancelled")
                sys.exit(0)

        # Read rollback SQL
        print_banner("Executing Rollback", "⚙️")
        rollback_sql = read_sql_file(ROLLBACK_FILE)

        print(f"⏳ Dropping 13 tables, 4 ENUMs, 5 sequences...")

        start_time = datetime.now()

        # Execute rollback
        try:
            with engine.connect() as connection:
                connection.execute(text(rollback_sql))
                connection.commit()

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            print("✅ Rollback SQL executed successfully")

            # Verify tables were dropped
            table_count_after = get_table_count(engine)
            tables_dropped = table_count_before - table_count_after

            # Print summary
            print_banner("Rollback Summary", "📊")
            print(f"\n{'Tables before:':<25} {table_count_before}")
            print(f"{'Tables after:':<25} {table_count_after}")
            print(f"{'Tables dropped:':<25} {tables_dropped}")
            print(f"{'Duration:':<25} {duration:.2f} seconds")
            print(f"{'Timestamp:':<25} {end_time.strftime('%Y-%m-%d %H:%M:%S')}")

            print("\n✅ PGP-LIVE schema rollback completed successfully!")
            print("\n📋 Database is now empty (13 tables removed)")
            print("   You can re-deploy using deploy_pgp_live_schema.py")

        except Exception as e:
            print(f"\n❌ Rollback failed: {e}")
            print("   Database may be in an inconsistent state")
            print("   Check the database manually and retry if needed")
            sys.exit(1)

    finally:
        # Close connector
        connector.close()
        print("\n✅ Database connection closed")


def main():
    """Main entry point"""
    try:
        rollback_schema()
    except KeyboardInterrupt:
        print("\n\n❌ Rollback cancelled by user (Ctrl+C)")
        print("   No changes were made to the database")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
