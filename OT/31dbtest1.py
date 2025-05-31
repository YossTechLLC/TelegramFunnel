import psycopg2

# database credentials
DB_HOST = '34.58.246.248'
DB_PORT = 5432
DB_NAME = 'client_table'
DB_USER = 'postgres'
DB_PASSWORD = 'Chigdabeast123$'

def fetch_tele_channel_data():
    try:
        # connect to database
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor()

        # execute query
        cursor.execute("SELECT tele_open, tele_closed FROM tele_channel")
        rows = cursor.fetchall()

        # separate into two arrays
        tele_open_list = [row[0] for row in rows]
        tele_closed_list = [row[1] for row in rows]

        print("tele_open array:", tele_open_list)
        print("tele_closed array:", tele_closed_list)

        # cleanup
        cursor.close()
        conn.close()

        return tele_open_list, tele_closed_list

    except Exception as e:
        print(f"❌ error fetching data: {e}")
        return [], []

# run the function
if __name__ == "__main__":
    fetch_tele_channel_data()
