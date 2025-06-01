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

# ──────────────────────────────────────────────────────────────────────────────
# patch the event loop so telegram-ext & flask can coexist
nest_asyncio.apply()

# ─────────────────────────────  flask stub  ───────────────────────────────────
app = Flask(__name__)

# ─────────────────────────  postgres connection  ─────────────────────────────
DB_HOST = '34.58.246.248'
DB_PORT = 5432
DB_NAME = 'client_table'
DB_USER = 'postgres'
DB_PASSWORD = 'Chigdabeast123$'

# ───────────────────────  telegram bot credentials  ──────────────────────────
BOT_TOKEN    = '8139434770:AAGQNpGzbpeY1FgENcuJ_rctuXOAmRuPVJU'
BOT_USERNAME = 'PayGatePrime_bot'

# ───────────────────────────  global state  ──────────────────────────────────
tele_open_list: list[int] = []       # channel chat_ids to message

# ──────────────────────  sql helpers  ────────────────────────────────────────
def fetch_tele_open_list() -> None:
    """
    populate tele_open_list with channel chat_ids from tele_channel.tele_open.
    """
    global tele_open_list
    try:
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
            user=DB_USER, password=DB_PASSWORD
        )
        with conn, conn.cursor() as cur:
            cur.execute("SELECT tele_open FROM tele_channel")
            tele_open_list = [row[0] for row in cur.fetchall()]
    except Exception as exc:
        print(f"❌ error fetching tele_open list: {exc}")
        tele_open_list = []

# ────────────────────  telegram messaging helpers  ───────────────────────────
def send_telegram_message(chat_id: int, text: str) -> None:
    """
    send *one* markdown message to a single chat_id and schedule deletion
    after 1 hour. no more cross-posting to other channels.
    """
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        resp = requests.post(url, json=payload)
        resp.raise_for_status()
        message_id = resp.json().get("result", {}).get("message_id")

        if message_id:
            # schedule deletion after 3600 s
            delete_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
            asyncio.get_event_loop().call_later(
                3600,
                lambda: requests.post(
                    delete_url,
                    json={"chat_id": chat_id, "message_id": message_id}
                )
            )
    except requests.exceptions.RequestException as exc:
        print(f"❌ error sending message to {chat_id}: {exc}")

# ─────────────────────────  hash helpers  ─────────────────────────────────────
def encode_id(original_id: int) -> str:
    return base64.urlsafe_b64encode(str(original_id).encode()).decode()

def decode_hash(hash_str: str) -> int:
    return int(base64.urlsafe_b64decode(hash_str.encode()).decode())

# ─────────────────────  broadcast hash links  ────────────────────────────────
def broadcast_hash_links() -> None:
    """
    iterate over tele_open_list once; each channel gets *exactly one* message
    containing its own hash & deep-link.
    """
    if not tele_open_list:
        fetch_tele_open_list()

    for chat_id in tele_open_list:
        hash_val = encode_id(chat_id)                          # hash matches the same id
        deep_link = f"https://t.me/{BOT_USERNAME}?start={hash_val}"
        text = f"Hash: `{hash_val}`\n🔗 [Decode Link]({deep_link})"
        send_telegram_message(chat_id, text)

# ───────────────────────────  bot handler  ───────────────────────────────────
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
        except Exception as exc:
            await update.message.reply_text(f"❌ error decoding hash: {exc}")
    else:
        await update.message.reply_text(
            "welcome to paygateprime bot. use /start <hash> to decode."
        )

# ─────────────────────  telegram app bootstrap  ──────────────────────────────
def create_telegram_app() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command_handler))
    return app

# ────────────────  flask endpoint for external decode  ───────────────────────
@app.route("/decode_start", methods=["GET"])
def handle_decode_start():
    hash_val = request.args.get("start")
    user_id  = request.args.get("user_id", "unknown")
    if not hash_val:
        return "missing 'start' parameter", 400
    try:
        original_id = decode_hash(hash_val)
        send_telegram_message(
            original_id,
            f"🔓 decoded ID from /start param: {original_id}\n👤 user ID: {user_id}"
        )
        return f"decoded ID: {original_id}, user ID: {user_id}", 200
    except Exception as exc:
        return f"error decoding hash: {exc}", 500

# ───────────────────────────────  main  ──────────────────────────────────────
if __name__ == "__main__":
    fetch_tele_open_list()        # load channel ids
    broadcast_hash_links()        # send exactly one message per channel

    telegram_app = create_telegram_app()
    loop = asyncio.get_event_loop()
    loop.create_task(telegram_app.run_polling())

    # run flask (blocking) on the same event loop
    app.run(host="0.0.0.0", port=5000)
