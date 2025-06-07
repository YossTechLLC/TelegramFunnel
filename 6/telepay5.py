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
import struct
import os
import logging
import json
from google.cloud import secretmanager
import httpx
from urllib.parse import quote, urlencode

from telegram import (
    Bot,
    Update,
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
    CallbackQueryHandler,
)

# Setup
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
nest_asyncio.apply()
app = Flask(__name__)

# DB Config
DB_HOST = '34.58.246.248'
DB_PORT = 5432
DB_NAME = 'client_table'
DB_USER = 'postgres'
DB_PASSWORD = 'Chigdabeast123$'

def get_db_connection():
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )

# Secure keys (via GCP secretmanager)
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

def fetch_success_url_signing_key():
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_name = os.getenv("SUCCESS_URL_SIGNING_KEY")
        if not secret_name:
            raise ValueError("Environment variable SUCCESS_URL_SIGNING_KEY is not set.")
        secret_path = f"{secret_name}"
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"Error fetching the SUCCESS_URL_SIGNING_KEY: {e}")
        return None

# ── Conversation states for /database
(
    TELE_OPEN_INPUT,
    TELE_CLOSED_INPUT,
    SUB1_INPUT,
    SUB2_INPUT,
    SUB3_INPUT,
    SUB1_TIME_INPUT,
    SUB2_TIME_INPUT,
    SUB3_TIME_INPUT,
) = range(8)

# ── DB fetch helpers ───────────────────────────────────────────────────────────
def fetch_closed_channel_id(open_channel_id):
    """Looks up closed_channel_id in DB, given an open_channel_id (both as string)."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        print(f"[DEBUG] Looking up closed_channel_id for tele_open: {str(open_channel_id)}")
        cur.execute("SELECT tele_closed FROM tele_channel WHERE tele_open = %s", (str(open_channel_id),))
        result = cur.fetchone()
        print(f"[DEBUG] fetch_closed_channel_id result: {result}")
        cur.close()
        conn.close()
        if result and result[0]:
            return result[0]
        else:
            print(f"❌ No matching record found for tele_open = {open_channel_id}")
            return None
    except Exception as e:
        print(f"❌ Error fetching tele_closed: {e}")
        return None

# Encode and sign success url
def safe_int64(val):
    try:
        val = int(val)
        if val < 0:
            val = 2**64 + val  # pack negative numbers as unsigned
        if val > 2**64 - 1:
            val = 2**64 - 1
    except Exception:
        val = 0
    return val

def build_signed_success_url(tele_open_id, closed_channel_id, signing_key, base_url="https://invite-webhook-291176869049.us-central1.run.app"):
    tele_open_id = safe_int64(tele_open_id)
    closed_channel_id = safe_int64(closed_channel_id)
    timestamp = int(time.time())
    print(f"[DEBUG] Packing for token: tele_open_id={tele_open_id}, closed_channel_id={closed_channel_id}, timestamp={timestamp}")
    packed = struct.pack(">QQI", tele_open_id, closed_channel_id, timestamp)
    signature = hmac.new(signing_key.encode(), packed, hashlib.sha256).digest()
    payload = packed + signature
    token = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    return f"{base_url}?token={token}"

def get_telegram_user_id(update):
    if hasattr(update, "effective_user") and update.effective_user:
        return update.effective_user.id
    if hasattr(update, "callback_query") and update.callback_query and update.callback_query.from_user:
        return update.callback_query.from_user.id
    return None

def build_menu_buttons(buttons_config):
    buttons = []
    for b in buttons_config:
        if "callback_data" in b:
            buttons.append(InlineKeyboardButton(text=b["text"], callback_data=b["callback_data"]))
        elif "url" in b:
            buttons.append(InlineKeyboardButton(text=b["text"], url=b["url"]))
    return InlineKeyboardMarkup([buttons])

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat.id
    if data == "CMD_START":
        await context.bot.send_message(chat_id, "You clicked Start!")
    elif data == "CMD_DATABASE":
        await start_database(update, context)
    elif data == "CMD_GATEWAY":
        await start_np_gateway_new(update, context)
    else:
        await context.bot.send_message(chat_id, "Unknown command.")

# /start handler
async def start_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user    = update.effective_user
    args    = context.args[0] if context.args else None

    if args and '-' in args:
        try:
            chat_part, channel_part, cmd = args.split('-', 2)
            await context.bot.send_message(
                chat_id,
                f"🔍 Parsed tele_open_id: {chat_part}, channel_id: {channel_part}",
            )
            if cmd == "start_np_gateway_new":
                await start_np_gateway_new(update, context)
                return
            elif cmd == "database":
                await start_database(update, context)
                return
        except Exception as e:
            await context.bot.send_message(chat_id, f"❌ could not parse command: {e}")
    buttons_cfg = [
        {"text": "Start", "callback_data": "CMD_START"},
        {"text": "Database", "callback_data": "CMD_DATABASE"},
        {"text": "Payment Gateway", "callback_data": "CMD_GATEWAY"},
    ]
    keyboard = build_menu_buttons(buttons_cfg)
    await context.bot.send_message(
        chat_id,
        rf"Hi {user.mention_html()}! 👋",
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    if not context.args:
        return
    try:
        token = context.args[0]
        hash_part, _, sub_part = token.partition("_")
        open_channel_id = base64.urlsafe_b64decode(hash_part.encode()).decode()
        sub_raw = sub_part.replace("d", ".") if sub_part else "n/a"
        try:
            local_sub_value = float(sub_raw)
        except ValueError:
            local_sub_value = 15.0
        await context.bot.send_message(
            chat_id,
            f"🔓 Decoded ID: <code>{open_channel_id}</code>\n"
            f"👤 User ID: <code>{user.id}</code>\n"
            f"📦 sub value: <code>{local_sub_value}</code>",
            parse_mode="HTML",
        )
    except Exception as e:
        await context.bot.send_message(chat_id, f"❌ decode error: {e}")

# Payment handler
async def start_np_gateway_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = get_telegram_user_id(update)
    if not user_id:
        chat_id = update.effective_chat.id if hasattr(update, "effective_chat") else None
        if chat_id:
            await context.bot.send_message(chat_id, "❌ Could not determine user ID.")
        return

    open_channel_id = str(update.effective_chat.id)
    closed_channel_id = fetch_closed_channel_id(open_channel_id)
    if not closed_channel_id:
        chat_id = update.effective_chat.id if hasattr(update, "effective_chat") else update.callback_query.message.chat.id
        await context.bot.send_message(chat_id, f"❌ Could not find a closed_channel_id for open_channel_id {open_channel_id}. Please check your database!")
        return

    signing_key = fetch_success_url_signing_key()
    if not signing_key:
        chat_id = update.effective_chat.id if hasattr(update, "effective_chat") else None
        if chat_id:
            await context.bot.send_message(chat_id, "❌ Signing key missing, cannot generate secure URL.")
        return

    secure_success_url = build_signed_success_url(
        tele_open_id=user_id,
        closed_channel_id=closed_channel_id,
        signing_key=signing_key,
    )
    global_sub_value = 5.0  # set/lookup as needed

    INVOICE_PAYLOAD = {
        "price_amount": global_sub_value,
        "price_currency": "USD",
        "order_id": f"PGP-{user_id}-{open_channel_id}",
        "order_description": "Payment-Test-1",
        "success_url": secure_success_url,
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
    chat_id = update.effective_chat.id if hasattr(update, "effective_chat") else update.callback_query.message.chat.id
    bot     = context.bot
    if resp.status_code == 200:
        invoice_url = resp.json().get("invoice_url", "<no url>")
        reply_markup = ReplyKeyboardMarkup.from_button(
            KeyboardButton(
                text="Open Payment Gateway",
                web_app=WebAppInfo(url=invoice_url),
            )
        )
        text = (
            f"{closed_channel_id} – {user_id} – "
            f"{global_sub_value}\n"
            f"{secure_success_url}\n\n"
            "Please click ‘Open Payment Gateway’ below. "
            "You have 20 minutes to complete the payment."
        )
        await bot.send_message(chat_id, text, reply_markup=reply_markup)
    else:
        await bot.send_message(
            chat_id,
            f"nowpayments error ❌ — status {resp.status_code}\n{resp.text}",
        )

# --- /database logic ---
def _valid_channel_id(text: str) -> bool:
    return text.lstrip("-").isdigit() and len(text) <= 14

def _valid_sub(text: str) -> bool:
    try:
        val = float(text)
    except ValueError:
        return False
    if not (0 <= val <= 9999.99):
        return False
    parts = text.split(".")
    return len(parts) == 1 or len(parts[1]) <= 2

def _valid_time(text: str) -> bool:
    return text.isdigit() and 1 <= int(text) <= 999

async def start_database(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    chat_id = update.effective_chat.id if hasattr(update, "effective_chat") else update.callback_query.message.chat.id
    await ctx.bot.send_message(
        chat_id,
        "Enter *tele_open* (≤14 chars integer):",
        parse_mode="Markdown",
    )
    return TELE_OPEN_INPUT

async def receive_tele_open(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if _valid_channel_id(update.message.text):
        ctx.user_data["tele_open"] = update.message.text.strip()
        await update.message.reply_text("Enter *tele_closed* (≤14 chars integer):", parse_mode="Markdown")
        return TELE_CLOSED_INPUT
    await update.message.reply_text("❌ Invalid tele_open. Try again:")
    return TELE_OPEN_INPUT

async def receive_tele_closed(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if _valid_channel_id(update.message.text):
        ctx.user_data["tele_closed"] = update.message.text.strip()
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
        await update.message.reply_text("❌ Invalid sub value. Try again:")
        return SUB1_INPUT if idx_key == "sub_1" else SUB2_INPUT if idx_key == "sub_2" else SUB3_INPUT
    return inner

def _time_handler(idx_key: str, next_state: int, prompt: str):
    async def inner(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if _valid_time(update.message.text):
            ctx.user_data[idx_key] = int(update.message.text)
            await update.message.reply_text(prompt, parse_mode="Markdown")
            return next_state
        await update.message.reply_text("❌ Invalid time (1-999). Try again:")
        return SUB1_TIME_INPUT if idx_key == "sub_1_time" else SUB2_TIME_INPUT if idx_key == "sub_2_time" else SUB3_TIME_INPUT
    return inner

receive_sub1       = _sub_handler ("sub_1",       SUB1_TIME_INPUT, "Enter *sub_1_time* (1-999):")
receive_sub1_time  = _time_handler("sub_1_time",  SUB2_INPUT,      "Enter *sub_2* (0-9999.99):")
receive_sub2       = _sub_handler ("sub_2",       SUB2_TIME_INPUT, "Enter *sub_2_time* (1-999):")
receive_sub2_time  = _time_handler("sub_2_time",  SUB3_INPUT,      "Enter *sub_3* (0-9999.99):")
receive_sub3       = _sub_handler ("sub_3",       SUB3_TIME_INPUT, "Enter *sub_3_time* (1-999):")

async def receive_sub3_time(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _valid_time(update.message.text):
        await update.message.reply_text("❌ Invalid time. Try sub_3_time again:")
        return SUB3_TIME_INPUT
    ctx.user_data["sub_3_time"] = int(update.message.text)
    vals = (
        ctx.user_data["tele_open"],
        ctx.user_data["tele_closed"],
        ctx.user_data["sub_1"],
        ctx.user_data["sub_1_time"],
        ctx.user_data["sub_2"],
        ctx.user_data["sub_2_time"],
        ctx.user_data["sub_3"],
        ctx.user_data["sub_3_time"],
    )
    try:
        conn = get_db_connection()
        with conn, conn.cursor() as cur:
            cur.execute(
                """INSERT INTO tele_channel
                   (tele_open, tele_closed,
                    sub_1, sub_1_time,
                    sub_2, sub_2_time,
                    sub_3, sub_3_time)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                vals,
            )
        await update.message.reply_text(
            "✅ Saved:\n"
            f"tele_open={vals[0]}, tele_closed={vals[1]},\n"
            f"sub_1={vals[2]} ({vals[3]}), sub_2={vals[4]} ({vals[5]}), sub_3={vals[6]} ({vals[7]})"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ DB error: {e}")
    ctx.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text("❌ Operation cancelled.")
    return ConversationHandler.END

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
            TELE_OPEN_INPUT   : [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_tele_open)],
            TELE_CLOSED_INPUT : [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_tele_closed)],
            SUB1_INPUT        : [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_sub1)],
            SUB1_TIME_INPUT   : [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_sub1_time)],
            SUB2_INPUT        : [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_sub2)],
            SUB2_TIME_INPUT   : [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_sub2_time)],
            SUB3_INPUT        : [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_sub3)],
            SUB3_TIME_INPUT   : [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_sub3_time)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(database_handler)
    application.add_handler(CommandHandler("start", start_bot))
    application.add_handler(CommandHandler("start_np_gateway_new", start_np_gateway_new))
    application.add_handler(CallbackQueryHandler(main_menu_callback))
    application.run_polling(allowed_updates=Update.ALL_TYPES)
    return application

if __name__ == "__main__":
    app = main()
    app.run(host="0.0.0.0", port=5000)
