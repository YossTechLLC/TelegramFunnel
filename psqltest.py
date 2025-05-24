import psycopg2

# Replace with your actual database credentials
DB_HOST = "34.58.246.248"
DB_PORT = 5432
DB_NAME = "postgres"
DB_USER = "telepaypsql"
DB_PASSWORD = "Chigdabeast123$"

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    print("✅ Connected successfully to the database.")

    # Optionally test a query
    with conn.cursor() as cur:
        cur.execute("SELECT version();")
        print("PostgreSQL version:", cur.fetchone())

except Exception as e:
    print("❌ Connection failed:", e)

finally:
    if 'conn' in locals() and conn:
        conn.close()
