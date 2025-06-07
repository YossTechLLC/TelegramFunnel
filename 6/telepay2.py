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
from json import dumps as _json_dumps
import struct

#!/usr/bin/env python
import os
import logging
import json
from google.cloud import secretmanager
import httpx
from urllib.parse import quote, urlencode

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
    CallbackQueryHandler,
)

# Global Setup
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Flask Setup Start
nest_asyncio.apply()
app = Flask(__name__)

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
    SUB1_TIME_INPUT,
    SUB2_TIME_INPUT,
    SUB3_TIME_INPUT,
) = range(8)

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
            password=DB_PASSWORD,
        ) as conn, conn.cursor() as cur:
            cur.execute("SELECT tele_open, sub_1, sub_1_time, sub_2, sub_2_time, sub_3, sub_3_time FROM tele_channel")
            for (tele_open, s1, s1_time, s2, s2_time, s3, s3_time,) in cur.fetchall():
                tele_open_list.append(tele_open)
                tele_info_open_map[tele_open] = {
                    "sub_1": s1,
                    "sub_1_time": s1_time,
                    "sub_2": s2,
                    "sub_2_time": s2_time,
                    "sub_3": s3,
                    "sub_3_time": s3_time,
                }
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
# ------------------------------------------------------------------------------

# === PostgreSQL Connection Details ===
DB_HOST = '34.58.246.248'
DB_PORT = 5432
DB_NAME = 'client_table'
DB_USER = 'postgres'
DB_PASSWORD = 'Chigdabeast123$'
# ------------------------------------------------------------------------------

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
SUCCESS_URL_SIGNING_KEY = fetch_success_url_signing_key()
# ------------------------------------------------------------------------------

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

# ── inline keyboard builder ────────────────────────────────────────────────
def build_menu_buttons(buttons_config):
    buttons = []
    for b in buttons_config:
        if "callback_data" in b:
            buttons.append(InlineKeyboardButton(text=b["text"], callback_data=b["callback_data"]))
        elif "url" in b:
            buttons.append(InlineKeyboardButton(text=b["text"], url=b["url"]))
    return InlineKeyboardMarkup([buttons])

# ── broadcast ───────────────────────────────────────────────────────────────
def broadcast_hash_links() -> None:
    if not tele_open_list:
        fetch_tele_open_list()
    for chat_id in tele_open_list:
        data = tele_info_open_map.get(chat_id, {})
        base_hash = encode_id(chat_id)
        buttons_cfg = []
        for idx in (1, 2, 3):
            price = data.get(f"sub_{idx}")
            days  = data.get(f"sub_{idx}_time")
            if price is None or days is None:
                continue
            safe_sub = str(price).replace(".", "d")
            token    = f"{base_hash}_{safe_sub}"
            url      = f"https://t.me/{BOT_USERNAME}?start={token}"
            buttons_cfg.append({"text": f"${price} for {days} days", "url": url})
        if not buttons_cfg:
            continue
        reply_markup = build_menu_buttons(buttons_cfg)
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": "<b>Choose your Subscription Tier</b>",
                    "parse_mode": "HTML",
                    "reply_markup": reply_markup.to_dict(),
                },
                timeout=10,
            )
            resp.raise_for_status()
            msg_id = resp.json()["result"]["message_id"]
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
            logging.error("send error to %s: %s", chat_id, e)

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
# ------------------------------------------------------------------------------

def get_telegram_user_id(update):
    """Helper to get Telegram user ID regardless of Command or Callback context."""
    if hasattr(update, "effective_user") and update.effective_user:
        return update.effective_user.id
    if hasattr(update, "callback_query") and update.callback_query and update.callback_query.from_user:
        return update.callback_query.from_user.id
    return None

# NEW: CallbackQuery handler for main menu buttons
async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat.id
    # Route by callback data value
    if data == "CMD_START":
        await context.bot.send_message(chat_id, "You clicked Start!")
    elif data == "CMD_DATABASE":
        await start_database(update, context)
    elif data == "CMD_GATEWAY":
        await start_np_gateway_new(update, context)
    else:
        await context.bot.send_message(chat_id, "Unknown command.")

# Script: Echo Bot
async def start_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global global_sub_value, global_open_channel_id

    chat_id = update.effective_chat.id
    user    = update.effective_user
    args    = context.args[0] if context.args else None

    # deep-link     ----------------------------------------------------------
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
    # menu buttons  ----------------------------------------------------------
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
    # if invoked by plain /start with no token, stop here
    if not context.args:
        return
    # decode token   ---------------------------------------------------------
    try:
        token = context.args[0]
        hash_part, _, sub_part = token.partition("_")
        open_channel_id = decode_hash(hash_part)
        global_open_channel_id = open_channel_id
        sub_raw = sub_part.replace("d", ".") if sub_part else "n/a"
        try:
            local_sub_value = float(sub_raw)
        except ValueError:
            local_sub_value = 15.0
        global_sub_value = local_sub_value
        await context.bot.send_message(
            chat_id,
            f"🔓 Decoded ID: <code>{open_channel_id}</code>\n"
            f"👤 User ID: <code>{user.id}</code>\n"
            f"📦 sub value: <code>{local_sub_value}</code>",
            parse_mode="HTML",
        )
    except Exception as e:
        await context.bot.send_message(chat_id, f"❌ decode error: {e}")
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

def _valid_time(text: str) -> bool:
    return text.isdigit() and 1 <= int(text) <= 999

# ─── /database conversation handlers ───────────────────────────────────────
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

# Utility: encode & sign success url parameters (COMPACT VERSION, with safety)
def build_signed_success_url(tele_open_id, closed_channel_id, signing_key, base_url="https://us-central1-telepay-459221.cloudfunctions.net/success_inv"):
    try:
        tele_open_id = int(tele_open_id)
    except Exception:
        tele_open_id = 0
    try:
        closed_channel_id = int(closed_channel_id)
    except Exception:
        closed_channel_id = 0
    timestamp = int(time.time())
    packed = struct.pack(">QQI", tele_open_id, closed_channel_id, timestamp)
    signature = hmac.new(signing_key.encode(), packed, hashlib.sha256).digest()
    payload = packed + signature
    token = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    return f"{base_url}?token={token}"

# NowPayment NEW PAYMENTS PORTAL (robust for both command and callback context)
async def start_np_gateway_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global global_sub_value
    # Try to get Telegram user id in a robust way:
    user_id = get_telegram_user_id(update)
    if not user_id:
        chat_id = update.effective_chat.id if hasattr(update, "effective_chat") else None
        if chat_id:
            await context.bot.send_message(chat_id, "❌ Could not determine user ID.")
        return
    closed_channel_id = fetch_closed_channel_id()
    if closed_channel_id is None:
        closed_channel_id = 0
    if not SUCCESS_URL_SIGNING_KEY:
        chat_id = update.effective_chat.id if hasattr(update, "effective_chat") else None
        if chat_id:
            await context.bot.send_message(chat_id, "❌ Signing key missing, cannot generate secure URL.")
        return
    secure_success_url = build_signed_success_url(
        tele_open_id=user_id,
        closed_channel_id=closed_channel_id,
        signing_key=SUCCESS_URL_SIGNING_KEY,
    )
    INVOICE_PAYLOAD = {
        "price_amount": global_sub_value,
        "price_currency": "USD",
        "order_id": f"PGP-{user_id}{global_open_channel_id}",
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
            f"{global_sub_value}\n\n"
            "Please click ‘Open Payment Gateway’ below. "
            "You have 20 minutes to complete the payment."
        )
        await bot.send_message(chat_id, text, reply_markup=reply_markup)
    else:
        await bot.send_message(
            chat_id,
            f"nowpayments error ❌ — status {resp.status_code}\n{resp.text}",
        )

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
    fetch_tele_open_list()
    broadcast_hash_links()
    app = main()
    app.run(host="0.0.0.0", port=5000)
