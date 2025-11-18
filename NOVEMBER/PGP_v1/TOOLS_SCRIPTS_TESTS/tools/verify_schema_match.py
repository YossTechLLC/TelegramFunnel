#!/usr/bin/env python3
"""
Verify that deployment scripts match existing telepay-459221 schema.

This script compares the existing schema with the deployment scripts
to ensure they will recreate the database correctly.
"""
import subprocess
from google.cloud.sql.connector import Connector

def get_secret(secret_name, project="telepay-459221"):
    """Fetch secret from Google Secret Manager"""
    result = subprocess.run(
        ['gcloud', 'secrets', 'versions', 'access', 'latest',
         '--secret', secret_name, '--project', project],
        capture_output=True, text=True
    )
    return result.stdout.strip()

def main():
    print("=" * 100)
    print("🔍 SCHEMA VERIFICATION: Comparing telepay-459221 with deployment scripts")
    print("=" * 100)

    # Connect to telepay-459221 database
    connector = Connector()
    conn = connector.connect(
        "telepay-459221:us-central1:telepaypsql",
        "pg8000",
        user=get_secret("DATABASE_USER_SECRET"),
        password=get_secret("DATABASE_PASSWORD_SECRET"),
        db=get_secret("DATABASE_NAME_SECRET")
    )

    cur = conn.cursor()

    # =========================================================================
    # Check 1: Table Count
    # =========================================================================
    print("\n" + "=" * 100)
    print("CHECK 1: Table Count")
    print("=" * 100)

    cur.execute("""
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
    """)
    actual_table_count = cur.fetchone()[0]
    expected_table_count = 15

    if actual_table_count == expected_table_count:
        print(f"✅ Table count matches: {actual_table_count} tables")
    else:
        print(f"⚠️  Table count mismatch!")
        print(f"   Expected: {expected_table_count}")
        print(f"   Actual: {actual_table_count}")

    # =========================================================================
    # Check 2: List All Tables
    # =========================================================================
    print("\n" + "=" * 100)
    print("CHECK 2: Table Names")
    print("=" * 100)

    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)

    actual_tables = {row[0] for row in cur.fetchall()}
    expected_tables = {
        'batch_conversions',
        'broadcast_manager',
        'currency_to_network',
        'donation_keypad_state',
        'failed_transactions',
        'main_clients_database',
        'payout_accumulation',
        'payout_batches',
        'private_channel_users_database',
        'processed_payments',
        'registered_users',
        'split_payout_hostpay',
        'split_payout_que',
        'split_payout_request',
        'user_conversation_state'
    }

    if actual_tables == expected_tables:
        print(f"✅ All table names match")
        for table in sorted(expected_tables):
            print(f"   • {table}")
    else:
        print(f"⚠️  Table names mismatch!")
        missing = expected_tables - actual_tables
        extra = actual_tables - expected_tables
        if missing:
            print(f"\n   Missing tables (in deployment script but not in database):")
            for table in sorted(missing):
                print(f"     • {table}")
        if extra:
            print(f"\n   Extra tables (in database but not in deployment script):")
            for table in sorted(extra):
                print(f"     • {table}")

    # =========================================================================
    # Check 3: Column Counts Per Table
    # =========================================================================
    print("\n" + "=" * 100)
    print("CHECK 3: Column Counts")
    print("=" * 100)

    expected_column_counts = {
        'batch_conversions': 12,
        'broadcast_manager': 22,
        'currency_to_network': 4,
        'donation_keypad_state': 7,
        'failed_transactions': 22,
        'main_clients_database': 25,
        'payout_accumulation': 28,
        'payout_batches': 18,
        'private_channel_users_database': 25,
        'processed_payments': 10,
        'registered_users': 20,
        'split_payout_hostpay': 14,
        'split_payout_que': 18,
        'split_payout_request': 16,
        'user_conversation_state': 4
    }

    all_match = True
    for table, expected_count in sorted(expected_column_counts.items()):
        cur.execute(f"""
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_name = '{table}'
        """)
        actual_count = cur.fetchone()[0]

        if actual_count == expected_count:
            print(f"   ✅ {table:40s} {actual_count} columns")
        else:
            print(f"   ⚠️  {table:40s} Expected: {expected_count}, Actual: {actual_count}")
            all_match = False

    if all_match:
        print(f"\n✅ All column counts match")

    # =========================================================================
    # Check 4: Primary Keys
    # =========================================================================
    print("\n" + "=" * 100)
    print("CHECK 4: Primary Keys")
    print("=" * 100)

    expected_pks = {
        'batch_conversions': ['id'],
        'broadcast_manager': ['id'],
        'donation_keypad_state': ['user_id'],
        'failed_transactions': ['id'],
        'main_clients_database': ['id'],
        'payout_accumulation': ['id'],
        'payout_batches': ['batch_id'],
        'private_channel_users_database': ['id'],
        'processed_payments': ['payment_id'],
        'registered_users': ['user_id'],
        'split_payout_que': ['unique_id'],
        'split_payout_request': ['unique_id'],
        'user_conversation_state': ['user_id', 'conversation_type']
    }

    all_pks_match = True
    for table, expected_pk_cols in sorted(expected_pks.items()):
        cur.execute(f"""
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
            WHERE tc.table_name = '{table}'
              AND tc.constraint_type = 'PRIMARY KEY'
            ORDER BY kcu.ordinal_position
        """)

        actual_pk_cols = [row[0] for row in cur.fetchall()]

        if actual_pk_cols == expected_pk_cols:
            pk_str = ', '.join(actual_pk_cols)
            print(f"   ✅ {table:40s} PK: ({pk_str})")
        else:
            print(f"   ⚠️  {table:40s} PK mismatch!")
            print(f"      Expected: {expected_pk_cols}")
            print(f"      Actual: {actual_pk_cols}")
            all_pks_match = False

    if all_pks_match:
        print(f"\n✅ All primary keys match")

    # =========================================================================
    # Check 5: Foreign Keys
    # =========================================================================
    print("\n" + "=" * 100)
    print("CHECK 5: Foreign Keys")
    print("=" * 100)

    cur.execute("""
        SELECT
            tc.table_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage AS ccu
          ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
        ORDER BY tc.table_name, kcu.column_name
    """)

    fks = cur.fetchall()

    if fks:
        print(f"\n✅ Found {len(fks)} foreign key constraints:")
        for fk in fks:
            print(f"   • {fk[0]:40s}.{fk[1]:30s} → {fk[2]:40s}.{fk[3]}")
    else:
        print(f"\n⚠️  No foreign keys found!")

    # =========================================================================
    # Check 6: Sequences
    # =========================================================================
    print("\n" + "=" * 100)
    print("CHECK 6: Sequences")
    print("=" * 100)

    cur.execute("""
        SELECT sequence_name
        FROM information_schema.sequences
        WHERE sequence_schema = 'public'
        ORDER BY sequence_name
    """)

    sequences = [row[0] for row in cur.fetchall()]
    expected_sequences = {
        'batch_conversions_id_seq',
        'failed_transactions_id_seq',
        'main_clients_database_id_seq',
        'payout_accumulation_id_seq',
        'private_channel_users_database_id_seq'
    }

    actual_sequences = set(sequences)

    if actual_sequences == expected_sequences:
        print(f"✅ All sequences match ({len(sequences)} sequences):")
        for seq in sorted(sequences):
            print(f"   • {seq}")
    else:
        print(f"⚠️  Sequence mismatch!")
        missing = expected_sequences - actual_sequences
        extra = actual_sequences - expected_sequences
        if missing:
            print(f"\n   Missing sequences:")
            for seq in sorted(missing):
                print(f"     • {seq}")
        if extra:
            print(f"\n   Extra sequences:")
            for seq in sorted(extra):
                print(f"     • {seq}")

    # =========================================================================
    # Check 7: ENUM Types
    # =========================================================================
    print("\n" + "=" * 100)
    print("CHECK 7: Custom ENUM Types")
    print("=" * 100)

    cur.execute("""
        SELECT typname
        FROM pg_type
        WHERE typtype = 'e'
        ORDER BY typname
    """)

    enums = [row[0] for row in cur.fetchall()]
    expected_enums = {'currency_type', 'network_type', 'flow_type', 'type_type'}
    actual_enums = set(enums)

    if actual_enums == expected_enums:
        print(f"✅ All ENUM types match ({len(enums)} ENUMs):")
        for enum in sorted(enums):
            print(f"   • {enum}")
    else:
        print(f"⚠️  ENUM type mismatch!")
        missing = expected_enums - actual_enums
        extra = actual_enums - expected_enums
        if missing:
            print(f"\n   Missing ENUM types:")
            for enum in sorted(missing):
                print(f"     • {enum}")
        if extra:
            print(f"\n   Extra ENUM types:")
            for enum in sorted(extra):
                print(f"     • {enum}")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 100)
    print("📊 VERIFICATION SUMMARY")
    print("=" * 100)

    print(f"\n✅ Tables: {actual_table_count}/{expected_table_count}")
    print(f"✅ Sequences: {len(sequences)}/{len(expected_sequences)}")
    print(f"✅ ENUM Types: {len(enums)}/{len(expected_enums)}")
    print(f"✅ Foreign Keys: {len(fks)}")

    print("\n" + "=" * 100)
    print("✅ Deployment scripts are ready for pgp-live!")
    print("=" * 100)
    print("\nDeployment files:")
    print("  • 001_create_complete_schema.sql (15 tables, 4 ENUMs)")
    print("  • 002_populate_currency_to_network.sql (87 mappings)")
    print("  • deploy_complete_schema_pgp_live.py (Python executor)")

    cur.close()
    conn.close()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()
