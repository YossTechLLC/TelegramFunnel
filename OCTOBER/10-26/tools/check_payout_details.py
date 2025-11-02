#!/usr/bin/env python
"""
Check detailed payout accumulation data to find GROUP BY issues.
"""
import subprocess
from google.cloud.sql.connector import Connector

# Get credentials from secrets
def get_secret(secret_name):
    result = subprocess.run(
        ['gcloud', 'secrets', 'versions', 'access', 'latest', '--secret', secret_name],
        capture_output=True, text=True
    )
    return result.stdout.strip()

# Database connection
instance_connection_name = get_secret('CLOUD_SQL_CONNECTION_NAME')
db_name = get_secret('DATABASE_NAME_SECRET')
db_user = get_secret('DATABASE_USER_SECRET')
db_password = get_secret('DATABASE_PASSWORD_SECRET')

connector = Connector()

conn = connector.connect(
    instance_connection_name,
    "pg8000",
    user=db_user,
    password=db_password,
    db=db_name
)

print("=" * 80)
print("DETAILED PAYOUT_ACCUMULATION DATA")
print("=" * 80)

cur = conn.cursor()

cur.execute("""
    SELECT
        id,
        client_id,
        user_id,
        accumulated_amount_usdt,
        client_wallet_address,
        client_payout_currency,
        client_payout_network,
        is_paid_out
    FROM payout_accumulation
    WHERE client_id = %s
    ORDER BY id
""", ('-1003296084379',))

print("\nAll records for client -1003296084379:")
print("-" * 80)
for row in cur.fetchall():
    print(f"ID: {row[0]}")
    print(f"  User ID: {row[1]}")
    print(f"  USDT: {row[3]}")
    print(f"  Wallet: {row[4]}")
    print(f"  Currency: {row[5]}")
    print(f"  Network: {row[6]}")
    print(f"  Paid Out: {row[7]}")
    print()

print("=" * 80)
print("TESTING GROUP BY")
print("=" * 80)

cur.execute("""
    SELECT
        pa.client_id,
        pa.client_wallet_address,
        pa.client_payout_currency,
        pa.client_payout_network,
        COUNT(*) as count,
        SUM(pa.accumulated_amount_usdt) as total_usdt
    FROM payout_accumulation pa
    WHERE pa.client_id = %s AND pa.is_paid_out = FALSE
    GROUP BY
        pa.client_id,
        pa.client_wallet_address,
        pa.client_payout_currency,
        pa.client_payout_network
""", ('-1003296084379',))

print("\nGrouped results:")
print("-" * 80)
for row in cur.fetchall():
    print(f"Client: {row[0]}")
    print(f"Wallet: {row[1]}")
    print(f"Currency: {row[2]}")
    print(f"Network: {row[3]}")
    print(f"Count: {row[4]}")
    print(f"Total USDT: {row[5]}")
    print()

print("=" * 80)
print("TESTING FULL BATCH PROCESSOR QUERY")
print("=" * 80)

cur.execute("""
    SELECT
        pa.client_id,
        pa.client_wallet_address,
        pa.client_payout_currency,
        pa.client_payout_network,
        SUM(pa.accumulated_amount_usdt) as total_usdt,
        COUNT(*) as payment_count,
        mc.payout_threshold_usd as threshold,
        mc.open_channel_id,
        mc.closed_channel_id
    FROM payout_accumulation pa
    JOIN main_clients_database mc ON pa.client_id = mc.closed_channel_id
    WHERE pa.is_paid_out = FALSE AND pa.client_id = %s
    GROUP BY
        pa.client_id,
        pa.client_wallet_address,
        pa.client_payout_currency,
        pa.client_payout_network,
        mc.payout_threshold_usd,
        mc.open_channel_id,
        mc.closed_channel_id
""", ('-1003296084379',))

print("\nFull query results with JOIN:")
print("-" * 80)
results = cur.fetchall()
for row in results:
    print(f"Client ID (from pa): {row[0]}")
    print(f"Wallet: {row[1]}")
    print(f"Currency: {row[2]}")
    print(f"Network: {row[3]}")
    print(f"Total USDT: {row[4]}")
    print(f"Payment Count: {row[5]}")
    print(f"Threshold: {row[6]}")
    print(f"Open Channel ID: {row[7]}")
    print(f"Closed Channel ID: {row[8]}")
    print(f"Over threshold? {row[4] >= row[6] if row[6] else 'N/A (threshold is None)'}")
    print()

if len(results) == 0:
    print("❌ NO RESULTS FROM FULL QUERY! Checking why...")
    print("\nChecking if JOIN fails:")
    cur.execute("""
        SELECT COUNT(*)
        FROM payout_accumulation pa
        JOIN main_clients_database mc ON pa.client_id = mc.closed_channel_id
        WHERE pa.client_id = %s
    """, ('-1003296084379',))
    print(f"Join count: {cur.fetchone()[0]}")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("DONE")
print("=" * 80)
