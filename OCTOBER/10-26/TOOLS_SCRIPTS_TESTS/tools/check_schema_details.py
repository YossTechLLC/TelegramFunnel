#!/usr/bin/env python
"""
Check schema details for subscription_id relationship and payout_accumulation fields.
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

cur = conn.cursor()

print("=" * 80)
print("PRIVATE_CHANNEL_USERS_DATABASE SCHEMA")
print("=" * 80)
cur.execute("""
    SELECT column_name, data_type, is_nullable, column_default
    FROM information_schema.columns
    WHERE table_name = 'private_channel_users_database'
    ORDER BY ordinal_position;
""")

for row in cur.fetchall():
    print(f"{row[0]:30s} {row[1]:20s} NULL:{row[2]:5s} DEFAULT:{row[3] or 'None'}")

print("\n" + "=" * 80)
print("PAYOUT_ACCUMULATION SCHEMA")
print("=" * 80)
cur.execute("""
    SELECT column_name, data_type, is_nullable, column_default
    FROM information_schema.columns
    WHERE table_name = 'payout_accumulation'
    ORDER BY ordinal_position;
""")

for row in cur.fetchall():
    print(f"{row[0]:30s} {row[1]:20s} NULL:{row[2]:5s} DEFAULT:{row[3] or 'None'}")

print("\n" + "=" * 80)
print("FOREIGN KEY RELATIONSHIPS")
print("=" * 80)
cur.execute("""
    SELECT
        tc.table_name,
        kcu.column_name,
        ccu.table_name AS foreign_table_name,
        ccu.column_name AS foreign_column_name
    FROM information_schema.table_constraints AS tc
    JOIN information_schema.key_column_usage AS kcu
      ON tc.constraint_name = kcu.constraint_name
    JOIN information_schema.constraint_column_usage AS ccu
      ON ccu.constraint_name = tc.constraint_name
    WHERE tc.constraint_type = 'FOREIGN KEY'
      AND tc.table_name IN ('payout_accumulation', 'private_channel_users_database');
""")

for row in cur.fetchall():
    print(f"{row[0]:30s}.{row[1]:30s} -> {row[2]:30s}.{row[3]:30s}")

print("\n" + "=" * 80)
print("SAMPLE DATA - SUBSCRIPTION RELATIONSHIP")
print("=" * 80)
cur.execute("""
    SELECT
        pa.id as accum_id,
        pa.subscription_id,
        pa.user_id as pa_user_id,
        pa.client_id,
        pcud.id as subscription_table_id,
        pcud.user_id as pcud_user_id,
        pcud.private_channel_id,
        pcud.sub_price
    FROM payout_accumulation pa
    LEFT JOIN private_channel_users_database pcud ON pa.subscription_id = pcud.id
    LIMIT 5;
""")

print("\nAccumulation -> Subscription Link:")
print("-" * 80)
for row in cur.fetchall():
    print(f"Accum ID: {row[0]}")
    print(f"  → subscription_id (FK): {row[1]}")
    print(f"  → user_id in payout_accumulation: {row[2]}")
    print(f"  → client_id: {row[3]}")
    print(f"  → Matches subscription table ID: {row[4]}")
    print(f"  → user_id in private_channel_users_database: {row[5]}")
    print(f"  → private_channel_id: {row[6]}")
    print(f"  → sub_price: {row[7]}")
    print()

cur.close()
conn.close()

print("=" * 80)
print("DONE")
print("=" * 80)
