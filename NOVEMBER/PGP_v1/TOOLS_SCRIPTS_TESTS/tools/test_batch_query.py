#!/usr/bin/env python
"""
Test the exact query that GCBatchProcessor uses.
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
print("TESTING GCBATCHPROCESSOR QUERY")
print("=" * 80)

cur = conn.cursor()

# This is the EXACT query from GCBatchProcessor
cur.execute("""
    SELECT
        pa.client_id,
        pa.client_wallet_address,
        pa.client_payout_currency,
        pa.client_payout_network,
        SUM(pa.accumulated_amount_usdt) as total_usdt,
        COUNT(*) as payment_count,
        mc.payout_threshold_usd as threshold
    FROM payout_accumulation pa
    JOIN main_clients_database mc ON pa.client_id = mc.closed_channel_id
    WHERE pa.is_paid_out = FALSE
    GROUP BY
        pa.client_id,
        pa.client_wallet_address,
        pa.client_payout_currency,
        pa.client_payout_network,
        mc.payout_threshold_usd
    HAVING SUM(pa.accumulated_amount_usdt) >= mc.payout_threshold_usd
""")

results = cur.fetchall()

print(f"\nFound {len(results)} client(s) over threshold:\n")

for row in results:
    print(f"Client ID: {row[0]}")
    print(f"Wallet Address: {row[1]}")
    print(f"Payout Currency: {row[2]}")
    print(f"Payout Network: {row[3]}")
    print(f"Total USDT: ${row[4]}")
    print(f"Payment Count: {row[5]}")
    print(f"Threshold: ${row[6]}")
    print()

if len(results) == 0:
    print("❌ NO CLIENTS FOUND - Testing why...")
    print("\nStep 1: Check if JOIN works")
    cur.execute("""
        SELECT pa.client_id, mc.closed_channel_id, mc.payout_threshold_usd
        FROM payout_accumulation pa
        JOIN main_clients_database mc ON pa.client_id = mc.closed_channel_id
        WHERE pa.is_paid_out = FALSE
        LIMIT 5
    """)
    print(f"JOIN results: {cur.fetchall()}")

    print("\nStep 2: Check aggregation")
    cur.execute("""
        SELECT
            pa.client_id,
            SUM(pa.accumulated_amount_usdt) as total_usdt,
            mc.payout_threshold_usd as threshold
        FROM payout_accumulation pa
        JOIN main_clients_database mc ON pa.client_id = mc.closed_channel_id
        WHERE pa.is_paid_out = FALSE
        GROUP BY pa.client_id, mc.payout_threshold_usd
    """)
    agg_results = cur.fetchall()
    for row in agg_results:
        print(f"Client: {row[0]}, Total: ${row[1]}, Threshold: ${row[2]}, Over? {row[1] >= row[2]}")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("DONE")
print("=" * 80)
