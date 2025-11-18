#!/usr/bin/env python
"""
Run database migration 002: Add Email Change Support
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.connection import DatabaseManager

def run_migration():
    """Execute migration 002: Add email change support and verification rate limiting"""
    print("🔧 Starting database migration 002...")
    print("=" * 80)
    print("Migration: Add Email Change Support and Verification Rate Limiting")
    print("=" * 80)

    # Read migration file
    migration_file = os.path.join(
        os.path.dirname(__file__),
        'database',
        'migrations',
        '002_add_email_change_support.sql'
    )

    print(f"\n📄 Reading migration from: {migration_file}")

    with open(migration_file, 'r') as f:
        migration_sql = f.read()

    # Initialize database manager
    print("🔌 Connecting to database...")
    db_manager = DatabaseManager()

    try:
        with db_manager.get_db() as conn:
            cursor = conn.cursor()

            print("\n📋 Current schema before migration:")
            cursor.execute("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = 'registered_users'
                ORDER BY ordinal_position;
            """)
            columns_before = cursor.fetchall()
            print(f"   Existing columns: {len(columns_before)}")

            print("\n🔄 Executing migration...")

            # Execute the full migration SQL
            cursor.execute(migration_sql)

            # Commit transaction
            conn.commit()
            print("   ✅ Migration SQL executed successfully")

            print("\n📋 Schema after migration:")
            cursor.execute("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = 'registered_users'
                ORDER BY ordinal_position;
            """)
            columns_after = cursor.fetchall()
            print(f"   Total columns: {len(columns_after)}")
            print(f"   New columns added: {len(columns_after) - len(columns_before)}")

            # Show new columns
            new_column_names = {col[0] for col in columns_after} - {col[0] for col in columns_before}
            if new_column_names:
                print("\n✨ New columns added:")
                for col_name in sorted(new_column_names):
                    col_info = next(c for c in columns_after if c[0] == col_name)
                    print(f"   - {col_info[0]} ({col_info[1]}) - Nullable: {col_info[2]}")
            else:
                print("\n⚠️  No new columns (they may have already existed)")

            # Verify indexes
            print("\n🔍 Verifying indexes...")
            cursor.execute("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'registered_users'
                AND indexname LIKE 'idx_%';
            """)
            indexes = cursor.fetchall()
            print(f"\nFound {len(indexes)} custom indexes:")
            for idx_name, idx_def in indexes:
                print(f"   - {idx_name}")

            # Verify constraints
            print("\n🔍 Verifying constraints...")
            cursor.execute("""
                SELECT conname, contype, pg_get_constraintdef(oid) as definition
                FROM pg_constraint
                WHERE conrelid = 'registered_users'::regclass
                ORDER BY conname;
            """)
            constraints = cursor.fetchall()
            print(f"\nFound {len(constraints)} constraints:")
            for name, ctype, definition in constraints:
                constraint_type = {
                    'c': 'CHECK',
                    'u': 'UNIQUE',
                    'p': 'PRIMARY KEY',
                    'f': 'FOREIGN KEY'
                }.get(ctype, ctype)
                print(f"   - {name} ({constraint_type})")

            cursor.close()

            print("\n" + "=" * 80)
            print("✅ Migration 002 completed successfully!")
            print("=" * 80)

            print("\n📊 Summary of changes:")
            print("   ✅ Added columns for pending email changes")
            print("   ✅ Added columns for verification rate limiting")
            print("   ✅ Added indexes for performance")
            print("   ✅ Added constraints for data integrity")

            print("\n🎯 Next steps:")
            print("   1. Deploy updated application code")
            print("   2. Test email change flow in staging")
            print("   3. Test verification resend rate limiting")
            print("   4. Monitor logs for constraint violations")

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    run_migration()
