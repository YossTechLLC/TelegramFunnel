#!/usr/bin/env python
import psycopg2
import requests
import base64
import asyncio
import hmac
import hashlib
import time
from typing import Tuple
from html import escape
from flask import Flask, request
import nest_asyncio

#!/usr/bin/env python
import os
import logging
import json
from google.cloud import secretmanager
import httpx
from urllib.parse import quote

from telegram import (
    Bot,
    Update,
    ForceReply,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler,
)

# Global Setup
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# ------------------------------------------------------------------------------

# Flask Setup Start
nest_asyncio.apply()
app = Flask(__name__)
# ------------------------------------------------------------------------------

# Global Sub Value
global_sub_value = 5.0
global_open_channel_id = 1.0
global_closed_channel_id = 2.0

# ── globals ─────────────────────────────────────────────────────────────────
tele_open_list: list[int] = []
tele_closed_list: list[int] = []
tele_info_open_map: dict[int, dict[str, int | None]] = {}
tele_info_closed_map: dict[int, dict[str, int | None]] = {}

# Conversation states for /database
(
    TELE_OPEN_INPUT,
    TELE_CLOSED_INPUT,
    SUB1_INPUT,
    SUB2_INPUT,
    SUB3_INPUT,
) = range(5)
# ------------------------------------------------------------------------------

# ── helper lambdas ──────────────────────────────────────────────────────────
encode_id = lambda i: base64.urlsafe_b64encode(str(i).encode()).decode()
decode_hash = lambda s: int(base64.urlsafe_b64decode(s.encode()).decode())

# Fetch TOKENs
def fetch_telegram_token():
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_name = os.getenv("TELEGRAM_BOT_SECRET_NAME")
        if not secret_name:
            raise ValueError("Environment variable TELEGRAM_BOT_SECRET_NAME is not set.")
        secret_path = f"{secret_name}"
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"Error fetching the Telegram bot TOKEN: {e}")
        return None

def fetch_payment_provider_token():
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_name = os.getenv("PAYMENT_PROVIDER_SECRET_NAME")
        if not secret_name:
            raise ValueError("Environment variable PAYMENT_PROVIDER_SECRET_NAME is not set.")
        secret_path = f"{secret_name}"
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"Error fetching the PAYMENT_PROVIDER_TOKEN: {e}")
        return None
    
def fetch_now_webhook_key():
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_name = os.getenv("NOWPAYMENT_WEBHOOK_KEY")
        if not secret_name:
            raise ValueError("Environment variable NOWPAYMENT_WEBHOOK_KEY is not set.")
        secret_path = f"{secret_name}"
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"Error fetching the NOWPAYMENT_WEBHOOK_KEY: {e}")
        return None
# ------------------------------------------------------------------------------

# ── db fetch OPEN ───────────────────────────────────────────────────────────
def fetch_tele_open_list() -> None:
    tele_open_list.clear()
    tele_info_open_map.clear()
    try:
        with psycopg2.connect(
            host=DB_HOST, 
            port=DB_PORT, 
            dbname=DB_NAME,
            user=DB_USER, 
            password=DB_PASSWORD
        ) as conn, conn.cursor() as cur:
            cur.execute("SELECT tele_open, sub_1, sub_2, sub_3 FROM tele_channel")
            for tele_open, s1, s2, s3 in cur.fetchall():
                tele_open_list.append(tele_open)
                tele_info_open_map[tele_open] = {"sub_1": s1, "sub_2": s2, "sub_3": s3}
    except Exception as e:
        print("db tele_open error:", e)

# ── db fetch CLOSED ────────────────────────────────────────────────────────-
def fetch_tele_closed_list() -> None:
    tele_closed_list.clear()
    tele_info_closed_map.clear()
    try:
        with psycopg2.connect(
            host=DB_HOST, 
            port=DB_PORT, 
            dbname=DB_NAME,
            user=DB_USER, 
            password=DB_PASSWORD
        ) as conn, conn.cursor() as cur:
            cur.execute("SELECT tele_open, tele_closed FROM tele_channel")
            for tele_closed, o1 in cur.fetchall():
                tele_open_list.append(tele_closed)
                tele_info_closed_map[tele_closed] = {"tele_closed": o1}
    except Exception as e:
        print("db tele_closed error:", e)

def fetch_closed_channel_id():
    global global_closed_channel_id
    global global_open_channel_id
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT tele_closed FROM tele_channel WHERE tele_open::bigint = %s", (global_open_channel_id,))
        result = cur.fetchone()
        if result:
            global_closed_channel_id = result[0]
        else:
            print("❌ No matching record found for tele_open =", global_open_channel_id)
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Error fetching tele_closed: {e}")

    return global_closed_channel_id

# === PostgreSQL Connection Details ===
DB_HOST = '34.58.246.248'
DB_PORT = 5432
DB_NAME = 'client_table'
DB_USER = 'postgres'
DB_PASSWORD = 'Chigdabeast123$'

# PostgreSQL Connection
def get_db_connection():
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )
# ------------------------------------------------------------------------------

# ── config ──────────────────────────────────────────────────────────────────
BOT_TOKEN = fetch_telegram_token()
BOT_USERNAME = "PayGatePrime_bot"
NOW_WEBHOOK_KEY = fetch_now_webhook_key()

# ── telegram send ───────────────────────────────────────────────────────────
def send_message(chat_id: int, html_text: str) -> None:
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": html_text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        r.raise_for_status()
        msg_id = r.json()["result"]["message_id"]
        # auto-delete after 15 s
        del_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
        asyncio.get_event_loop().call_later(
            60,
            lambda: requests.post(
                del_url,
                json={"chat_id": chat_id, "message_id": msg_id},
                timeout=5,
            ),
        )
    except Exception as e:
        print(f"❌ send error to {chat_id}: {e}")

# ── broadcast ───────────────────────────────────────────────────────────────
def broadcast_hash_links() -> None:
    if not tele_open_list:
        fetch_tele_open_list()
    for chat_id in tele_open_list:
        subs = tele_info_open_map.get(chat_id, {})
        base_hash = encode_id(chat_id)
        lines = ["<b>decode links:</b>"]
        for key in ("sub_1", "sub_2", "sub_3"):
            val = subs.get(key)
            safe_sub = str(val).replace(".", "d")  
            if val is None:
                continue
            token = f"{base_hash}_{safe_sub}"
            url   = f"https://t.me/{BOT_USERNAME}?start={token}"
            lines.append(
                f"• {escape(key)} <b>{val}</b> → <a href=\"{escape(url)}\">link</a>"
            )
        send_message(chat_id, "\n".join(lines))

def decode_start():
    token = (request.args.get("start") or request.form.get("start"))
    user = request.args.get("tele_open_id", "unknown")

    if not token:
        return "missing start", 400
    try:
        hash_part, _, sub_part = token.partition("_")
        sub = sub_part.replace("d", ".") 
        open_channel_id = decode_hash(hash_part)
        send_message(
            open_channel_id,
            f"🔓 decoded ID: <code>{open_channel_id}</code>\n"
            f"👤 user: <code>{escape(user)}</code>\n"
            f"📦 sub value: <code>{escape(sub or 'n/a')}</code>",
        )
        return "ok", 200
    except Exception as e:
        return f"err {e}", 500
####################################################### BUNLDE ###############

# Script: Echo Bot
async def start_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global global_sub_value
    global global_open_channel_id
    user = update.effective_user
    args = context.args[0] if context.args else None

    if args and '-' in args:
        try:
            chat_part, channel_part, cmd = args.split('-', 2)
            await update.message.reply_text(f"🔍 Parsed tele_open_id: {chat_part}, channel_id: {channel_part}")

            if cmd == "start_np_gateway_new":
                await start_np_gateway_new(update, context)
                return
            elif cmd == "database":
                await start_database(update, context)
                return
        except Exception as e:
            await update.message.reply_text(f"❌ could not parse command: {e}")
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! (EchoBot) - here are the commands you are use right now /start /database /start_np_gateway_new",
        reply_markup=ForceReply(selective=True),
    )
    if not context.args:
        await update.message.reply_text(
            "welcome – use /start &lt;hash_sub&gt; to decode.", parse_mode="HTML"
        )
        return
    try:
        token = context.args[0]
        hash_part, _, sub_part = token.partition("_")
        open_channel_id  = decode_hash(hash_part)
        global_open_channel_id = open_channel_id
        sub = sub_part.replace("d", ".") if sub_part else "n/a"
        try:
            local_sub_value = float(sub)
        except ValueError:
            local_sub_value = 15
        global_sub_value = local_sub_value
        await update.message.reply_text(
            f"🔓 Decoded ID: <code>{open_channel_id}</code>\n"
            f"👤 User ID: <code>{update.effective_user.id}</code>\n"
            f"📦 sub value: <code>{local_sub_value}</code>",
            parse_mode="HTML",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ decode error: {e}")
# ------------------------------------------------------------------------------

# ─── helpers ────────────────────────────────────────────────────────────────
def _valid_channel_id(text: str) -> bool:
    if text.lstrip("-").isdigit():
        return len(text) <= 14
    return False

def _valid_sub(text: str) -> bool:
    try:
        val = float(text)
    except ValueError:
        return False
    if not (0 <= val <= 9999.99):
        return False
    parts = text.split(".")
    return len(parts) == 1 or len(parts[1]) <= 2
# ------------------------------------------------------------------------------

# ─── /database conversation handlers ───────────────────────────────────────
async def start_database(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text("Enter *tele_open* (≤14 chars integer):", parse_mode="Markdown")
    return TELE_OPEN_INPUT

async def receive_tele_open(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if _valid_channel_id(update.message.text):
        ctx.user_data["tele_open"] = int(update.message.text)
        await update.message.reply_text("Enter *tele_closed* (≤14 chars integer):", parse_mode="Markdown")
        return TELE_CLOSED_INPUT
    await update.message.reply_text("❌ Invalid tele_open. Try again:")
    return TELE_OPEN_INPUT

async def receive_tele_closed(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if _valid_channel_id(update.message.text):
        ctx.user_data["tele_closed"] = int(update.message.text)
        await update.message.reply_text("Enter *sub_1* (0-9999.99):", parse_mode="Markdown")
        return SUB1_INPUT
    await update.message.reply_text("❌ Invalid tele_closed. Try again:")
    return TELE_CLOSED_INPUT

def _sub_handler(idx_key: str, next_state: int, prompt: str):
    async def inner(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if _valid_sub(update.message.text):
            ctx.user_data[idx_key] = float(update.message.text)
            await update.message.reply_text(prompt, parse_mode="Markdown")
            return next_state
        await update.message.reply_text(
            "❌ Invalid value. Must be 0-9999.99 with ≤2 decimals. Try again:"
        )
        return update.handler  # stay in the same state
    return inner

receive_sub1 = _sub_handler("sub_1", SUB2_INPUT, "Enter *sub_2* (0-9999.99):")
receive_sub2 = _sub_handler("sub_2", SUB3_INPUT, "Enter *sub_3* (0-9999.99):")

async def receive_sub3(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _valid_sub(update.message.text):
        await update.message.reply_text("❌ Invalid value. Try sub_3 again:")
        return SUB3_INPUT

    ctx.user_data["sub_3"] = float(update.message.text)

    vals = (
        ctx.user_data["tele_open"],
        ctx.user_data["tele_closed"],
        ctx.user_data["sub_1"],
        ctx.user_data["sub_2"],
        ctx.user_data["sub_3"],
    )

    try:
        conn = get_db_connection()
        with conn, conn.cursor() as cur:
            cur.execute(
                """INSERT INTO tele_channel
                   (tele_open, tele_closed, sub_1, sub_2, sub_3)
                   VALUES (%s, %s, %s, %s, %s)""",
                vals,
            )
        await update.message.reply_text(
            "✅ Saved:\n"
            f"tele_open={vals[0]}, tele_closed={vals[1]}, "
            f"sub_1={vals[2]}, sub_2={vals[3]}, sub_3={vals[4]}"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ DB error: {e}")

    ctx.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text("❌ Operation cancelled.")
    return ConversationHandler.END
# ------------------------------------------------------------------------------

# NowPayment NEW PAYMENTS PORTAL
async def start_np_gateway_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global global_sub_value
    closed_channel_id = fetch_closed_channel_id()
    INVOICE_PAYLOAD = {
        "price_amount": global_sub_value,
        "price_currency": "USD",
        "order_id": f"PGP-{update.effective_user.id}{global_open_channel_id}",
        "order_description": "Payment-Test-1",
        "success_url": f"https://us-central1-telepay-459221.cloudfunctions.net/success_inv?tele_open_id={update.effective_user.id}&closed_channel_id={closed_channel_id}",
        "is_fixed_rate": False,
        "is_fee_paid_by_user": False
            }
    headers = {
        "x-api-key": fetch_payment_provider_token(),
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.nowpayments.io/v1/invoice",
            headers=headers,
            json=INVOICE_PAYLOAD,
        )

    if resp.status_code == 200:
        data = resp.json()
        invoice_url = data.get("invoice_url", "<no url>")
        await update.message.reply_text(
            f"{closed_channel_id} - {update.effective_user.id} - {global_sub_value} - test invite - https://us-central1-telepay-459221.cloudfunctions.net/success_inv?tele_open_id={update.effective_user.id}&closed_channel_id={closed_channel_id} Please click on the 'Open Payment Gateway' button you see at the bottom of the screen to inniate the payment process - You have a 20 minute window within which you can submit the payment, if the payment isn't submitted withint that timeframe you will need to request the payment gateway again - thank you!",
            reply_markup=ReplyKeyboardMarkup.from_button(
            KeyboardButton(
                text="Open Payment Gateway",
                web_app=WebAppInfo(url=invoice_url),
            )
        ),
    )
    else:
        await update.message.reply_text(
            f"nowpayments error ❌ — status {resp.status_code}\n{resp.text}"
        )
# ------------------------------------------------------------------------------

# Main Entry
def main():
    telegram_token = fetch_telegram_token()
    payment_provider_token = fetch_payment_provider_token()

    if not telegram_token:
        raise RuntimeError("Bot cannot start: TELEGRAM_BOT_SECRET_NAME is missing or invalid.")
    if not payment_provider_token:
        raise RuntimeError("Bot cannot start: PAYMENT_PROVIDER_SECRET_NAME is missing or invalid.")
    
    application = Application.builder().token(telegram_token).build()

    database_handler = ConversationHandler(
        entry_points=[CommandHandler("database", start_database)],
        states={
            TELE_OPEN_INPUT : [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_tele_open)],
            TELE_CLOSED_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_tele_closed)],
            SUB1_INPUT      : [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_sub1)],
            SUB2_INPUT      : [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_sub2)],
            SUB3_INPUT      : [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_sub3)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(database_handler)

    # Echo bot (last to avoid overriding input during conversation)
    application.add_handler(CommandHandler("start", start_bot))
    application.add_handler(CommandHandler("start_np_gateway_new", start_np_gateway_new))
    application.run_polling(allowed_updates=Update.ALL_TYPES)
    return application
# ------------------------------------------------------------------------------

# START MAIN    
if __name__ == "__main__":
    fetch_tele_open_list()
    broadcast_hash_links()
    app = main()
    app.run(host="0.0.0.0", port=5000)
# ------------------------------------------------------------------------------
