#!/usr/bin/env python3
"""
📢 Backfill Script for Missing broadcast_manager Entries

Purpose:
    Creates broadcast_manager entries for channels that were registered
    before the auto-creation feature was implemented.

Target User:
    UUID 7e1018e4-5644-4031-a05c-4166cc877264 (and any other affected users)

Usage:
    python3 backfill_missing_broadcast_entries.py

Safety:
    - Idempotent (safe to run multiple times)
    - Uses ON CONFLICT DO NOTHING for duplicate protection
    - Logs all operations for audit trail
    - Dry-run mode available for testing

Database:
    Production: telepaypsql (NOT telepaypsql-clone-preclaude)
"""

import sys
import os
from datetime import datetime
from contextlib import contextmanager

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from google.cloud.sql.connector import Connector
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool


class BackfillManager:
    """Manages backfill operations for broadcast_manager table"""

    def __init__(self):
        """Initialize connection to Cloud SQL database"""
        self.connector = Connector()
        self._engine = None

    def _get_engine(self):
        """Get or create SQLAlchemy engine with Cloud SQL Connector"""
        if self._engine is None:
            # Cloud SQL connection details
            connection_name = "pgp-live:us-central1:pgp-telepaypsql"
            db_name = "client_table"
            db_user = "postgres"
            db_password = "Chigdabeast123$"

            def getconn():
                conn = self.connector.connect(
                    connection_name,
                    "pg8000",
                    user=db_user,
                    password=db_password,
                    db=db_name
                )
                return conn

            self._engine = create_engine(
                "postgresql+pg8000://",
                creator=getconn,
                poolclass=NullPool,
            )

            print(f"🔌 Connected to database: {connection_name}/{db_name}")

        return self._engine

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        engine = self._get_engine()
        conn = engine.raw_connection()
        try:
            yield conn
        except Exception as e:
            conn.rollback()
            print(f"❌ Database error: {e}")
            raise
        finally:
            conn.close()

    def find_orphaned_channels(self):
        """
        Find channels without broadcast_manager entries.

        Returns:
            List of (client_id, open_channel_id, closed_channel_id) tuples
        """
        print("\n🔍 Searching for channels without broadcast_manager entries...")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT
                    m.client_id,
                    m.open_channel_id,
                    m.closed_channel_id,
                    m.open_channel_title,
                    m.closed_channel_title
                FROM main_clients_database m
                LEFT JOIN broadcast_manager b
                    ON m.open_channel_id = b.open_channel_id
                    AND m.closed_channel_id = b.closed_channel_id
                WHERE b.id IS NULL
                    AND m.client_id IS NOT NULL
                    AND m.open_channel_id IS NOT NULL
                    AND m.closed_channel_id IS NOT NULL
                ORDER BY m.client_id
            """

            cursor.execute(query)
            orphaned = cursor.fetchall()
            cursor.close()

            return orphaned

    def create_broadcast_entry(self, conn, client_id, open_channel_id, closed_channel_id):
        """
        Create a single broadcast_manager entry.

        Args:
            conn: Database connection
            client_id: User UUID
            open_channel_id: Open channel ID
            closed_channel_id: Closed channel ID

        Returns:
            UUID of created entry, or None if already exists
        """
        cursor = conn.cursor()

        try:
            # Use ON CONFLICT DO NOTHING for idempotency
            cursor.execute("""
                INSERT INTO broadcast_manager (
                    client_id,
                    open_channel_id,
                    closed_channel_id,
                    next_send_time,
                    broadcast_status,
                    is_active,
                    total_broadcasts,
                    successful_broadcasts,
                    failed_broadcasts,
                    consecutive_failures,
                    manual_trigger_count
                ) VALUES (
                    %s, %s, %s, NOW(), 'pending', true, 0, 0, 0, 0, 0
                )
                ON CONFLICT (open_channel_id, closed_channel_id) DO NOTHING
                RETURNING id
            """, (client_id, open_channel_id, closed_channel_id))

            result = cursor.fetchone()
            cursor.close()

            if result:
                broadcast_id = str(result[0])
                return broadcast_id
            else:
                # Entry already existed (conflict)
                return None

        except Exception as e:
            cursor.close()
            raise

    def backfill_all(self, dry_run=False):
        """
        Execute backfill for all orphaned channels.

        Args:
            dry_run: If True, only report what would be done (no changes)

        Returns:
            Dictionary with statistics
        """
        print("\n" + "="*60)
        print("📢 BROADCAST MANAGER BACKFILL SCRIPT")
        print("="*60)
        print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'PRODUCTION (will create entries)'}")
        print(f"Target Database: telepaypsql")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print("="*60 + "\n")

        # Find orphaned channels
        orphaned = self.find_orphaned_channels()

        if not orphaned:
            print("✅ No orphaned channels found! All channels have broadcast_manager entries.")
            return {
                'total_found': 0,
                'created': 0,
                'skipped': 0,
                'errors': 0
            }

        print(f"📋 Found {len(orphaned)} channels without broadcast_manager entries:\n")

        # Display orphaned channels
        target_user_found = False
        for i, (client_id, open_ch, closed_ch, open_title, closed_title) in enumerate(orphaned, 1):
            client_id_str = str(client_id)
            client_short = client_id_str[:8] + "..." if len(client_id_str) > 8 else client_id_str
            print(f"   {i}. User {client_short} | Open: {open_ch} ({open_title}) | Closed: {closed_ch} ({closed_title})")

            if client_id_str == "7e1018e4-5644-4031-a05c-4166cc877264":
                print(f"      🎯 TARGET USER FOUND: {client_id}")
                target_user_found = True

        if not target_user_found:
            print(f"\n⚠️ WARNING: Target user 7e1018e4-5644-4031-a05c-4166cc877264 NOT found in orphaned list")
            print("   This user may already have a broadcast_manager entry, or their channel data is incomplete.")

        if dry_run:
            print(f"\n🔍 DRY RUN MODE: Would create {len(orphaned)} broadcast_manager entries")
            print("   Run without --dry-run to execute backfill")
            return {
                'total_found': len(orphaned),
                'created': 0,
                'skipped': 0,
                'errors': 0
            }

        # Execute backfill
        print(f"\n🚀 Starting backfill for {len(orphaned)} channels...\n")

        created = 0
        skipped = 0
        errors = 0

        with self.get_connection() as conn:
            for client_id, open_ch, closed_ch, open_title, closed_title in orphaned:
                try:
                    client_id_str = str(client_id)
                    broadcast_id = self.create_broadcast_entry(
                        conn, client_id_str, open_ch, closed_ch
                    )

                    if broadcast_id:
                        created += 1
                        client_short = client_id_str[:8] + "..."
                        print(f"   ✅ Created: {broadcast_id} for user {client_short} | {open_ch}/{closed_ch}")

                        # Highlight target user
                        if client_id_str == "7e1018e4-5644-4031-a05c-4166cc877264":
                            print(f"      🎯 TARGET USER FIXED: broadcast_id={broadcast_id}")
                    else:
                        skipped += 1
                        print(f"   ⏭️ Skipped: Entry already exists for {open_ch}/{closed_ch}")

                except Exception as e:
                    errors += 1
                    print(f"   ❌ Error creating entry for {open_ch}/{closed_ch}: {e}")

            # Commit all changes
            conn.commit()
            print(f"\n✅ Transaction committed successfully")

        # Final statistics
        print("\n" + "="*60)
        print("📊 BACKFILL SUMMARY")
        print("="*60)
        print(f"Total orphaned channels found:  {len(orphaned)}")
        print(f"Broadcast entries created:      {created}")
        print(f"Skipped (already exist):        {skipped}")
        print(f"Errors:                         {errors}")
        print("="*60)

        if created > 0:
            print(f"\n✅ SUCCESS: {created} broadcast_manager entries created")
            print("   Users can now use the 'Resend Notification' button on their dashboard")
        else:
            print(f"\n⚠️ No new entries created (all may already exist)")

        return {
            'total_found': len(orphaned),
            'created': created,
            'skipped': skipped,
            'errors': errors
        }

    def verify_target_user(self):
        """
        Verify if target user 7e1018e4-5644-4031-a05c-4166cc877264 now has broadcast_manager entry.

        Returns:
            True if user has broadcast_id, False otherwise
        """
        print("\n🔍 Verifying target user fix...")

        target_user = "7e1018e4-5644-4031-a05c-4166cc877264"

        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT
                    b.id AS broadcast_id,
                    b.open_channel_id,
                    b.closed_channel_id,
                    b.broadcast_status,
                    b.is_active
                FROM main_clients_database m
                INNER JOIN broadcast_manager b
                    ON m.open_channel_id = b.open_channel_id
                    AND m.closed_channel_id = b.closed_channel_id
                WHERE m.client_id = %s
            """

            cursor.execute(query, (target_user,))
            result = cursor.fetchone()
            cursor.close()

            if result:
                broadcast_id, open_ch, closed_ch, status, active = result
                print(f"✅ Target user HAS broadcast_manager entry:")
                print(f"   Broadcast ID:  {broadcast_id}")
                print(f"   Open Channel:  {open_ch}")
                print(f"   Closed Channel: {closed_ch}")
                print(f"   Status:        {status}")
                print(f"   Active:        {active}")
                print(f"\n🎯 User should now see 'Resend Notification' button on dashboard")
                return True
            else:
                print(f"❌ Target user DOES NOT have broadcast_manager entry")
                print(f"   User may not have registered a channel yet, or data is incomplete")
                return False

    def close(self):
        """Close database connector"""
        if self.connector:
            self.connector.close()
            print("\n🔌 Database connection closed")


def main():
    """Main execution function"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Backfill missing broadcast_manager entries for existing channels'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simulate backfill without making changes (default: False)'
    )
    parser.add_argument(
        '--verify-only',
        action='store_true',
        help='Only verify target user, do not run backfill (default: False)'
    )

    args = parser.parse_args()

    backfill_manager = BackfillManager()

    try:
        if args.verify_only:
            # Only verify target user
            backfill_manager.verify_target_user()
        else:
            # Run backfill
            stats = backfill_manager.backfill_all(dry_run=args.dry_run)

            # Verify target user if backfill was executed
            if not args.dry_run and stats['created'] > 0:
                print("\n" + "-"*60)
                backfill_manager.verify_target_user()

    except KeyboardInterrupt:
        print("\n\n⚠️ Backfill interrupted by user (Ctrl+C)")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Backfill failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        backfill_manager.close()


if __name__ == "__main__":
    main()
