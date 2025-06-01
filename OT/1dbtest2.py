#!/usr/bin/env python
import psycopg2
import requests
import base64
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import nest_asyncio

# ─────────────────────────────────────────────────────────────────────────────
# allow telegram-ext & flask to share the same asyncio event-loop
nest_asyncio.apply()

# ─────────────────────────────  flask app  ───────────────────────────────────
app = Flask(__name__)

# ──────────────────────────  postgres details  ──────────────────────────────
DB_HOST = "34.58.246.248"
DB_PORT = 5432
DB_NAME = "client_table"
DB_USER = "postgres"
DB_PASSWORD = "Chigdabeast123$"

# ────────────────────────  telegram credentials  ────────────────────────────
BOT_TOKEN    = "8139434770:AAGQNpGzbpeY1FgENcuJ_rctuXOAmRuPVJU"
BOT_USERNAME = "PayGatePrime_bot"

# ───────────────────────────  global state  ─────────────────────────────────
tele_open_list: list[int] = []                 # ids only (for iteration order)
tele_info_map: dict[int, dict[str, int]] = {}  # chat_id → {"sub_1": …, …}

# ────────────────────────  sql helper  ──────────────────────────────────────
def fetch_tele_open_list() -> None:
    """
    fill tele_open_list and tele_info_map with rows from tele_channel:
      tele_open, sub_1, sub_2, sub_3
    """
    global tele_open_list, tele_info_map
    tele_open_list.clear()
    tele_info_map.clear()

    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )
        with conn, conn.cursor() as cur:
            cur.execute(
                "SELECT tele_open, sub_1, sub_2, sub_3 "
                "FROM tele_channel"
            )
            for tele_open, sub1, sub2, sub3 in cur.fetchall():
                tele_open_list.append(tele_open)
                tele_info_map[tele_open] = {
                    "sub_1": sub1,
                    "sub_2": sub2,
                    "sub_3": sub3,
                }
    except Exception as exc:
        print(f"❌ error fetching tele_open data: {exc}")

# ───────────────────────  telegram helpers  ─────────────────────────────────
def send_telegram_message(chat_id: int, text: str) -> None:
    """
    send one markdown message to chat_id, auto-delete after 15 s.
    """
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}

    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        msg_id = resp.json()["result"]["message_id"]

        # schedule deletion
        del_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
        asyncio.get_event_loop().call_later(
            15,
            lambda: requests.post(
                del_url,
                json={"chat_id": chat_id, "message_id": msg_id},
                timeout=10,
            ),
        )
    except Exception as exc:
        print(f"❌ error sending message to {chat_id}: {exc}")

# ───────────────────────  hash helpers  ─────────────────────────────────────
encode_id = lambda i: base64.urlsafe_b64encode(str(i).encode()).decode()
decode_hash = lambda s: int(base64.urlsafe_b64decode(s.encode()).decode())

# ─────────────────────  broadcast hash links  ───────────────────────────────
def broadcast_hash_links() -> None:
    """
    each channel gets exactly one message with its hash link.
    """
    if not tele_open_list:
        fetch_tele_open_list()

    for chat_id in tele_open_list:
        hash_val  = encode_id(chat_id)
        hash_link = f"https://t.me/{BOT_USERNAME}?start={hash_val}"
        text      = f"Hash: `{hash_val}`\n🔗 [Decode Link]({hash_link})"
        send_telegram_message(chat_id, text)

# ────────────────────────  bot command /start  ──────────────────────────────
async def start_command_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    args    = context.args
    user_id = update.effective_user.id

    if args:
        hash_val = args[0]
        try:
            decoded_id = decode_hash(hash_val)

            # fetch sub-values if we have them
            subs = tele_info_map.get(decoded_id, {})
            sub_info = (
                f"\n📦 sub_1: `{subs.get('sub_1', 'n/a')}`, "
                f"sub_2: `{subs.get('sub_2', 'n/a')}`, "
                f"sub_3: `{subs.get('sub_3', 'n/a')}`"
                if subs
                else ""
            )

            await update.message.reply_text(
                f"🔓 Decoded ID from hash: `{decoded_id}`\n"
                f"👤 User ID: `{user_id}`{sub_info}",
                parse_mode="Markdown",
            )
        except Exception as exc:
            await update.message.reply_text(f"❌ error decoding hash: {exc}")
    else:
        await update.message.reply_text(
            "welcome to paygateprime bot. use /start <hash> to decode."
        )

# ─────────────────────  telegram app bootstrap  ─────────────────────────────
def create_telegram_app() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command_handler))
    return app

# ────────────────  flask endpoint for external decode  ──────────────────────
@app.route("/decode_start", methods=["GET"])
def handle_decode_start():
    hash_val = request.args.get("start")
    user_id  = request.args.get("user_id", "unknown")
    if not hash_val:
        return "missing 'start' parameter", 400
    try:
        decoded = decode_hash(hash_val)
        subs    = tele_info_map.get(decoded, {})
        sub_txt = (
            f"\n📦 sub_1: `{subs.get('sub_1','n/a')}`, "
            f"sub_2: `{subs.get('sub_2','n/a')}`, "
            f"sub_3: `{subs.get('sub_3','n/a')}`"
            if subs
            else ""
        )
        send_telegram_message(
            decoded,
            f"🔓 decoded ID: {decoded}\n👤 user ID: {user_id}{sub_txt}",
        )
        return f"decoded: {decoded}, user: {user_id}", 200
    except Exception as exc:
        return f"error decoding hash: {exc}", 500

# ───────────────────────────────  main  ─────────────────────────────────────
if __name__ == "__main__":
    fetch_tele_open_list()   # load channels + sub_x values
    broadcast_hash_links()   # one hash per channel

    telegram_app = create_telegram_app()
    loop = asyncio.get_event_loop()
    loop.create_task(telegram_app.run_polling())

    # run flask (blocking) on same event-loop
    app.run(host="0.0.0.0", port=5000)
