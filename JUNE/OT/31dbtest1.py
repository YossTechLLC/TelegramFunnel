import psycopg2

# === postgresql connection details ===
DB_HOST = '34.58.246.248'
DB_PORT = 5432
DB_NAME = 'client_table'
DB_USER = 'postgres'
DB_PASSWORD = 'Chigdabeast123$'

# === global variables ===
tele_open_list = []
tele_closed_list = []

def fetch_tele_channel_data():
    global tele_open_list, tele_closed_list
    try:
        # connect to db
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor()

        cursor.execute("SELECT tele_open, tele_closed FROM tele_channel")
        rows = cursor.fetchall()

        # store to global arrays
        tele_open_list = [row[0] for row in rows]
        tele_closed_list = [row[1] for row in rows]

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"❌ error fetching data: {e}")
        tele_open_list = []
        tele_closed_list = []

# run fetch once at startup to populate globals
fetch_tele_channel_data()

# example usage
print("tele_open_list:", tele_open_list)
print("tele_closed_list:", tele_closed_list)
