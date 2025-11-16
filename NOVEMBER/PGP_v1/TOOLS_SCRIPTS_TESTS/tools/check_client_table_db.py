#!/usr/bin/env python
"""
Check if client_table database exists and what data it has.
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
db_user = get_secret('DATABASE_USER_SECRET')
db_password = get_secret('DATABASE_PASSWORD_SECRET')

connector = Connector()

print("=" * 80)
print("CHECKING DATABASE: client_table")
print("=" * 80)

try:
    conn = connector.connect(
        instance_connection_name,
        "pg8000",
        user=db_user,
        password=db_password,
        db='client_table'
    )

    cur = conn.cursor()

    # Check if payout_accumulation table exists
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'payout_accumulation'
        )
    """)
    table_exists = cur.fetchone()[0]

    print(f"\npayout_accumulation table exists in client_table: {table_exists}")

    if table_exists:
        cur.execute("SELECT COUNT(*) FROM payout_accumulation")
        count = cur.fetchone()[0]
        print(f"Number of records: {count}")

    cur.close()
    conn.close()

except Exception as e:
    print(f"❌ Error connecting to client_table: {e}")

print("\n" + "=" * 80)
print("CHECKING DATABASE: pgp-psql")
print("=" * 80)

try:
    conn = connector.connect(
        instance_connection_name,
        "pg8000",
        user=db_user,
        password=db_password,
        db='pgp-psql'
    )

    cur = conn.cursor()

    # Check if payout_accumulation table exists
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'payout_accumulation'
        )
    """)
    table_exists = cur.fetchone()[0]

    print(f"\npayout_accumulation table exists in pgp-psql: {table_exists}")

    if table_exists:
        cur.execute("SELECT COUNT(*) FROM payout_accumulation WHERE is_paid_out = FALSE")
        count = cur.fetchone()[0]
        print(f"Number of unpaid records: {count}")

    cur.close()
    conn.close()

except Exception as e:
    print(f"❌ Error connecting to pgp-psql: {e}")

print("\n" + "=" * 80)
print("DONE")
print("=" * 80)
