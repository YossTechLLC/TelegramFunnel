#!/usr/bin/env python
import psycopg2
import requests
import base64
from flask import Flask, request

# === Flask App for handling decode requests ===
app = Flask(__name__)

# === PostgreSQL Connection Details ===
DB_HOST = '34.58.246.248'
DB_PORT = 5432
DB_NAME = 'client_table'
DB_USER = 'postgres'
DB_PASSWORD = 'Chigdabeast123$'

# === Telegram Bot Token and Chat ID ===
BOT_TOKEN = '8139434770:AAGQNpGzbpeY1FgENcuJ_rctuXOAmRuPVJU'
CHAT_ID = '-1002398681722'  # Channel ID

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

# === Encode ID to Base64 (2-way hashing) ===
def encode_id(original_id):
    return base64.urlsafe_b64encode(str(original_id).encode()).decode()

# === Decode Base64 back to ID ===
def decode_hash(hash_str):
    return int(base64.urlsafe_b64decode(hash_str.encode()).decode())

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

        # Send each hash to Telegram with a decode link
        for id_val in id_list:
            hash_val = encode_id(id_val)
            url = f"https://yourdomain.com/decode?hash={hash_val}"
            send_telegram_message(f"Hash: {hash_val}\n🔗 [Decode Link]({url})")

        cursor.close()
        connection.close()

    except Exception as e:
        print(f"❌ Error fetching IDs: {e}")

# === Flask route to handle decoding hash ===
@app.route('/decode', methods=['GET'])
def handle_decode():
    hash_val = request.args.get('hash')
    if not hash_val:
        return "Missing 'hash' parameter", 400
    try:
        original_id = decode_hash(hash_val)
        send_telegram_message(f"🔓 Decoded ID: {original_id}")
        return f"Decoded ID: {original_id}", 200
    except Exception as e:
        return f"Error decoding hash: {e}", 500

if __name__ == "__main__":
    fetch_all_ids()
    # To run Flask app in parallel, you might need to separate this or run using gunicorn or similar
    # app.run(host='0.0.0.0', port=5000)
