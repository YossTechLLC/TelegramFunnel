#!/usr/bin/env python
import psycopg2

# === PostgreSQL Connection Details ===
DB_HOST = '34.58.246.248'
DB_PORT = 5432
DB_NAME = 'client_table'
DB_USER = 'postgres'
DB_PASSWORD = 'Chigdabeast123$'

def fetch_all_ids():
    try:
        # Connect to the PostgreSQL database
        connection = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )

        cursor = connection.cursor()
        cursor.execute("SELECT id FROM test_table")
        rows = cursor.fetchall()

        id_list = [row[0] for row in rows]
        print("All IDs in test_table:", id_list)

        cursor.close()
        connection.close()

    except Exception as e:
        print(f"❌ Error fetching IDs: {e}")

if __name__ == "__main__":
    fetch_all_ids()
