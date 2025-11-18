#!/usr/bin/env python3
"""
Check if conversion_status fields exist in payout_accumulation table.
"""
import sys
from google.cloud import secretmanager
from google.cloud.sql.connector import Connector
import pg8000

def get_secret(project_id: str, secret_name: str) -> str:
    """Fetch secret from Google Secret Manager."""
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8").strip()

def main():
    project_id = "pgp-live"

    print("🔐 Fetching database credentials from Secret Manager...")
    try:
        connection_name = get_secret(project_id, "CLOUD_SQL_CONNECTION_NAME")
        database_name = get_secret(project_id, "DATABASE_NAME_SECRET")
        user = get_secret(project_id, "DATABASE_USER_SECRET")
        password = get_secret(project_id, "DATABASE_PASSWORD_SECRET")

        print(f"✅ Credentials loaded successfully")
        print(f"   Database: {database_name}")
        print(f"   User: {user}")

    except Exception as e:
        print(f"❌ Failed to load credentials: {e}")
        return 1

    print(f"\n🔌 Connecting to Cloud SQL instance...")
    connector = Connector()

    try:
        conn = connector.connect(
            connection_name,
            "pg8000",
            user=user,
            password=password,
            db=database_name
        )

        print(f"✅ Connected to database")

        # Check if conversion_status fields exist
        print(f"\n🔍 Checking for conversion_status fields...")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT column_name, data_type, column_default, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'payout_accumulation'
              AND column_name IN ('conversion_status', 'conversion_attempts', 'last_conversion_attempt')
            ORDER BY column_name
        """)

        columns = cursor.fetchall()

        if columns:
            print(f"\n✅ Conversion status fields found:")
            print(f"   {'Column Name':<30} {'Data Type':<20} {'Default':<20} {'Nullable'}")
            print(f"   {'-'*30} {'-'*20} {'-'*20} {'-'*8}")
            for col in columns:
                col_name, data_type, default, nullable = col
                default_str = default if default else "NULL"
                print(f"   {col_name:<30} {data_type:<20} {default_str:<20} {nullable}")
        else:
            print(f"\n❌ No conversion_status fields found in payout_accumulation table")
            print(f"   Migration needs to be run!")

        # Check if index exists
        print(f"\n🔍 Checking for conversion_status index...")
        cursor.execute("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'payout_accumulation'
              AND indexname LIKE '%conversion_status%'
        """)

        indexes = cursor.fetchall()

        if indexes:
            print(f"\n✅ Conversion status index found:")
            for idx_name, idx_def in indexes:
                print(f"   Index: {idx_name}")
                print(f"   Definition: {idx_def}")
        else:
            print(f"\n⚠️  No conversion_status index found")

        # Get conversion status distribution
        print(f"\n📊 Conversion status distribution:")
        cursor.execute("""
            SELECT
                conversion_status,
                COUNT(*) as count
            FROM payout_accumulation
            GROUP BY conversion_status
            ORDER BY conversion_status
        """)

        status_dist = cursor.fetchall()

        if status_dist:
            print(f"   {'Status':<15} {'Count'}")
            print(f"   {'-'*15} {'-'*10}")
            for status, count in status_dist:
                status_str = status if status else "NULL"
                print(f"   {status_str:<15} {count}")
        else:
            print(f"   No records in payout_accumulation table")

        cursor.close()
        conn.close()
        connector.close()

        print(f"\n✅ Schema check complete")
        return 0

    except Exception as e:
        print(f"❌ Database error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
