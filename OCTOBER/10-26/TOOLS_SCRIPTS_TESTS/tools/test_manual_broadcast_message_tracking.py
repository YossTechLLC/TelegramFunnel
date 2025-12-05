#!/usr/bin/env python3
"""
Test Manual Broadcast with Message Tracking
Tests the complete workflow of message deletion and tracking
"""
import os
import sys
import requests
from google.cloud.sql.connector import Connector
from datetime import datetime
import time

# Configuration
GCBROADCASTSERVICE_URL = "https://gcbroadcastservice-10-26-291176869049.us-central1.run.app"
CLOUD_SQL_CONNECTION_NAME = "telepay-459221:us-central1:telepaypsql"
DATABASE_NAME = "client_table"
DATABASE_USER = "postgres"
DATABASE_PASSWORD = os.getenv('DATABASE_PASSWORD_SECRET', 'Chigdabeast123$')

# Test channel (from user's example)
TEST_OPEN_CHANNEL_ID = "-1003377958897"

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

def get_broadcast_entry(open_channel_id):
    """Get broadcast entry for channel"""
    conn, connector = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT
                id,
                broadcast_status,
                last_open_message_id,
                last_closed_message_id,
                last_sent_time,
                next_send_time
            FROM broadcast_manager
            WHERE open_channel_id = %s
        """, (open_channel_id,))

        row = cur.fetchone()

        if row:
            return {
                'id': row[0],
                'status': row[1],
                'last_open_message_id': row[2],
                'last_closed_message_id': row[3],
                'last_sent_time': row[4],
                'next_send_time': row[5]
            }
        return None

    finally:
        cur.close()
        conn.close()
        connector.close()

def queue_manual_broadcast(broadcast_id):
    """Queue a manual broadcast via API"""
    url = f"{GCBROADCASTSERVICE_URL}/api/broadcast/trigger/{broadcast_id}"

    print(f"📤 Sending POST to: {url}")

    try:
        response = requests.post(url, timeout=30)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")

        if response.status_code == 200:
            return response.json()
        else:
            print(f"   ❌ API call failed: {response.status_code}")
            return None

    except Exception as e:
        print(f"   ❌ Error calling API: {e}")
        return None

def main():
    print("=" * 80)
    print("MANUAL BROADCAST MESSAGE TRACKING TEST")
    print("=" * 80)

    # Step 1: Get current state
    print(f"\n1️⃣ Getting current state for channel {TEST_OPEN_CHANNEL_ID}...")
    before_state = get_broadcast_entry(TEST_OPEN_CHANNEL_ID)

    if not before_state:
        print(f"   ❌ No broadcast entry found for channel {TEST_OPEN_CHANNEL_ID}")
        sys.exit(1)

    print(f"   Broadcast ID: {before_state['id']}")
    print(f"   Status: {before_state['status']}")
    print(f"   Last Open Message ID: {before_state['last_open_message_id']}")
    print(f"   Last Closed Message ID: {before_state['last_closed_message_id']}")
    print(f"   Last Sent: {before_state['last_sent_time']}")
    print(f"   Next Send: {before_state['next_send_time']}")

    # Step 2: Queue manual broadcast
    print(f"\n2️⃣ Queueing manual broadcast...")
    broadcast_id = before_state['id']
    api_result = queue_manual_broadcast(broadcast_id)

    if not api_result:
        print("   ❌ Failed to queue broadcast")
        sys.exit(1)

    print(f"   ✅ Broadcast queued: {api_result}")

    # Step 3: Wait for scheduler to run (runs every minute)
    print(f"\n3️⃣ Waiting for scheduler to execute broadcast...")
    print("   Note: Scheduler runs every minute, waiting up to 90 seconds...")

    max_wait = 90
    poll_interval = 5
    waited = 0

    while waited < max_wait:
        time.sleep(poll_interval)
        waited += poll_interval

        current_state = get_broadcast_entry(TEST_OPEN_CHANNEL_ID)

        # Check if broadcast executed (status changed back to 'completed')
        if current_state['status'] == 'completed' and current_state['last_sent_time'] != before_state['last_sent_time']:
            print(f"   ✅ Broadcast executed! (waited {waited}s)")
            break

        print(f"   ⏳ Still waiting... ({waited}s elapsed, status: {current_state['status']})")

    # Step 4: Get final state
    print(f"\n4️⃣ Getting final state after broadcast...")
    after_state = get_broadcast_entry(TEST_OPEN_CHANNEL_ID)

    print(f"   Broadcast ID: {after_state['id']}")
    print(f"   Status: {after_state['status']}")
    print(f"   Last Open Message ID: {after_state['last_open_message_id']}")
    print(f"   Last Closed Message ID: {after_state['last_closed_message_id']}")
    print(f"   Last Sent: {after_state['last_sent_time']}")

    # Step 5: Analysis
    print(f"\n5️⃣ Analysis:")
    print("\n   BEFORE:")
    print(f"      Status: {before_state['status']}")
    print(f"      Last Open Message ID: {before_state['last_open_message_id']}")
    print(f"      Last Closed Message ID: {before_state['last_closed_message_id']}")
    print(f"      Last Sent: {before_state['last_sent_time']}")

    print("\n   AFTER:")
    print(f"      Status: {after_state['status']}")
    print(f"      Last Open Message ID: {after_state['last_open_message_id']}")
    print(f"      Last Closed Message ID: {after_state['last_closed_message_id']}")
    print(f"      Last Sent: {after_state['last_sent_time']}")

    print("\n   CHANGES:")
    if after_state['last_open_message_id'] != before_state['last_open_message_id']:
        print(f"      ✅ Open message ID updated: {before_state['last_open_message_id']} → {after_state['last_open_message_id']}")
    else:
        print(f"      ❌ Open message ID NOT updated (still {after_state['last_open_message_id']})")

    if after_state['last_closed_message_id'] != before_state['last_closed_message_id']:
        print(f"      ✅ Closed message ID updated: {before_state['last_closed_message_id']} → {after_state['last_closed_message_id']}")
    else:
        print(f"      ❌ Closed message ID NOT updated (still {after_state['last_closed_message_id']})")

    if after_state['last_sent_time'] != before_state['last_sent_time']:
        print(f"      ✅ Last sent time updated: {before_state['last_sent_time']} → {after_state['last_sent_time']}")
    else:
        print(f"      ❌ Last sent time NOT updated")

    # Step 6: Verdict
    print("\n" + "=" * 80)
    if (after_state['last_open_message_id'] is not None and
        after_state['last_open_message_id'] != before_state['last_open_message_id']):
        print("✅ TEST PASSED: Message tracking is working!")
        print("   - Message IDs are being stored in database")
        print("   - Next resend will delete the old message")
    elif after_state['status'] == 'completed' and after_state['last_sent_time'] != before_state['last_sent_time']:
        print("⚠️ PARTIAL SUCCESS: Broadcast sent but message IDs not tracked")
        print("   - Check service logs for errors")
        print("   - May need to verify update_message_ids() is being called")
    else:
        print("❌ TEST FAILED: Broadcast did not execute")
        print("   - Check scheduler logs")
        print("   - Verify broadcast_status is 'pending'")
    print("=" * 80)

if __name__ == "__main__":
    main()
