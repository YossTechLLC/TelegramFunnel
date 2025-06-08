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
from google.cloud import secretmanager
import httpx

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    WebAppInfo,
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

# --- Global Setup ---
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
nest_asyncio.apply()
flask_app = Flask(__name__)

global_sub_value = 5.0
global_open_channel_id = ""  # Always str for varchar compatibility
global_closed_channel_id = ""

tele_open_list: list[str] = []
tele_closed_list: list[str] = []
tele_info_open_map: dict[str, dict[str, int | None]] = {}

# Carousel states for /database carousel (single state, all navigation via callback)
CAROUSEL = range(1)

DB_HOST = '34.58.246.248'
DB_PORT = 5432
DB_NAME = 'client_table'
DB_USER = 'postgres'
DB_PASSWORD = 'Chigdabeast123$'

BOT_USERNAME = "PayGatePrime_bot"
encode_id = lambda i: base64.urlsafe_b64encode(str(i).encode()).decode()
decode_hash = lambda s: base64.urlsafe_b64decode(s.encode()).decode()

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

def fetch_closed_channel_id(open_channel_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT tele_closed FROM tele_channel WHERE tele_open = %s", (str(open_channel_id),))
        result = cur.fetchone()
        cur.close()
        conn.close()
        if result and result[0]:
            return result[0]
        else:
            print("❌ No matching record found for tele_open =", open_channel_id)
            return None
    except Exception as e:
        print(f"❌ Error fetching tele_closed: {e}")
        return None

def get_db_connection():
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )

BOT_TOKEN = fetch_telegram_token()
NOW_WEBHOOK_KEY = fetch_now_webhook_key()
SUCCESS_URL_SIGNING_KEY = fetch_success_url_signing_key()

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

# ----------- Carousel Logic -----------
DB_FIELDS = [
    {
        "key": "tele_open",
        "label": "Select tele_open:",
        "type": "carousel",
        "choices": [str(x) for x in range(-1000000000000, -1000000000000 + 5)] + ["Manual Input"], # change this to real list or allow manual input
    },
    {
        "key": "tele_closed",
        "label": "Select tele_closed:",
        "type": "carousel",
        "choices": [str(x) for x in range(-1000000, -1000000 + 5)] + ["Manual Input"],
    },
    {
        "key": "sub_1",
        "label": "Select sub_1 (price):",
        "type": "carousel",
        "choices": ["10", "25", "50", "100", "Manual Input"],
    },
    {
        "key": "sub_1_time",
        "label": "Select sub_1_time (days):",
        "type": "carousel",
        "choices": ["7", "14", "30", "60", "Manual Input"],
    },
    {
        "key": "sub_2",
        "label": "Select sub_2 (price):",
        "type": "carousel",
        "choices": ["50", "100", "200", "500", "Manual Input"],
    },
    {
        "key": "sub_2_time",
        "label": "Select sub_2_time (days):",
        "type": "carousel",
        "choices": ["7", "14", "30", "60", "Manual Input"],
    },
    {
        "key": "sub_3",
        "label": "Select sub_3 (price):",
        "type": "carousel",
        "choices": ["100", "200", "300", "500", "Manual Input"],
    },
    {
        "key": "sub_3_time",
        "label": "Select sub_3_time (days):",
        "type": "carousel",
        "choices": ["7", "14", "30", "60", "Manual Input"],
    },
]

def get_carousel_keyboard(field_idx, user_data):
    field = DB_FIELDS[field_idx]
    key = field["key"]
    selected = user_data.get(key, None)
    buttons = []
    for idx, val in enumerate(field["choices"]):
        if val == "Manual Input":
            buttons.append(
                InlineKeyboardButton("✍️ Manual Input", callback_data=f"manual_{key}_{field_idx}")
            )
        else:
            mark = "✅" if str(selected) == val else ""
            buttons.append(
                InlineKeyboardButton(f"{val} {mark}", callback_data=f"select_{key}_{field_idx}_{idx}")
            )
    nav = []
    if field_idx > 0:
        nav.append(InlineKeyboardButton("⬅️ Back", callback_data=f"nav_{field_idx - 1}"))
    if field_idx < len(DB_FIELDS) - 1:
        nav.append(InlineKeyboardButton("➡️ Next", callback_data=f"nav_{field_idx + 1}"))
    else:
        nav.append(InlineKeyboardButton("💾 Save", callback_data="save_db"))
    kb = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    if nav:
        kb.append(nav)
    kb.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_db")])
    return InlineKeyboardMarkup(kb)

async def start_database_carousel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    return await show_carousel_field(update, context, 0)

async def show_carousel_field(update, context, field_idx, edit=False):
    field = DB_FIELDS[field_idx]
    key = field["key"]
    label = field["label"]
    current_val = context.user_data.get(key, "None")
    text = f"{label}\nCurrent value: <b>{escape(str(current_val))}</b>"
    kb = get_carousel_keyboard(field_idx, context.user_data)
    if edit and update.callback_query:
        await update.callback_query.edit_message_text(text=text, reply_markup=kb, parse_mode="HTML")
        await update.callback_query.answer()
    else:
        await update.effective_chat.send_message(text=text, reply_markup=kb, parse_mode="HTML")
    return CAROUSEL

async def carousel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    # Navigation
    if data.startswith("nav_"):
        idx = int(data.split("_")[1])
        return await show_carousel_field(update, context, idx, edit=True)

    # Selection
    if data.startswith("select_"):
        _, key, field_idx, val_idx = data.split("_")
        field_idx = int(field_idx)
        value = DB_FIELDS[field_idx]["choices"][int(val_idx)]
        # validation
        if key.startswith("sub") and not _valid_sub(value):
            await query.answer("Invalid value, select another or Manual Input.")
            return CAROUSEL
        if key.endswith("time") and not _valid_time(value):
            await query.answer("Invalid value, select another or Manual Input.")
            return CAROUSEL
        context.user_data[key] = float(value) if key.startswith("sub") else int(value) if key.endswith("time") else value
        await show_carousel_field(update, context, field_idx, edit=True)
        return CAROUSEL

    # Manual Input
    if data.startswith("manual_"):
        _, key, field_idx = data.split("_")
        field_idx = int(field_idx)
        context.user_data["manual_entry"] = key
        await query.edit_message_text(f"Please enter value for <b>{DB_FIELDS[field_idx]['label']}</b>", parse_mode="HTML")
        await query.answer()
        context.user_data["manual_field_idx"] = field_idx
        return CAROUSEL

    # Save
    if data == "save_db":
        vals = (
            context.user_data.get("tele_open"),
            context.user_data.get("tele_closed"),
            context.user_data.get("sub_1"),
            context.user_data.get("sub_1_time"),
            context.user_data.get("sub_2"),
            context.user_data.get("sub_2_time"),
            context.user_data.get("sub_3"),
            context.user_data.get("sub_3_time"),
        )
        # Validate all fields
        for i, field in enumerate(DB_FIELDS):
            v = vals[i]
            if v is None:
                await query.answer(f"Missing: {field['key']}")
                await show_carousel_field(update, context, i, edit=True)
                return CAROUSEL
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
            await query.edit_message_text(
                "✅ Saved:\n"
                f"tele_open={vals[0]}, tele_closed={vals[1]},\n"
                f"sub_1={vals[2]} ({vals[3]}), sub_2={vals[4]} ({vals[5]}), sub_3={vals[6]} ({vals[7]})"
            )
        except Exception as e:
            await query.edit_message_text(f"❌ DB error: {e}")
        context.user_data.clear()
        await query.answer()
        return ConversationHandler.END

    # Cancel
    if data == "cancel_db":
        await query.edit_message_text("❌ Operation cancelled.")
        context.user_data.clear()
        await query.answer()
        return ConversationHandler.END

    await query.answer()
    return CAROUSEL

async def manual_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = context.user_data.get("manual_entry")
    field_idx = context.user_data.get("manual_field_idx", 0)
    value = update.message.text.strip()
    # Validate
    if key == "tele_open" or key == "tele_closed":
        if not _valid_channel_id(value):
            await update.message.reply_text("❌ Invalid channel id. Try again:")
            return CAROUSEL
        context.user_data[key] = value
    elif key.startswith("sub"):
        if not _valid_sub(value):
            await update.message.reply_text("❌ Invalid sub value. Try again:")
            return CAROUSEL
        context.user_data[key] = float(value)
    elif key.endswith("time"):
        if not _valid_time(value):
            await update.message.reply_text("❌ Invalid time. Try again:")
            return CAROUSEL
        context.user_data[key] = int(value)
    else:
        context.user_data[key] = value
    del context.user_data["manual_entry"]
    await show_carousel_field(update, context, field_idx, edit=False)
    return CAROUSEL

async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text("❌ Operation cancelled.")
    return ConversationHandler.END

# ---------- Main Menu & other handlers (unchanged) ----------
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
        await start_database_carousel(update, context)
    elif data == "CMD_GATEWAY":
        await start_np_gateway_new(update, context)
    else:
        await context.bot.send_message(chat_id, "Unknown command.")

# (Add your existing /start and /start_np_gateway_new handlers here as before!)

async def start_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global global_sub_value, global_open_channel_id
    chat_id = update.effective_chat.id
    user    = update.effective_user
    args    = context.args[0] if context.args else None

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
    # rest as before...

# --- Registration ---

async def run_telegram_bot():
    telegram_token = fetch_telegram_token()
    payment_provider_token = fetch_payment_provider_token()
    if not telegram_token:
        raise RuntimeError("Bot cannot start: TELEGRAM_BOT_SECRET_NAME is missing or invalid.")
    if not payment_provider_token:
        raise RuntimeError("Bot cannot start: PAYMENT_PROVIDER_SECRET_NAME is missing or invalid.")

    application = Application.builder().token(telegram_token).build()

    database_handler = ConversationHandler(
        entry_points=[CommandHandler("database", start_database_carousel)],
        states={
            CAROUSEL: [
                CallbackQueryHandler(carousel_callback),
                MessageHandler(filters.TEXT & ~filters.COMMAND, manual_input_handler),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
        per_chat=True,
    )
    application.add_handler(database_handler)
    application.add_handler(CommandHandler("start", start_bot))
    application.add_handler(CallbackQueryHandler(main_menu_callback))
    await application.run_polling(allowed_updates=Update.ALL_TYPES)

def run_flask_server():
    flask_app.run(host="0.0.0.0", port=5000)

if __name__ == "__main__":
    fetch_tele_open_list()
    from threading import Thread
    flask_thread = Thread(target=run_flask_server, daemon=True)
    flask_thread.start()
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(run_telegram_bot())
    except KeyboardInterrupt:
        print("\nShutting down gracefully. Goodbye!")
