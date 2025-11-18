#!/usr/bin/env python3
"""
Extract complete database schema from telepay-459221:telepaypsql.
This will be used to create deployment scripts for pgp-live.
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
    print("🔍 Extracting Complete Schema from telepay-459221:telepaypsql")
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

    # ============================================================================
    # STEP 1: List ALL tables
    # ============================================================================
    print("\n📋 STEP 1: ALL TABLES IN DATABASE")
    print("=" * 100)
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)

    tables = [row[0] for row in cur.fetchall()]
    print(f"\n✅ Found {len(tables)} tables:\n")
    for i, table in enumerate(tables, 1):
        print(f"  {i:2d}. {table}")

    # ============================================================================
    # STEP 2: Extract schema for each table
    # ============================================================================
    print("\n" + "=" * 100)
    print("📊 STEP 2: DETAILED SCHEMA FOR EACH TABLE")
    print("=" * 100)

    for table in tables:
        print(f"\n{'=' * 100}")
        print(f"TABLE: {table}")
        print("=" * 100)

        # Get columns
        cur.execute("""
            SELECT
                column_name,
                data_type,
                character_maximum_length,
                numeric_precision,
                numeric_scale,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """, (table,))

        columns = cur.fetchall()
        print(f"\n📌 Columns ({len(columns)}):")
        print("-" * 100)
        for col in columns:
            col_name = col[0]
            data_type = col[1]
            max_len = col[2]
            num_precision = col[3]
            num_scale = col[4]
            nullable = "NULL" if col[5] == "YES" else "NOT NULL"
            default = col[6] or "None"

            # Format data type with size/precision
            if data_type == 'character varying' and max_len:
                dtype_display = f"VARCHAR({max_len})"
            elif data_type == 'numeric' and num_precision:
                if num_scale:
                    dtype_display = f"NUMERIC({num_precision}, {num_scale})"
                else:
                    dtype_display = f"NUMERIC({num_precision})"
            elif data_type == 'character' and max_len:
                dtype_display = f"CHAR({max_len})"
            else:
                dtype_display = data_type.upper()

            print(f"  {col_name:40s} {dtype_display:25s} {nullable:10s} DEFAULT: {default}")

        # Get primary key
        cur.execute("""
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
            WHERE tc.table_name = %s
              AND tc.constraint_type = 'PRIMARY KEY'
        """, (table,))

        pk_cols = cur.fetchall()
        if pk_cols:
            pk_list = ", ".join([row[0] for row in pk_cols])
            print(f"\n🔑 Primary Key: {pk_list}")

        # Get foreign keys
        cur.execute("""
            SELECT
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name,
                rc.update_rule,
                rc.delete_rule
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
            JOIN information_schema.referential_constraints AS rc
              ON rc.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_name = %s
        """, (table,))

        fks = cur.fetchall()
        if fks:
            print(f"\n🔗 Foreign Keys:")
            for fk in fks:
                print(f"  {fk[0]} -> {fk[1]}.{fk[2]} (ON UPDATE {fk[3]}, ON DELETE {fk[4]})")

        # Get unique constraints
        cur.execute("""
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
            WHERE tc.table_name = %s
              AND tc.constraint_type = 'UNIQUE'
        """, (table,))

        unique_cols = cur.fetchall()
        if unique_cols:
            print(f"\n🎯 Unique Constraints:")
            for uc in unique_cols:
                print(f"  {uc[0]}")

        # Get check constraints
        cur.execute("""
            SELECT
                cc.constraint_name,
                cc.check_clause
            FROM information_schema.check_constraints cc
            JOIN information_schema.table_constraints tc
              ON cc.constraint_name = tc.constraint_name
            WHERE tc.table_name = %s
        """, (table,))

        checks = cur.fetchall()
        if checks:
            print(f"\n✓ Check Constraints:")
            for check in checks:
                print(f"  {check[0]}: {check[1]}")

        # Get indexes
        cur.execute("""
            SELECT
                indexname,
                indexdef
            FROM pg_indexes
            WHERE tablename = %s
              AND schemaname = 'public'
        """, (table,))

        indexes = cur.fetchall()
        if indexes:
            print(f"\n📑 Indexes:")
            for idx in indexes:
                print(f"  {idx[0]}")
                print(f"    {idx[1]}")

        # Get row count
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        row_count = cur.fetchone()[0]
        print(f"\n📊 Row Count: {row_count:,}")

    # ============================================================================
    # STEP 3: Get sequences
    # ============================================================================
    print("\n" + "=" * 100)
    print("🔢 STEP 3: SEQUENCES")
    print("=" * 100)

    cur.execute("""
        SELECT sequence_name
        FROM information_schema.sequences
        WHERE sequence_schema = 'public'
        ORDER BY sequence_name
    """)

    sequences = cur.fetchall()
    if sequences:
        for seq in sequences:
            print(f"  {seq[0]}")
    else:
        print("  No sequences found")

    # ============================================================================
    # STEP 4: Summary
    # ============================================================================
    print("\n" + "=" * 100)
    print("📈 SUMMARY")
    print("=" * 100)
    print(f"  Total Tables: {len(tables)}")
    print(f"  Total Sequences: {len(sequences)}")
    print("\n  Tables List:")
    for table in tables:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"    • {table:50s} ({count:,} rows)")

    cur.close()
    conn.close()

    print("\n" + "=" * 100)
    print("✅ Schema extraction complete!")
    print("=" * 100)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
