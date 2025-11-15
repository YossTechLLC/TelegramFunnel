#!/usr/bin/env python3
"""
Populate broadcast_manager table with existing channel pairs from main_clients_database.
This script should be run once after creating the broadcast_manager table.

It fetches all channel pairs (open_channel_id, closed_channel_id, client_id) from
main_clients_database and inserts them into broadcast_manager with initial state.
"""

import sys
import os
from datetime import datetime, timedelta
from google.cloud import secretmanager
import psycopg2

def fetch_secret(secret_name):
    """Fetch secret from Secret Manager."""
    try:
        client = secretmanager.SecretManagerServiceClient()
        project_id = "telepay-459221"
        secret_path = f"projects/{project_id}/secrets/{secret_name}/versions/latest"

        response = client.access_secret_version(request={"name": secret_path})
        value = response.payload.data.decode("UTF-8")
        return value
    except Exception as e:
        print(f"❌ Error fetching secret {secret_name}: {e}")
        raise

def populate_broadcast_manager():
    """Populate broadcast_manager table from main_clients_database."""

    print("🚀 Starting broadcast_manager population...")
    print("=" * 70)

    # Fetch database credentials
    print("\n📡 Fetching database credentials from Secret Manager...")
    try:
        db_host = fetch_secret('DATABASE_HOST_SECRET')
        db_name = fetch_secret('DATABASE_NAME_SECRET')
        db_user = fetch_secret('DATABASE_USER_SECRET')
        db_password = fetch_secret('DATABASE_PASSWORD_SECRET')
        print("✅ Database credentials fetched successfully")
        print(f"   Host: {db_host}")
        print(f"   Database: {db_name}")
    except Exception as e:
        print(f"❌ Failed to fetch database credentials: {e}")
        sys.exit(1)

    # Connect to database
    print(f"\n🔌 Connecting to database...")
    try:
        conn = psycopg2.connect(
            host=db_host,
            dbname=db_name,
            user=db_user,
            password=db_password,
            port=5432
        )
        print("✅ Database connection established")
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        sys.exit(1)

    try:
        with conn.cursor() as cur:
            # First, check current broadcast_manager count
            cur.execute("SELECT COUNT(*) FROM broadcast_manager")
            existing_count = cur.fetchone()[0]
            print(f"\n📊 Current broadcast_manager entries: {existing_count}")

            if existing_count > 0:
                print(f"⚠️  Warning: broadcast_manager already has {existing_count} entries")
                response = input("Continue and add new entries? (y/n): ")
                if response.lower() != 'y':
                    print("❌ Population cancelled by user")
                    sys.exit(0)

            # Fetch all channel pairs from main_clients_database
            print("\n📋 Fetching channel pairs from main_clients_database...")

            query = """
                SELECT
                    client_id,
                    open_channel_id,
                    closed_channel_id,
                    open_channel_title,
                    closed_channel_title
                FROM main_clients_database
                WHERE open_channel_id IS NOT NULL
                    AND closed_channel_id IS NOT NULL
                    AND client_id IS NOT NULL
                ORDER BY client_id
            """

            cur.execute(query)
            channel_pairs = cur.fetchall()
            print(f"✅ Found {len(channel_pairs)} channel pairs to process")

            if len(channel_pairs) == 0:
                print("⚠️  No channel pairs found in main_clients_database")
                print("   This is normal if the system is new.")
                sys.exit(0)

            # Insert into broadcast_manager
            print("\n💾 Inserting into broadcast_manager...")
            print("-" * 70)

            inserted = 0
            skipped = 0
            errors = []

            for client_id, open_channel_id, closed_channel_id, open_title, closed_title in channel_pairs:
                try:
                    # Set initial next_send_time to NOW (will send on first cron run)
                    insert_query = """
                        INSERT INTO broadcast_manager (
                            client_id,
                            open_channel_id,
                            closed_channel_id,
                            next_send_time,
                            broadcast_status,
                            is_active
                        ) VALUES (%s, %s, %s, NOW(), 'pending', true)
                        ON CONFLICT (open_channel_id, closed_channel_id) DO NOTHING
                        RETURNING id
                    """

                    cur.execute(insert_query, (client_id, open_channel_id, closed_channel_id))
                    result = cur.fetchone()

                    if result:
                        inserted += 1
                        print(f"  ✅ [{inserted:3d}] Inserted: client={str(client_id)[:8]}... open={open_title[:20]}")
                    else:
                        skipped += 1
                        print(f"  ⏭️  [{skipped:3d}] Skipped (duplicate): open={open_title[:20]}")

                except psycopg2.Error as e:
                    error_msg = f"open={open_channel_id}: {e.pgerror}"
                    errors.append(error_msg)
                    skipped += 1
                    print(f"  ❌ Error: {error_msg[:60]}...")

            # Commit the transaction
            conn.commit()
            print("-" * 70)

            # Display summary
            print("\n📊 Population Summary:")
            print("=" * 70)
            print(f"  Total channel pairs found:  {len(channel_pairs)}")
            print(f"  Successfully inserted:       {inserted}")
            print(f"  Skipped (duplicates):        {skipped}")
            print(f"  Errors:                      {len(errors)}")
            print("=" * 70)

            if errors:
                print("\n❌ Errors encountered:")
                for i, error in enumerate(errors[:10], 1):
                    print(f"  {i}. {error}")
                if len(errors) > 10:
                    print(f"  ... and {len(errors) - 10} more errors")

            # Verify final count
            cur.execute("SELECT COUNT(*) FROM broadcast_manager")
            final_count = cur.fetchone()[0]

            print(f"\n✅ Final broadcast_manager count: {final_count}")

            # Show sample of inserted data
            print("\n📋 Sample of inserted data (first 5):")
            print("-" * 70)

            cur.execute("""
                SELECT
                    id,
                    client_id,
                    open_channel_id,
                    closed_channel_id,
                    next_send_time,
                    broadcast_status,
                    is_active
                FROM broadcast_manager
                ORDER BY created_at DESC
                LIMIT 5
            """)

            for row in cur.fetchall():
                id_val, client_id, open_ch, closed_ch, next_send, status, active = row
                print(f"  ID: {str(id_val)[:8]}...")
                print(f"    Client: {str(client_id)[:8]}...")
                print(f"    Open:   {open_ch}")
                print(f"    Closed: {closed_ch}")
                print(f"    Next:   {next_send}")
                print(f"    Status: {status} | Active: {active}")
                print()

            print("-" * 70)
            print("✅ Population complete!")

    except psycopg2.Error as e:
        print(f"\n❌ Database error during population: {e}")
        print(f"   SQLSTATE: {e.pgcode}")
        print(f"   Details: {e.pgerror}")
        conn.rollback()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error during population: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()
        print("\n🔌 Database connection closed")

    print("\n" + "=" * 70)
    print("🎉 Broadcast manager populated successfully!")
    print("=" * 70)
    print("\n📋 Next steps:")
    print("  1. Verify data: SELECT COUNT(*) FROM broadcast_manager;")
    print("  2. Check sample: SELECT * FROM broadcast_manager LIMIT 5;")
    print("  3. Proceed to Phase 2: Service Development")

if __name__ == "__main__":
    populate_broadcast_manager()
