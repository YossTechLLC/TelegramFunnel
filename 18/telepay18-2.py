#!/usr/bin/env python
import requests
import base64
import asyncio
from html import escape
from flask import Flask, request
import nest_asyncio
import socket

import os
import logging
from google.cloud import secretmanager

# Import our custom modules
from database import DatabaseManager, _valid_channel_id, _valid_sub, _valid_time, receive_sub3_time_db
from secure_webhook import SecureWebhookManager
from start_np_gateway import PaymentGatewayManager

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

# Global Setup
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

nest_asyncio.apply()
flask_app = Flask(__name__)

# Global Sub Value and Channel IDs
global_sub_value = 5.0
global_open_channel_id = ""  # Always str for varchar compatibility
global_closed_channel_id = ""

# Global Data
tele_open_list: list[str] = []
tele_closed_list: list[str] = []
tele_info_open_map: dict[str, dict[str, int | None]] = {}

# Initialize our managers
db_manager = DatabaseManager()
webhook_manager = SecureWebhookManager()
payment_manager = PaymentGatewayManager()

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

encode_id = lambda i: base64.urlsafe_b64encode(str(i).encode()).decode()
decode_hash = lambda s: base64.urlsafe_b64decode(s.encode()).decode()  # returns string

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

def fetch_tele_open_list() -> None:
    global tele_open_list, tele_info_open_map
    tele_open_list.clear()
    tele_info_open_map.clear()
    
    new_list, new_map = db_manager.fetch_tele_open_list()
    tele_open_list.extend(new_list)
    tele_info_open_map.update(new_map)

def fetch_closed_channel_id(open_channel_id):
    return db_manager.fetch_closed_channel_id(open_channel_id)

# Database connection moved to database.py module

BOT_TOKEN = fetch_telegram_token()
BOT_USERNAME = "PayGatePrime_bot"
NOW_WEBHOOK_KEY = fetch_now_webhook_key()

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

def build_menu_buttons(buttons_config):
    buttons = []
    for b in buttons_config:
        if "callback_data" in b:
            buttons.append(InlineKeyboardButton(text=b["text"], callback_data=b["callback_data"]))
        elif "url" in b:
            buttons.append(InlineKeyboardButton(text=b["text"], url=b["url"]))
    return InlineKeyboardMarkup([buttons])

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

def get_telegram_user_id(update):
    if hasattr(update, "effective_user") and update.effective_user:
        return update.effective_user.id
    if hasattr(update, "callback_query") and update.callback_query and update.callback_query.from_user:
        return update.callback_query.from_user.id
    return None

def safe_int64(val):
    try:
        val = int(val)
        if val < 0:
            val = 2**64 + val
        if val > 2**64 - 1:
            val = 2**64 - 1
    except Exception:
        val = 0
    return val

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat.id
    if data == "CMD_START":
        await context.bot.send_message(chat_id, "You clicked Start!")
    elif data == "CMD_DATABASE":
        # DO NOT edit the message! Just send prompt for input.
        await context.bot.send_message(
            chat_id,
            "Enter *tele_open* (≤14 chars integer):",
            parse_mode="Markdown"
        )
        return TELE_OPEN_INPUT
    elif data == "CMD_GATEWAY":
        await start_np_gateway_new(update, context)
    else:
        await context.bot.send_message(chat_id, "Unknown command.")

async def start_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global global_sub_value, global_open_channel_id
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
        open_channel_id = decode_hash(hash_part)
        global_open_channel_id = open_channel_id  # always a string!
        sub_raw = sub_part.replace("d", ".") if sub_part else "n/a"
        try:
            local_sub_value = float(sub_raw)
        except ValueError:
            local_sub_value = 15.0
        global_sub_value = local_sub_value
    except Exception as e:
        await context.bot.send_message(chat_id, f"❌ decode error: {e}")

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

async def start_database(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text("Enter *tele_open* (≤14 chars integer):", parse_mode="Markdown")
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
    return await receive_sub3_time_db(update, ctx, db_manager)

async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text("❌ Operation cancelled.")
    return ConversationHandler.END

# build_signed_success_url moved to secure_webhook.py

async def start_np_gateway_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global global_sub_value, global_open_channel_id
    user_id = payment_manager.get_telegram_user_id(update)
    if not user_id:
        chat_id = update.effective_chat.id if hasattr(update, "effective_chat") else None
        if chat_id:
            await context.bot.send_message(chat_id, "❌ Could not determine user ID.")
        return

    closed_channel_id = fetch_closed_channel_id(global_open_channel_id)
    if not closed_channel_id:
        chat_id = update.effective_chat.id if hasattr(update, "effective_chat") else update.callback_query.message.chat.id
        await context.bot.send_message(chat_id, "❌ Could not find a closed_channel_id for this open_channel_id. Please check your database!")
        return

    if not webhook_manager.signing_key:
        chat_id = update.effective_chat.id if hasattr(update, "effective_chat") else None
        if chat_id:
            await context.bot.send_message(chat_id, "❌ Signing key missing, cannot generate secure URL.")
        return

    secure_success_url = webhook_manager.build_signed_success_url(
        tele_open_id=user_id,
        closed_channel_id=closed_channel_id,
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
        "x-api-key": payment_manager.payment_token,
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
            "Please click ‘Open Payment Gateway’ below. "
            "You have 20 minutes to complete the payment."
        )
        await bot.send_message(chat_id, text, reply_markup=reply_markup)
    else:
        await bot.send_message(
            chat_id,
            f"nowpayments error ❌ — status {resp.status_code}\n{resp.text}",
        )

async def run_telegram_bot():
    telegram_token = fetch_telegram_token()
    if not telegram_token:
        raise RuntimeError("Bot cannot start: TELEGRAM_BOT_SECRET_NAME is missing or invalid.")
    if not payment_manager.payment_token:
        raise RuntimeError("Bot cannot start: PAYMENT_PROVIDER_SECRET_NAME is missing or invalid.")

    application = Application.builder().token(telegram_token).build()

    # Accept both /database and CMD_DATABASE button to start conversation
    database_handler = ConversationHandler(
        entry_points=[
            CommandHandler("database", start_database),
            CallbackQueryHandler(main_menu_callback, pattern="^CMD_DATABASE$"),
        ],
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
        per_message=False,  # This is default, warning can be ignored or silenced
    )
    application.add_handler(database_handler)
    application.add_handler(CommandHandler("start", start_bot))
    application.add_handler(CommandHandler("start_np_gateway_new", start_np_gateway_new))
    application.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^(?!CMD_DATABASE).*$"))
    await application.run_polling(allowed_updates=Update.ALL_TYPES)

def find_free_port(start_port=5000, max_tries=20):
    for port in range(start_port, start_port + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', port)) != 0:
                return port
    raise OSError("No available port found for Flask.")

def run_flask_server():
    port = find_free_port(5000)
    print(f"Running Flask on port {port}")
    flask_app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    fetch_tele_open_list()
    broadcast_hash_links()
    from threading import Thread
    flask_thread = Thread(target=run_flask_server, daemon=True)
    flask_thread.start()
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(run_telegram_bot())
    except KeyboardInterrupt:
        print("\nShutting down gracefully. Goodbye!")
