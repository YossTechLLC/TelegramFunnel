#!/usr/bin/env python
"""
Check if migration 002 has been run on production database
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.connection import DatabaseManager

def check_migration():
    """Check if migration 002 columns exist"""
    print("🔍 Checking if migration 002 has been run...")
    print("=" * 80)

    db_manager = DatabaseManager()

    try:
        with db_manager.get_db() as conn:
            cursor = conn.cursor()

            # Check for migration 002 columns
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'registered_users'
                AND column_name IN (
                    'pending_email',
                    'pending_email_token',
                    'pending_email_token_expires',
                    'pending_email_old_notification_sent',
                    'last_verification_resent_at',
                    'verification_resend_count',
                    'last_email_change_requested_at'
                )
                ORDER BY column_name;
            """)

            existing_columns = cursor.fetchall()
            expected_columns = [
                'last_email_change_requested_at',
                'last_verification_resent_at',
                'pending_email',
                'pending_email_old_notification_sent',
                'pending_email_token',
                'pending_email_token_expires',
                'verification_resend_count'
            ]

            print(f"\n📊 Migration 002 columns:")
            print(f"   Expected: {len(expected_columns)}")
            print(f"   Found: {len(existing_columns)}")

            if len(existing_columns) == len(expected_columns):
                print("\n✅ Migration 002 HAS been run on this database!")
                print("\n   Columns found:")
                for col in existing_columns:
                    print(f"   - {col[0]}")
                return True
            else:
                print("\n❌ Migration 002 has NOT been run on this database!")
                print("\n   Missing columns:")
                found_names = {col[0] for col in existing_columns}
                for expected in expected_columns:
                    if expected not in found_names:
                        print(f"   - {expected}")
                return False

    except Exception as e:
        print(f"\n❌ Error checking migration: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = check_migration()
    sys.exit(0 if result else 1)
