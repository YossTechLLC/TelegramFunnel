#!/usr/bin/env python3
"""
PayGatePrime PGP-LIVE Schema Verification Tool
=============================================
Project: pgp-live
Database: telepaydb
Instance: pgp-live:us-central1:pgp-telepaypsql

This script verifies that the pgp-live database schema was deployed correctly.

Usage:
    python3 verify_pgp_live_schema.py

Expected Schema:
    • 13 tables (excluding donation_keypad_state, user_conversation_state)
    • 4 custom ENUM types
    • 60+ indexes
    • 3 foreign keys
    • 5 sequences
    • 87 currency/network mappings
    • 1 legacy system user
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

# Expected Schema Configuration
EXPECTED_TABLES = {
    'registered_users',
    'main_clients_database',
    'private_channel_users_database',
    'processed_payments',
    'batch_conversions',
    'payout_accumulation',
    'payout_batches',
    'split_payout_request',
    'split_payout_que',
    'split_payout_hostpay',
    'broadcast_manager',
    'currency_to_network',
    'failed_transactions'
}

EXCLUDED_TABLES = {'donation_keypad_state', 'user_conversation_state'}

EXPECTED_ENUMS = {'currency_type', 'network_type', 'flow_type', 'type_type'}

EXPECTED_SEQUENCES = {
    'batch_conversions_id_seq',
    'failed_transactions_id_seq',
    'main_clients_database_id_seq',
    'payout_accumulation_id_seq',
    'private_channel_users_database_id_seq'
}


def print_banner(message: str, emoji: str = "🔍"):
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

        print("✅ Database connection established\n")
        return engine, connector

    except Exception as e:
        print(f"❌ Error connecting to database: {e}")
        sys.exit(1)


def run_verification_query(engine, query: str, description: str):
    """Run a verification query and return results"""
    try:
        with engine.connect() as connection:
            result = connection.execute(text(query))
            return result.fetchall()
    except Exception as e:
        print(f"❌ Error executing {description}: {e}")
        return None


def verify_tables(engine) -> tuple[bool, list]:
    """Verify table count and names"""
    print_banner("Verifying Tables", "📋")

    query = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """

    results = run_verification_query(engine, query, "table verification")
    if results is None:
        return False, []

    actual_tables = {row[0] for row in results}

    print(f"Expected tables: {len(EXPECTED_TABLES)}")
    print(f"Found tables: {len(actual_tables)}")

    issues = []

    # Check for missing tables
    missing = EXPECTED_TABLES - actual_tables
    if missing:
        print(f"\n❌ Missing tables ({len(missing)}):")
        for table in sorted(missing):
            print(f"   • {table}")
            issues.append(f"Missing table: {table}")

    # Check for unexpected tables
    unexpected = actual_tables - EXPECTED_TABLES - EXCLUDED_TABLES
    if unexpected:
        print(f"\n⚠️  Unexpected tables ({len(unexpected)}):")
        for table in sorted(unexpected):
            print(f"   • {table}")

    # Check for deprecated tables that should NOT exist
    deprecated_found = actual_tables & EXCLUDED_TABLES
    if deprecated_found:
        print(f"\n❌ Found deprecated tables (should be excluded):")
        for table in sorted(deprecated_found):
            print(f"   • {table}")
            issues.append(f"Deprecated table found: {table}")

    if not issues:
        print("\n✅ All expected tables present, no deprecated tables")
        print("\nTable List:")
        for table in sorted(actual_tables):
            status = "✅" if table in EXPECTED_TABLES else "⚠️"
            print(f"   {status} {table}")

    return len(issues) == 0, issues


def verify_enums(engine) -> tuple[bool, list]:
    """Verify custom ENUM types"""
    print_banner("Verifying ENUM Types", "🔐")

    query = """
        SELECT typname
        FROM pg_type
        WHERE typtype = 'e'
        ORDER BY typname
    """

    results = run_verification_query(engine, query, "ENUM verification")
    if results is None:
        return False, []

    actual_enums = {row[0] for row in results}

    print(f"Expected ENUMs: {len(EXPECTED_ENUMS)}")
    print(f"Found ENUMs: {len(actual_enums)}")

    issues = []

    # Check for missing ENUMs
    missing = EXPECTED_ENUMS - actual_enums
    if missing:
        print(f"\n❌ Missing ENUM types ({len(missing)}):")
        for enum in sorted(missing):
            print(f"   • {enum}")
            issues.append(f"Missing ENUM: {enum}")

    if not issues:
        print("\n✅ All expected ENUM types present")
        print("\nENUM List:")
        for enum in sorted(actual_enums):
            status = "✅" if enum in EXPECTED_ENUMS else "⚠️"
            print(f"   {status} {enum}")

    return len(issues) == 0, issues


def verify_indexes(engine) -> tuple[bool, list]:
    """Verify index count"""
    print_banner("Verifying Indexes", "⚡")

    query = """
        SELECT COUNT(DISTINCT indexname)
        FROM pg_indexes
        WHERE schemaname = 'public'
    """

    results = run_verification_query(engine, query, "index verification")
    if results is None:
        return False, []

    index_count = results[0][0]

    print(f"Expected indexes: 60+")
    print(f"Found indexes: {index_count}")

    issues = []

    if index_count < 60:
        print(f"\n⚠️  Warning: Expected at least 60 indexes, found {index_count}")
        issues.append(f"Low index count: {index_count} (expected 60+)")
    else:
        print("\n✅ Index count meets expectations")

    return len(issues) == 0, issues


def verify_foreign_keys(engine) -> tuple[bool, list]:
    """Verify foreign key constraints"""
    print_banner("Verifying Foreign Keys", "🔗")

    query = """
        SELECT COUNT(*)
        FROM information_schema.table_constraints
        WHERE constraint_schema = 'public'
          AND constraint_type = 'FOREIGN KEY'
    """

    results = run_verification_query(engine, query, "foreign key verification")
    if results is None:
        return False, []

    fk_count = results[0][0]

    print(f"Expected foreign keys: 3")
    print(f"Found foreign keys: {fk_count}")

    issues = []

    if fk_count != 3:
        print(f"\n⚠️  Warning: Expected 3 foreign keys, found {fk_count}")
        issues.append(f"Foreign key count mismatch: {fk_count} (expected 3)")
    else:
        print("\n✅ Foreign key count correct")

    return len(issues) == 0, issues


def verify_sequences(engine) -> tuple[bool, list]:
    """Verify sequences"""
    print_banner("Verifying Sequences", "🔢")

    query = """
        SELECT sequencename
        FROM pg_sequences
        WHERE schemaname = 'public'
        ORDER BY sequencename
    """

    results = run_verification_query(engine, query, "sequence verification")
    if results is None:
        return False, []

    actual_sequences = {row[0] for row in results}

    print(f"Expected sequences: {len(EXPECTED_SEQUENCES)}")
    print(f"Found sequences: {len(actual_sequences)}")

    issues = []

    # Check for missing sequences
    missing = EXPECTED_SEQUENCES - actual_sequences
    if missing:
        print(f"\n❌ Missing sequences ({len(missing)}):")
        for seq in sorted(missing):
            print(f"   • {seq}")
            issues.append(f"Missing sequence: {seq}")

    if not issues:
        print("\n✅ All expected sequences present")
        print("\nSequence List:")
        for seq in sorted(actual_sequences):
            status = "✅" if seq in EXPECTED_SEQUENCES else "⚠️"
            print(f"   {status} {seq}")

    return len(issues) == 0, issues


def verify_currency_data(engine) -> tuple[bool, list]:
    """Verify currency_to_network data"""
    print_banner("Verifying Currency Data", "💱")

    query = """
        SELECT COUNT(*)
        FROM currency_to_network
    """

    results = run_verification_query(engine, query, "currency data verification")
    if results is None:
        return False, []

    row_count = results[0][0]

    print(f"Expected currency mappings: 87")
    print(f"Found currency mappings: {row_count}")

    issues = []

    if row_count != 87:
        print(f"\n❌ Currency mapping count mismatch")
        issues.append(f"Currency mapping count: {row_count} (expected 87)")
    else:
        print("\n✅ Currency mapping count correct")

    return len(issues) == 0, issues


def verify_legacy_user(engine) -> tuple[bool, list]:
    """Verify legacy system user exists"""
    print_banner("Verifying Legacy User", "👤")

    query = """
        SELECT username, email
        FROM registered_users
        WHERE user_id = '00000000-0000-0000-0000-000000000000'
    """

    results = run_verification_query(engine, query, "legacy user verification")
    if results is None:
        return False, []

    issues = []

    if len(results) == 0:
        print("❌ Legacy system user not found")
        issues.append("Legacy system user missing (00000000-0000-0000-0000-000000000000)")
    elif results[0][0] != 'legacy_system':
        print(f"⚠️  Legacy user found but username is '{results[0][0]}' (expected 'legacy_system')")
        issues.append(f"Legacy username mismatch: {results[0][0]}")
    else:
        print("✅ Legacy system user exists")
        print(f"   Username: {results[0][0]}")
        print(f"   Email: {results[0][1]}")

    return len(issues) == 0, issues


def verify_schema():
    """Main verification function"""
    print_banner("PayGatePrime PGP-LIVE Schema Verification", "🔍")

    print(f"\n📋 Verification Configuration:")
    print(f"   Project ID: {PROJECT_ID}")
    print(f"   Instance: {INSTANCE_CONNECTION_NAME}")
    print(f"   Database: {DATABASE_NAME}")
    print(f"   Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Connect to database
    engine, connector = get_database_connection()

    all_passed = True
    all_issues = []

    try:
        # Run all verifications
        checks = [
            ("Tables", verify_tables),
            ("ENUM Types", verify_enums),
            ("Indexes", verify_indexes),
            ("Foreign Keys", verify_foreign_keys),
            ("Sequences", verify_sequences),
            ("Currency Data", verify_currency_data),
            ("Legacy User", verify_legacy_user)
        ]

        results = {}
        for name, check_func in checks:
            passed, issues = check_func(engine)
            results[name] = passed
            all_passed = all_passed and passed
            all_issues.extend(issues)

        # Print summary
        print_banner("Verification Summary", "📊")

        for name in results:
            status = "✅ PASS" if results[name] else "❌ FAIL"
            print(f"   {status:12} {name}")

        if all_passed:
            print("\n✅ All verifications passed!")
            print("   PGP-LIVE schema is correctly deployed")
            return 0
        else:
            print(f"\n❌ Verification failed with {len(all_issues)} issue(s):")
            for i, issue in enumerate(all_issues, 1):
                print(f"   {i}. {issue}")
            return 1

    finally:
        # Close connector
        connector.close()
        print("\n✅ Database connection closed")


def main():
    """Main entry point"""
    try:
        exit_code = verify_schema()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n❌ Verification cancelled by user (Ctrl+C)")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
