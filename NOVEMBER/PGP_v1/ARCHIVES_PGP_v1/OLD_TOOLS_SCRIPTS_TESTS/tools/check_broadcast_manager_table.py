#!/usr/bin/env python3
"""
Check broadcast_manager table status
"""
import os
import sys
from google.cloud.sql.connector import Connector
from datetime import datetime

# Database credentials
CLOUD_SQL_CONNECTION_NAME = "pgp-live:us-central1:pgp-telepaypsql"
DATABASE_NAME = "client_table"
DATABASE_USER = "postgres"
DATABASE_PASSWORD = os.getenv('DATABASE_PASSWORD_SECRET', 'Chigdabeast123$')

def get_connection():
    """Create database connection"""
    connector = Connector()
    conn = connector.connect(
        CLOUD_SQL_CONNECTION_NAME,
        "pg8000",
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        db=DATABASE_NAME
    )
    return conn, connector

def main():
    print("=" * 80)
    print("BROADCAST_MANAGER TABLE CHECK")
    print("=" * 80)

    conn, connector = get_connection()
    cur = conn.cursor()

    try:
        # 1. Check if table exists
        print("\n📋 Checking if broadcast_manager table exists...")
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'broadcast_manager'
            )
        """)
        exists = cur.fetchone()[0]
        print(f"   Table exists: {exists}")

        if not exists:
            print("   ❌ broadcast_manager table does NOT exist!")
            return

        # 2. Count total rows
        print("\n📊 Counting rows in broadcast_manager...")
        cur.execute("SELECT COUNT(*) FROM broadcast_manager")
        total_count = cur.fetchone()[0]
        print(f"   Total rows: {total_count}")

        if total_count == 0:
            print("   ❌ Table is EMPTY!")
            return

        # 3. Check column values distribution
        print("\n🔍 Analyzing column values...")

        # is_active distribution
        cur.execute("""
            SELECT is_active, COUNT(*)
            FROM broadcast_manager
            GROUP BY is_active
        """)
        print("   is_active distribution:")
        for row in cur.fetchall():
            print(f"      {row[0]}: {row[1]} rows")

        # broadcast_status distribution
        cur.execute("""
            SELECT broadcast_status, COUNT(*)
            FROM broadcast_manager
            GROUP BY broadcast_status
        """)
        print("   broadcast_status distribution:")
        for row in cur.fetchall():
            print(f"      {row[0]}: {row[1]} rows")

        # consecutive_failures distribution
        cur.execute("""
            SELECT
                CASE
                    WHEN consecutive_failures < 5 THEN 'Less than 5'
                    ELSE '5 or more'
                END as failure_category,
                COUNT(*)
            FROM broadcast_manager
            GROUP BY failure_category
        """)
        print("   consecutive_failures distribution:")
        for row in cur.fetchall():
            print(f"      {row[0]}: {row[1]} rows")

        # 4. Check next_send_time values
        print("\n⏰ Analyzing next_send_time...")
        cur.execute("""
            SELECT
                CASE
                    WHEN next_send_time IS NULL THEN 'NULL'
                    WHEN next_send_time <= NOW() THEN 'Past or now'
                    ELSE 'Future'
                END as time_category,
                COUNT(*)
            FROM broadcast_manager
            GROUP BY time_category
        """)
        print("   next_send_time distribution:")
        for row in cur.fetchall():
            print(f"      {row[0]}: {row[1]} rows")

        # 5. Show rows that SHOULD match the query conditions
        print("\n✅ Rows that SHOULD match fetch_due_broadcasts() conditions:")
        print("   (is_active=true AND broadcast_status='pending' AND next_send_time<=NOW() AND consecutive_failures<5)")
        cur.execute("""
            SELECT
                id,
                client_id,
                open_channel_id,
                is_active,
                broadcast_status,
                next_send_time,
                consecutive_failures,
                last_sent_time
            FROM broadcast_manager
            WHERE is_active = true
                AND broadcast_status = 'pending'
                AND next_send_time <= NOW()
                AND consecutive_failures < 5
            ORDER BY next_send_time ASC
            LIMIT 10
        """)
        matching_rows = cur.fetchall()
        print(f"   Found {len(matching_rows)} matching rows")

        if matching_rows:
            for row in matching_rows:
                print(f"\n   Row:")
                print(f"      id: {row[0]}")
                print(f"      client_id: {row[1]}")
                print(f"      open_channel_id: {row[2]}")
                print(f"      is_active: {row[3]}")
                print(f"      broadcast_status: {row[4]}")
                print(f"      next_send_time: {row[5]}")
                print(f"      consecutive_failures: {row[6]}")
                print(f"      last_sent_time: {row[7]}")
        else:
            print("   ❌ NO rows match the conditions!")

        # 6. Test the INNER JOIN with main_clients_database
        print("\n🔗 Testing INNER JOIN with main_clients_database...")
        cur.execute("""
            SELECT COUNT(*)
            FROM broadcast_manager bm
            INNER JOIN main_clients_database mc
                ON bm.open_channel_id = mc.open_channel_id
        """)
        join_count = cur.fetchone()[0]
        print(f"   Rows after INNER JOIN: {join_count}")

        if join_count < total_count:
            print(f"   ⚠️ WARNING: {total_count - join_count} broadcasts have no matching client in main_clients_database!")

        # 7. Show sample of ALL rows for debugging
        print("\n📝 Sample of ALL rows in broadcast_manager (first 5):")
        cur.execute("""
            SELECT
                id,
                client_id,
                open_channel_id,
                closed_channel_id,
                is_active,
                broadcast_status,
                next_send_time,
                consecutive_failures,
                last_sent_time,
                created_at
            FROM broadcast_manager
            ORDER BY created_at DESC
            LIMIT 5
        """)
        for row in cur.fetchall():
            print(f"\n   Row:")
            print(f"      id: {row[0]}")
            print(f"      client_id: {row[1]}")
            print(f"      open_channel_id: {row[2]}")
            print(f"      closed_channel_id: {row[3]}")
            print(f"      is_active: {row[4]}")
            print(f"      broadcast_status: {row[5]}")
            print(f"      next_send_time: {row[6]}")
            print(f"      consecutive_failures: {row[7]}")
            print(f"      last_sent_time: {row[8]}")
            print(f"      created_at: {row[9]}")

        print("\n" + "=" * 80)
        print("CHECK COMPLETE")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        cur.close()
        conn.close()
        connector.close()

if __name__ == "__main__":
    main()
