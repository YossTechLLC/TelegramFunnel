#!/usr/bin/env python
"""Verify batch creation success."""
import subprocess
from google.cloud.sql.connector import Connector

def get_secret(secret_name):
    result = subprocess.run(
        ['gcloud', 'secrets', 'versions', 'access', 'latest', '--secret', secret_name],
        capture_output=True, text=True
    )
    return result.stdout.strip()

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
print("PAYOUT_BATCHES TABLE")
print("=" * 80)

cur = conn.cursor()
cur.execute("""
    SELECT batch_id, client_id, total_amount_usdt, total_payments_count, status, created_at
    FROM payout_batches
    ORDER BY created_at DESC
    LIMIT 5
""")

for row in cur.fetchall():
    print(f"\nBatch ID: {row[0]}")
    print(f"  Client: {row[1]}")
    print(f"  Amount: ${row[2]}")
    print(f"  Payments: {row[3]}")
    print(f"  Status: {row[4]}")
    print(f"  Created: {row[5]}")

print("\n" + "=" * 80)
print("PAYOUT_ACCUMULATION STATUS")
print("=" * 80)

cur.execute("""
    SELECT id, client_id, accumulated_amount_usdt, is_paid_out, payout_batch_id
    FROM payout_accumulation
    WHERE client_id = %s
    ORDER BY id
""", ('-1003296084379',))

for row in cur.fetchall():
    print(f"\nID: {row[0]}")
    print(f"  Client: {row[1]}")
    print(f"  USDT: {row[2]}")
    print(f"  Paid Out: {row[3]}")
    print(f"  Batch ID: {row[4] if row[4] else 'None'}")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("VERIFICATION COMPLETE")
print("=" * 80)
