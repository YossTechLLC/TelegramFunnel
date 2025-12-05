#!/usr/bin/env python3
"""
Test fetch_due_broadcasts() to understand why it returns 0 broadcasts
"""
import os
import sys
from google.cloud.sql.connector import Connector
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from datetime import datetime

# Database credentials
CLOUD_SQL_CONNECTION_NAME = "telepay-459221:us-central1:telepaypsql"
DATABASE_NAME = "client_table"
DATABASE_USER = "postgres"
DATABASE_PASSWORD = os.getenv('DATABASE_PASSWORD_SECRET', 'Chigdabeast123$')

def get_engine():
    """Create SQLAlchemy engine with Cloud SQL Connector"""
    connector = Connector()

    def getconn():
        conn = connector.connect(
            CLOUD_SQL_CONNECTION_NAME,
            "pg8000",
            user=DATABASE_USER,
            password=DATABASE_PASSWORD,
            db=DATABASE_NAME
        )
        return conn

    engine = create_engine(
        "postgresql+pg8000://",
        creator=getconn,
        poolclass=NullPool,
    )

    return engine, connector

def test_fetch_due_broadcasts():
    """Test the exact query from fetch_due_broadcasts()"""
    print("=" * 80)
    print("TESTING fetch_due_broadcasts() QUERY")
    print("=" * 80)

    engine, connector = get_engine()

    try:
        conn = engine.raw_connection()
        cur = conn.cursor()

        # This is the EXACT query from database_manager.py fetch_due_broadcasts()
        query = """
            SELECT
                bm.id,
                bm.client_id,
                bm.open_channel_id,
                bm.closed_channel_id,
                bm.last_sent_time,
                bm.next_send_time,
                bm.broadcast_status,
                bm.consecutive_failures,
                mc.open_channel_title,
                mc.open_channel_description,
                mc.closed_channel_title,
                mc.closed_channel_description,
                mc.closed_channel_donation_message,
                mc.sub_1_price,
                mc.sub_1_time,
                mc.sub_2_price,
                mc.sub_2_time,
                mc.sub_3_price,
                mc.sub_3_time
            FROM broadcast_manager bm
            INNER JOIN main_clients_database mc
                ON bm.open_channel_id = mc.open_channel_id
            WHERE bm.is_active = true
                AND bm.broadcast_status = 'pending'
                AND bm.next_send_time <= NOW()
                AND bm.consecutive_failures < 5
            ORDER BY bm.next_send_time ASC
        """

        print("\n📋 Executing query...")
        print(f"   Current time (UTC): {datetime.utcnow()}")

        cur.execute(query)
        rows = cur.fetchall()

        print(f"\n✅ Query executed successfully!")
        print(f"   Rows returned: {len(rows)}")

        if rows:
            # Convert rows to dictionaries
            columns = [desc[0] for desc in cur.description]
            broadcasts = [dict(zip(columns, row)) for row in rows]

            print(f"\n📊 Found {len(broadcasts)} broadcasts:")
            for i, broadcast in enumerate(broadcasts, 1):
                print(f"\n   Broadcast {i}:")
                print(f"      id: {broadcast['id']}")
                print(f"      open_channel_id: {broadcast['open_channel_id']}")
                print(f"      closed_channel_id: {broadcast['closed_channel_id']}")
                print(f"      open_channel_title: {broadcast.get('open_channel_title', 'N/A')}")
                print(f"      closed_channel_title: {broadcast.get('closed_channel_title', 'N/A')}")
                print(f"      next_send_time: {broadcast['next_send_time']}")
                print(f"      broadcast_status: {broadcast['broadcast_status']}")
                print(f"      consecutive_failures: {broadcast['consecutive_failures']}")
        else:
            print("\n❌ NO broadcasts returned!")
            print("   This is the problem - query returns 0 rows when executed from Python")

            # Let's check if the INNER JOIN is the problem
            print("\n🔍 Testing without INNER JOIN...")
            cur.execute("""
                SELECT COUNT(*)
                FROM broadcast_manager bm
                WHERE bm.is_active = true
                    AND bm.broadcast_status = 'pending'
                    AND bm.next_send_time <= NOW()
                    AND bm.consecutive_failures < 5
            """)
            count_without_join = cur.fetchone()[0]
            print(f"   Rows WITHOUT join: {count_without_join}")

            if count_without_join > 0:
                print("   ⚠️ JOIN is filtering out results!")
            else:
                print("   ⚠️ Base WHERE conditions are not matching any rows!")

        cur.close()
        conn.close()

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        connector.close()

    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    test_fetch_due_broadcasts()
