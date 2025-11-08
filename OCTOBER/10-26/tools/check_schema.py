#!/usr/bin/env python
"""
Quick script to check database schema and data.
"""
import os
import sys
from google.cloud.sql.connector import Connector

# Get credentials from secrets
def get_secret(secret_name):
    import subprocess
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
print("MAIN_CLIENTS_DATABASE SCHEMA")
print("=" * 80)

cur = conn.cursor()
cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'main_clients_database'
    ORDER BY ordinal_position
""")
for row in cur.fetchall():
    print(f"{row[0]:30} {row[1]:20} NULL: {row[2]}")

print("\n" + "=" * 80)
print("PAYOUT_ACCUMULATION SCHEMA")
print("=" * 80)

cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'payout_accumulation'
    ORDER BY ordinal_position
""")
for row in cur.fetchall():
    print(f"{row[0]:30} {row[1]:20} NULL: {row[2]}")

print("\n" + "=" * 80)
print("CHECKING CLIENT -1003296084379")
print("=" * 80)

cur.execute("""
    SELECT open_channel_id, closed_channel_id, payout_threshold_usd
    FROM main_clients_database
    WHERE closed_channel_id = %s OR open_channel_id = %s
""", ('-1003296084379', '-1003296084379'))

rows = cur.fetchall()
if rows:
    for row in rows:
        print(f"open_channel_id: {row[0]}")
        print(f"closed_channel_id: {row[1]}")
        print(f"payout_threshold_usd: {row[2]}")
else:
    print("No matching client found!")

print("\n" + "=" * 80)
print("PAYOUT_ACCUMULATION FOR CLIENT -1003296084379")
print("=" * 80)

cur.execute("""
    SELECT id, client_id, accumulated_amount_usdt, is_paid_out
    FROM payout_accumulation
    WHERE client_id = %s
""", ('-1003296084379',))

for row in cur.fetchall():
    print(f"ID: {row[0]}, Client: {row[1]}, USDT: {row[2]}, Paid: {row[3]}")

cur.close()
conn.close()
print("\n" + "=" * 80)
print("DONE")
print("=" * 80)
