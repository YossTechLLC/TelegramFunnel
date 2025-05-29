#!/usr/bin/env python
import psycopg2
import requests

# === PostgreSQL Connection Details ===
DB_HOST = '34.58.246.248'
DB_PORT = 5432
DB_NAME = 'client_table'
DB_USER = 'postgres'
DB_PASSWORD = 'Chigdabeast123$'

# === Telegram Bot Token and Chat ID ===
BOT_TOKEN = '8139434770:AAGQNpGzbpeY1FgENcuJ_rctuXOAmRuPVJU'
CHAT_ID = '-1002398681722'  # Replace with your target chat_id

# === Send a message to Telegram ===
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': CHAT_ID,
        'text': text
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"❌ Error sending message to Telegram: {e}")

# === Fetch all IDs and send messages ===
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

        # Send each ID to Telegram
        for id_val in id_list:
            send_telegram_message(f"This value is {id_val}")

        cursor.close()
        connection.close()

    except Exception as e:
        print(f"❌ Error fetching IDs: {e}")

if __name__ == "__main__":
    fetch_all_ids()
