#!/usr/bin/env python3
"""
Export currency_to_network data from telepay-459221 for import to pgp-live.
"""
import subprocess
from google.cloud.sql.connector import Connector

def get_secret(secret_name, project="telepay-459221"):
    """Fetch secret from Google Secret Manager"""
    result = subprocess.run(
        ['gcloud', 'secrets', 'versions', 'access', 'latest',
         '--secret', secret_name, '--project', project],
        capture_output=True, text=True
    )
    return result.stdout.strip()

def main():
    print("🔍 Exporting currency_to_network data from telepay-459221")
    print("=" * 80)

    # Connect to telepay-459221 database
    connector = Connector()
    conn = connector.connect(
        "telepay-459221:us-central1:telepaypsql",
        "pg8000",
        user=get_secret("DATABASE_USER_SECRET"),
        password=get_secret("DATABASE_PASSWORD_SECRET"),
        db=get_secret("DATABASE_NAME_SECRET")
    )

    cur = conn.cursor()

    # Get all currency_to_network data
    cur.execute("""
        SELECT currency, network, currency_name, network_name
        FROM currency_to_network
        ORDER BY currency, network
    """)

    rows = cur.fetchall()

    print(f"\n📊 Found {len(rows)} currency/network mappings\n")
    print("-- ============================================================================")
    print("-- Currency to Network Data Population")
    print("-- ============================================================================")
    print("-- Project: pgp-live")
    print("-- Database: telepaydb")
    print("-- Exported from: telepay-459221")
    print("-- Count: {} mappings".format(len(rows)))
    print("-- ============================================================================\n")
    print("BEGIN;\n")
    print("INSERT INTO currency_to_network (currency, network, currency_name, network_name) VALUES")

    for i, row in enumerate(rows):
        currency = row[0]
        network = row[1]
        currency_name = row[2] or 'NULL'
        network_name = row[3] or 'NULL'

        if currency_name != 'NULL':
            currency_name = f"'{currency_name}'"
        if network_name != 'NULL':
            network_name = f"'{network_name}'"

        comma = "," if i < len(rows) - 1 else ";"
        print(f"    ('{currency}', '{network}', {currency_name}, {network_name}){comma}")

    print("\nCOMMIT;")
    print("\n-- ============================================================================")
    print(f"-- ✅ Exported {len(rows)} currency/network mappings")
    print("-- ============================================================================")

    cur.close()
    conn.close()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
