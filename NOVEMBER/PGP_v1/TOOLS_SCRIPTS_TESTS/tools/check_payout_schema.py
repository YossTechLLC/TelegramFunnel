#!/usr/bin/env python3
"""Check payout_accumulation table schema"""
import sys
from google.cloud.sql.connector import Connector
from google.cloud import secretmanager

def get_secret(secret_name):
    """Fetch secret from Google Secret Manager"""
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/telepay-459221/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode('UTF-8').strip()

def main():
    connector = Connector()
    conn = connector.connect(
        "telepay-459221:us-central1:telepaypsql",
        "pg8000",
        user=get_secret("DATABASE_USER_SECRET"),
        password=get_secret("DATABASE_PASSWORD_SECRET"),
        db=get_secret("DATABASE_NAME_SECRET"),
    )

    cursor = conn.cursor()

    # Get all columns
    cursor.execute("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = 'payout_accumulation'
        ORDER BY ordinal_position
    """)

    print("\n📋 payout_accumulation table schema:")
    print("="*80)
    for row in cursor.fetchall():
        nullable = "NULL" if row[2] == "YES" else "NOT NULL"
        default = f" DEFAULT {row[3]}" if row[3] else ""
        print(f"{row[0]:30s} {row[1]:20s} {nullable:10s}{default}")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
