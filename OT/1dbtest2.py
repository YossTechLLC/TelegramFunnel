#!/usr/bin/env python
import psycopg2
import requests
import base64
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import nest_asyncio

# ──────────────────────────  event-loop patch  ──────────────────────────────
nest_asyncio.apply()

# ──────────────────────────────  flask app  ─────────────────────────────────
app = Flask(__name__)

# ─────────────────────────  postgres details  ───────────────────────────────
DB_HOST = "34.58.246.248"
DB_PORT = 5432
DB_NAME = "client_table"
DB_USER = "postgres"
DB_PASSWORD = "Chigdabeast123$"

# ─────────────────────  telegram credentials  ───────────────────────────────
BOT_TOKEN    = "8139434770:AAGQNpGzbpeY1FgENcuJ_rctuXOAmRuPVJU"
BOT_USERNAME = "PayGatePrime_bot"

# ────────────────────────  global structures  ───────────────────────────────
tele_open_list: list[int]                     = []            # channel ids
tele_info_map: dict[int, dict[str, int | None]] = {}          # id → subs

# ───────────────────────────  helpers  ──────────────────────────────────────
encode_id = lambda i: base64.urlsafe_b64encode(str(i).encode()).decode()
decode_hash = lambda s: int(base64.urlsafe_b64decode(s.encode()).decode())

def fetch_tele_open_list() -> None:
    """load tele_open plus sub_1/2/3 into memory."""
    tele_open_list.clear()
    tele_info_map.clear()
    try:
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT,
            dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
        )
        with conn, conn.cursor() as cur:
            cur.execute(
                "SELECT tele_open, sub_1, sub_2, sub_3 FROM tele_channel"
            )
            for tele_open, s1, s2, s3 in cur.fetchall():
                tele_open_list.append(tele_open)
                tele_info_map[tele_open] = {"sub_1": s1, "sub_2": s2, "sub_3": s3}
    except Exception as exc:
        print(f"❌ DB load error: {exc}")

def send_telegram_message(chat_id: int, text: str) -> None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(
            url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=10
        )
        r.raise_for_status()
        msg_id = r.json()["result"]["message_id"]
        del_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
        asyncio.get_event_loop().call_later(
            15,
            lambda: requests.post(
                del_url,
                json={"chat_id": chat_id, "message_id": msg_id},
                timeout=5,
            ),
        )
    except Exception as exc:
        print(f"❌ send error to {chat_id}: {exc}")

# ───────────────────  broadcast with per-sub links  ─────────────────────────
def broadcast_hash_links() -> None:
    """each channel gets links for its sub_1, sub_2, sub_3 values."""
    if not tele_open_list:
        fetch_tele_open_list()

    for chat_id in tele_open_list:
        subs = tele_info_map.get(chat_id, {})
        base_hash = encode_id(chat_id)

        lines = ["*decode links:*"]  # first markdown line (asterisk ok)
        for sub_key in ("sub_1", "sub_2", "sub_3"):
            sub_val = subs.get(sub_key)
            if sub_val is None:
                continue
            # embed both pieces in the start param: <hash>_<subval>
            start_param = f"{base_hash}_{sub_val}"
            link = f"https://t.me/{BOT_USERNAME}?start={start_param}"
            # label the link with its sub value
            lines.append(f"• {sub_key} `{sub_val}` → [link]({link})")

        send_telegram_message(chat_id, "\n".join(lines))

# ────────────────────────  /start handler  ──────────────────────────────────
async def start_command_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    args    = context.args
    user_id = update.effective_user.id

    if not args:
        await update.message.reply_text(
            "welcome to paygateprime bot. use /start <hash_sub> to decode."
        )
        return

    try:
        # parse "<hash>_<subval>" or just "<hash>"
        token       = args[0]
        hash_part, sep, sub_part = token.partition("_")
        decoded_id  = decode_hash(hash_part)
        sub_string  = f"`{sub_part}`" if sep else "`n/a`"

        await update.message.reply_text(
            f"🔓 Decoded ID: `{decoded_id}`\n"
            f"👤 User ID: `{user_id}`\n"
            f"📦 sub value: {sub_string}",
            parse_mode="Markdown"
        )
    except Exception as exc:
        await update.message.reply_text(f"❌ decode error: {exc}")

def make_bot() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command_handler))
    return app

# ────────────────  flask endpoint  ──────────────────────────────────────────
@app.route("/decode_start", methods=["GET"])
def decode_start():
    param  = request.args.get("start")
    user   = request.args.get("user_id", "unknown")

    if not param:
        return "missing start", 400
    try:
        hash_part, sep, sub_part = param.partition("_")
        cid = decode_hash(hash_part)
        sub_txt = sub_part if sep else "n/a"
        send_telegram_message(
            cid,
            f"🔓 decoded ID: {cid}\n👤 user: {user}\n📦 sub value: `{sub_txt}`"
        )
        return "ok", 200
    except Exception as exc:
        return f"err {exc}", 500

# ─────────────────────────────── main  ──────────────────────────────────────
if __name__ == "__main__":
    fetch_tele_open_list()
    broadcast_hash_links()

    bot_app = make_bot()
    loop = asyncio.get_event_loop()
    loop.create_task(bot_app.run_polling())

    app.run(host="0.0.0.0", port=5000)
