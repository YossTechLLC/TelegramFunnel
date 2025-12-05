#!/usr/bin/env python3
"""
PayGatePrime PGP-LIVE Schema Deployment Tool
===========================================
Project: pgp-live
Database: telepaydb
Instance: pgp-live:us-central1:pgp-telepaypsql

This script deploys the complete 13-table schema to pgp-live database.

Usage:
    python3 deploy_pgp_live_schema.py [--dry-run] [--skip-confirmation]

Options:
    --dry-run           Print SQL without executing (default: False)
    --skip-confirmation Skip user confirmation prompt (default: False)
"""

import sys
import os
import argparse
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
SCHEMA_FILE = MIGRATION_DIR / "001_pgp_live_complete_schema.sql"
POPULATION_FILE = MIGRATION_DIR / "002_pgp_live_populate_currency_to_network.sql"


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


def execute_sql(engine, sql: str, description: str, dry_run: bool = False):
    """Execute SQL statement with error handling"""
    if dry_run:
        print(f"🔍 DRY RUN - Would execute: {description}")
        print(f"{'─' * 80}")
        print(sql[:500] + ("..." if len(sql) > 500 else ""))
        print(f"{'─' * 80}\n")
        return True

    try:
        print(f"⏳ {description}...")
        with engine.connect() as connection:
            connection.execute(text(sql))
            connection.commit()
        print(f"✅ {description} - SUCCESS")
        return True
    except Exception as e:
        print(f"❌ {description} - FAILED")
        print(f"   Error: {e}")
        return False


def check_schema_exists(engine) -> bool:
    """Check if schema already exists"""
    try:
        with engine.connect() as connection:
            result = connection.execute(text("""
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN (
                      'registered_users', 'main_clients_database',
                      'private_channel_users_database'
                  )
            """))
            count = result.scalar()
            return count > 0
    except Exception as e:
        print(f"⚠️  Warning: Could not check existing schema: {e}")
        return False


def deploy_schema(dry_run: bool = False, skip_confirmation: bool = False):
    """Main deployment function"""
    print_banner("PayGatePrime PGP-LIVE Schema Deployment", "🚀")

    print(f"\n📋 Deployment Configuration:")
    print(f"   Project ID: {PROJECT_ID}")
    print(f"   Instance: {INSTANCE_CONNECTION_NAME}")
    print(f"   Database: {DATABASE_NAME}")
    print(f"   Schema File: {SCHEMA_FILE.name}")
    print(f"   Population File: {POPULATION_FILE.name}")
    print(f"   Dry Run: {dry_run}")
    print(f"   Tables: 13 (excluding donation_keypad_state, user_conversation_state)")

    # Verify migration files exist
    if not SCHEMA_FILE.exists():
        print(f"\n❌ Error: Schema file not found: {SCHEMA_FILE}")
        sys.exit(1)
    if not POPULATION_FILE.exists():
        print(f"\n❌ Error: Population file not found: {POPULATION_FILE}")
        sys.exit(1)

    print("\n✅ Migration files validated")

    # Get user confirmation (unless skipped or dry-run)
    if not dry_run and not skip_confirmation:
        print_banner("⚠️  CONFIRMATION REQUIRED", "⚠️")
        print("\nThis will create/modify the following in pgp-live database:")
        print("  • 13 core operational tables")
        print("  • 4 custom ENUM types")
        print("  • 60+ indexes for performance")
        print("  • 3 foreign key relationships")
        print("  • 87 currency/network mappings")
        print("  • 1 legacy system user")
        print("\nDoes NOT include: donation_keypad_state, user_conversation_state")

        response = input("\n❓ Proceed with deployment? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("❌ Deployment cancelled by user")
            sys.exit(0)

    # Connect to database
    engine, connector = get_database_connection()

    try:
        # Check if schema already exists
        if check_schema_exists(engine):
            print("\n⚠️  WARNING: Some tables already exist in the database")
            if not dry_run and not skip_confirmation:
                response = input("❓ Continue anyway? (yes/no): ").strip().lower()
                if response not in ['yes', 'y']:
                    print("❌ Deployment cancelled by user")
                    sys.exit(0)

        # Read migration files
        print_banner("Reading Migration Files", "📖")
        schema_sql = read_sql_file(SCHEMA_FILE)
        population_sql = read_sql_file(POPULATION_FILE)

        print(f"✅ Read {SCHEMA_FILE.name} ({len(schema_sql)} bytes)")
        print(f"✅ Read {POPULATION_FILE.name} ({len(population_sql)} bytes)")

        # Execute migrations
        print_banner("Executing Migrations", "⚙️")

        start_time = datetime.now()

        # Step 1: Deploy schema
        success = execute_sql(
            engine,
            schema_sql,
            "Deploying PGP-LIVE schema (13 tables, 4 ENUMs)",
            dry_run
        )

        if not success and not dry_run:
            print("\n❌ Schema deployment failed. Aborting.")
            sys.exit(1)

        # Step 2: Populate currency_to_network
        success = execute_sql(
            engine,
            population_sql,
            "Populating currency_to_network (87 mappings)",
            dry_run
        )

        if not success and not dry_run:
            print("\n⚠️  Warning: Currency population failed, but schema was created")

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Print summary
        print_banner("Deployment Summary", "📊")
        print(f"\n{'Deployment Type:':<25} {'DRY RUN' if dry_run else 'LIVE DEPLOYMENT'}")
        print(f"{'Duration:':<25} {duration:.2f} seconds")
        print(f"{'Timestamp:':<25} {end_time.strftime('%Y-%m-%d %H:%M:%S')}")

        if not dry_run:
            print("\n✅ PGP-LIVE schema deployment completed successfully!")
            print("\n📋 Next Steps:")
            print("   1. Run verify_pgp_live_schema.py to validate deployment")
            print("   2. Update service code references from 'client_table' to 'pgp_live_db'")
            print("   3. Test service connections to pgp-live database")
        else:
            print("\n🔍 DRY RUN completed - No changes were made to the database")
            print("   Remove --dry-run flag to execute deployment")

    finally:
        # Close connector
        connector.close()
        print("\n✅ Database connection closed")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Deploy PGP-LIVE database schema (13 tables)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print SQL without executing (default: False)'
    )
    parser.add_argument(
        '--skip-confirmation',
        action='store_true',
        help='Skip user confirmation prompt (default: False)'
    )

    args = parser.parse_args()

    try:
        deploy_schema(
            dry_run=args.dry_run,
            skip_confirmation=args.skip_confirmation
        )
    except KeyboardInterrupt:
        print("\n\n❌ Deployment cancelled by user (Ctrl+C)")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
