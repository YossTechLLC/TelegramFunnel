#!/usr/bin/env python
import psycopg2
import requests
import base64
import time
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio
import nest_asyncio

# Patch the event loop to allow nested use
nest_asyncio.apply()

# === Flask App for handling decode requests ===
app = Flask(__name__)

# === PostgreSQL Connection Details ===
DB_HOST = '34.58.246.248'
DB_PORT = 5432
DB_NAME = 'client_table'
DB_USER = 'postgres'
DB_PASSWORD = 'Chigdabeast123$'

# === Telegram Bot Token and Username ===
BOT_TOKEN = '8139434770:AAGQNpGzbpeY1FgENcuJ_rctuXOAmRuPVJU'
BOT_USERNAME = 'PayGatePrime_bot'

# === Global chat ID list ===
tele_open_list = []

# === Fetch tele_open values from tele_channel table ===
def fetch_tele_open_list():
    global tele_open_list
    try:
        connection = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = connection.cursor()
        cursor.execute("SELECT tele_open FROM tele_channel")
        rows = cursor.fetchall()
        tele_open_list = [row[0] for row in rows]
        cursor.close()
        connection.close()
    except Exception as e:
        print(f"❌ Error fetching tele_open list: {e}")
        tele_open_list = []

# === Send a message to Telegram and schedule deletion ===
def send_telegram_message(text):
    for chat_id in tele_open_list:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'Markdown'
        }
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            message_id = response.json().get('result', {}).get('message_id')
            if message_id:
                # Schedule deletion after 1 hour (3600 seconds)
                delete_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
                asyncio.get_event_loop().call_later(3600, lambda: requests.post(delete_url, json={
                    'chat_id': chat_id,
                    'message_id': message_id
                }))
        except requests.exceptions.RequestException as e:
            print(f"❌ Error sending message to {chat_id}: {e}")

# === Encode ID to Base64 (2-way hashing) ===
def encode_id(original_id):
    return base64.urlsafe_b64encode(str(original_id).encode()).decode()

# === Decode Base64 back to ID ===
def decode_hash(hash_str):
    return int(base64.urlsafe_b64decode(hash_str.encode()).decode())

# === Fetch all IDs and send messages ===
def fetch_all_ids():
    try:
        connection = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = connection.cursor()
        cursor.execute("SELECT tele_open FROM tele_channel")
        rows = cursor.fetchall()

        id_list = [row[0] for row in rows]
        print("All IDs in tele_open:", id_list)

        for id_val in id_list:
            hash_val = encode_id(id_val)
            url = f"https://t.me/{BOT_USERNAME}?start={hash_val}"
            send_telegram_message(f"Hash: `{hash_val}`\n🔗 [Decode Link]({url})")

        cursor.close()
        connection.close()

    except Exception as e:
        print(f"❌ Error fetching IDs: {e}")

# === Telegram Bot: Decode /start <hash> and report user_id ===
async def start_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    user_id = update.effective_user.id
    if args:
        hash_val = args[0]
        try:
            decoded_id = decode_hash(hash_val)
            await update.message.reply_text(
                f"🔓 Decoded ID from hash: `{decoded_id}`\n👤 User ID: `{user_id}`",
                parse_mode="Markdown"
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Error decoding hash: {e}")
    else:
        await update.message.reply_text("Welcome to PayGatePrime Bot. Use /start <hash> to decode.")

# === Telegram Bot App Setup ===
def create_telegram_app():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command_handler))
    return app

# === Flask route to handle decoding from /start parameter ===
@app.route('/decode_start', methods=['GET'])
def handle_decode_start():
    hash_val = request.args.get('start')
    user_id = request.args.get('user_id', 'unknown')
    if not hash_val:
        return "Missing 'start' parameter", 400
    try:
        original_id = decode_hash(hash_val)
        send_telegram_message(f"🔓 Decoded ID from /start param: {original_id}\n👤 User ID: {user_id}")
        return f"Decoded ID: {original_id}, User ID: {user_id}", 200
    except Exception as e:
        return f"Error decoding hash: {e}", 500

# === Main Execution ===
if __name__ == "__main__":
    fetch_tele_open_list()       # Populate channel ID list
    fetch_all_ids()              # Send messages to each channel
    telegram_app = create_telegram_app()
    loop = asyncio.get_event_loop()
    loop.create_task(telegram_app.run_polling())
    app.run(host='0.0.0.0', port=5000)
