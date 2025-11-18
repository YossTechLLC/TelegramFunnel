#!/usr/bin/env python
"""
Run database migration to fix duplicate users and add UNIQUE constraints
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.connection import DatabaseManager

def run_migration():
    """Execute the migration SQL"""
    print("🔧 Starting database migration...")
    print("=" * 80)

    # Read migration file
    migration_file = os.path.join(
        os.path.dirname(__file__),
        'database',
        'migrations',
        'fix_duplicate_users_add_unique_constraints.sql'
    )

    print(f"📄 Reading migration from: {migration_file}")

    with open(migration_file, 'r') as f:
        migration_sql = f.read()

    # Initialize database manager
    print("🔌 Connecting to database...")
    db_manager = DatabaseManager()

    try:
        # Execute migration
        with db_manager.get_db() as conn:
            cursor = conn.cursor()

            print("🗑️  Cleaning up duplicate usernames...")
            # Delete duplicate usernames (keep most recent)
            cursor.execute("""
                DELETE FROM registered_users
                WHERE user_id IN (
                    SELECT user_id
                    FROM (
                        SELECT user_id,
                               ROW_NUMBER() OVER (
                                   PARTITION BY username
                                   ORDER BY created_at DESC, user_id DESC
                               ) as rn
                        FROM registered_users
                    ) duplicates
                    WHERE rn > 1
                )
                RETURNING user_id, username;
            """)
            deleted_usernames = cursor.fetchall()
            print(f"   Deleted {len(deleted_usernames)} duplicate username records")
            for user_id, username in deleted_usernames:
                print(f"   - Deleted user_id: {user_id} (username: {username})")

            print("\n🗑️  Cleaning up duplicate emails...")
            # Delete duplicate emails (keep most recent)
            cursor.execute("""
                DELETE FROM registered_users
                WHERE user_id IN (
                    SELECT user_id
                    FROM (
                        SELECT user_id,
                               ROW_NUMBER() OVER (
                                   PARTITION BY email
                                   ORDER BY created_at DESC, user_id DESC
                               ) as rn
                        FROM registered_users
                    ) duplicates
                    WHERE rn > 1
                )
                RETURNING user_id, email;
            """)
            deleted_emails = cursor.fetchall()
            print(f"   Deleted {len(deleted_emails)} duplicate email records")
            for user_id, email in deleted_emails:
                print(f"   - Deleted user_id: {user_id} (email: {email})")

            print("\n🔒 Adding UNIQUE constraint on username...")
            try:
                cursor.execute("""
                    ALTER TABLE registered_users
                    ADD CONSTRAINT unique_username UNIQUE (username);
                """)
                print("   ✅ UNIQUE constraint added to username column")
            except Exception as e:
                if "already exists" in str(e).lower():
                    print("   ⚠️  UNIQUE constraint already exists on username column")
                else:
                    raise

            print("\n🔒 Adding UNIQUE constraint on email...")
            try:
                cursor.execute("""
                    ALTER TABLE registered_users
                    ADD CONSTRAINT unique_email UNIQUE (email);
                """)
                print("   ✅ UNIQUE constraint added to email column")
            except Exception as e:
                if "already exists" in str(e).lower():
                    print("   ⚠️  UNIQUE constraint already exists on email column")
                else:
                    raise

            # Commit transaction
            conn.commit()
            cursor.close()

            print("\n" + "=" * 80)
            print("✅ Migration completed successfully!")
            print("=" * 80)

            # Verify constraints
            print("\n🔍 Verifying constraints...")
            cursor = conn.cursor()
            cursor.execute("""
                SELECT conname, contype
                FROM pg_constraint
                WHERE conrelid = 'registered_users'::regclass
                AND contype = 'u';
            """)
            constraints = cursor.fetchall()
            print(f"\nFound {len(constraints)} UNIQUE constraints:")
            for name, ctype in constraints:
                print(f"   - {name}")
            cursor.close()

            # Show remaining users
            print("\n📊 Remaining users in database:")
            cursor = conn.cursor()
            cursor.execute("""
                SELECT username, email, email_verified, created_at
                FROM registered_users
                ORDER BY created_at DESC
                LIMIT 10;
            """)
            users = cursor.fetchall()
            for username, email, verified, created_at in users:
                status = "✅ Verified" if verified else "❌ Unverified"
                print(f"   - {username} ({email}) - {status} - Created: {created_at}")
            cursor.close()

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    run_migration()
