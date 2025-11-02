#!/usr/bin/env python
"""
Check payment_amount_usd and accumulated_amount_usdt to find the calculation discrepancy.
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
print("PAYMENT AMOUNT VS ACCUMULATED AMOUNT ANALYSIS")
print("=" * 80)

cur = conn.cursor()

cur.execute("""
    SELECT
        id,
        client_id,
        user_id,
        payment_amount_usd,
        accumulated_amount_usdt,
        eth_to_usdt_rate,
        payment_timestamp,
        conversion_timestamp,
        (payment_amount_usd - accumulated_amount_usdt) as difference,
        ((payment_amount_usd - accumulated_amount_usdt) / payment_amount_usd * 100) as fee_percentage
    FROM payout_accumulation
    ORDER BY id
""")

print("\nFull Payment Analysis:")
print("-" * 80)
for row in cur.fetchall():
    print(f"ID: {row[0]}")
    print(f"  Client ID: {row[1]}")
    print(f"  User ID: {row[2]}")
    print(f"  Payment Amount USD: {row[3]}")
    print(f"  Accumulated Amount USDT: {row[4]}")
    print(f"  ETH to USDT Rate: {row[5]}")
    print(f"  Payment Timestamp: {row[6]}")
    print(f"  Conversion Timestamp: {row[7]}")
    print(f"  Difference (Fee): {row[8]}")
    print(f"  Fee Percentage: {row[9]:.2f}%")
    print()

cur.close()
conn.close()

print("\n" + "=" * 80)
print("DONE")
print("=" * 80)
