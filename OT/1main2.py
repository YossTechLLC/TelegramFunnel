#!/usr/bin/env python
import psycopg2
import requests
import base64
import asyncio
from html import escape
from flask import Flask, request
from telegram.ext import Application, CommandHandler, ContextTypes
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

# ── config ──────────────────────────────────────────────────────────────────
DB_HOST = "34.58.246.248"
DB_PORT = 5432 
DB_NAME = "client_table"
DB_USER = "postgres"
DB_PASSWORD = "Chigdabeast123$"
BOT_TOKEN = "8139434770:AAGQNpGzbpeY1FgENcuJ_rctuXOAmRuPVJU"
BOT_USERNAME = "PayGatePrime_bot"

# Global Sub Value
global_sub_value = list[int] = []

# ── globals ─────────────────────────────────────────────────────────────────
tele_open_list: list[int] = []
tele_info_map: dict[int, dict[str, int | None]] = {}

# ── helper lambdas ──────────────────────────────────────────────────────────
encode_id = lambda i: base64.urlsafe_b64encode(str(i).encode()).decode()
decode_hash = lambda s: int(base64.urlsafe_b64decode(s.encode()).decode())

# ── db fetch ────────────────────────────────────────────────────────────────
def fetch_tele_open_list() -> None:
    tele_open_list.clear()
    tele_info_map.clear()
    try:
        with psycopg2.connect(
            host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
            user=DB_USER, password=DB_PASSWORD
        ) as conn, conn.cursor() as cur:
            cur.execute("SELECT tele_open, sub_1, sub_2, sub_3 FROM tele_channel")
            for tele_open, s1, s2, s3 in cur.fetchall():
                tele_open_list.append(tele_open)
                tele_info_map[tele_open] = {"sub_1": s1, "sub_2": s2, "sub_3": s3}
    except Exception as e:
        print("db error:", e)

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
        subs      = tele_info_map.get(chat_id, {})
        base_hash = encode_id(chat_id)

        lines = ["<b>decode links:</b>"]
        for key in ("sub_1", "sub_2", "sub_3"):
            val = subs.get(key)
            if val is None:
                continue
            token = f"{base_hash}_{val}"
            url   = f"https://t.me/{BOT_USERNAME}?start={token}"
            lines.append(
                f"• {escape(key)} <b>{val}</b> → <a href=\"{escape(url)}\">link</a>"
            )

        send_message(chat_id, "\n".join(lines))   # newline, no <br>


# ── flask endpoint (optional) ───────────────────────────────────────────────
@app.route("/decode_start")
def decode_start():
    token = request.args.get("start")
    user  = request.args.get("user_id", "unknown")
    if not token:
        return "missing start", 400
    try:
        h, _, sub = token.partition("_")
        cid = decode_hash(h)
        send_message(
            cid,
            f"🔓 decoded ID: <code>{cid}</code>\n"
            f"👤 user: <code>{escape(user)}</code>\n"
            f"📦 sub value: <code>{escape(sub or 'n/a')}</code>",
        )
        return "ok", 200
    except Exception as e:
        return f"err {e}", 500

####################################################### BUNLDE ###############

# Channel BOT ATTEMPT
async def post_welcome_message_to_channel(update: Update):
    bot = Bot(token=fetch_telegram_token())
    user_id = str(update.effective_user.id)
    chat = update.effective_chat
    chat_id = str(chat.id)
    chat_title = chat.title or "Private Chat"
    chat_type = chat.type

    if chat_type == "private":
        chat_title = "Private Chat (No Channel Context)"

    payload = f"{user_id}-{chat_id}"
    encoded_payload = quote(f"{user_id}-{chat_id}")

    text = (
        f"Hi OD Ricky! (EchoBot) - here are the commands you can use right now:\n"
        f"🪪 Chat Type: {chat_type}\n"
        f"🪪 The ID of {chat_title} is: {chat.id}\n"
        f"Your Telegram user ID: {user_id}"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Start", url=f"https://t.me/PayGatePrime_bot?start={encoded_payload}-start")],
        [InlineKeyboardButton("Gateway", url=f"https://t.me/PayGatePrime_bot?start={encoded_payload}-start_np_gateway_new")],
        [InlineKeyboardButton("Database", url=f"https://t.me/PayGatePrime_bot?start={encoded_payload}-database")],
    ])

    await bot.send_message(chat_id=chat.id, text=text, reply_markup=keyboard)

async def announce_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await post_welcome_message_to_channel(update)

# === PostgreSQL Connection Details ===
DB_HOST = '34.58.246.248'
DB_PORT = 5432
DB_NAME = 'client_table'
DB_USER = 'postgres'
DB_PASSWORD = 'Chigdabeast123$'

# Conversation states for /database
ID_INPUT, NAME_INPUT, AGE_INPUT = range(3)
# ------------------------------------------------------------------------------

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

# Script 1: Echo Bot
async def start_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args[0] if context.args else None

    if args and '-' in args:
        try:
            chat_part, channel_part, cmd = args.split('-', 2)
            await update.message.reply_text(f"🔍 Parsed user_id: {chat_part}, channel_id: {channel_part}")

            if cmd == "start_np_gateway_new":
                await start_np_gateway_new(update, context)
                return
            elif cmd == "database":
                await start_database(update, context)
                return
        except Exception as e:
            await update.message.reply_text(f"❌ could not parse command: {e}")

    await update.message.reply_html(
        rf"Hi {user.mention_html()}! (EchoBot) - here are the commands you are use right now /start /start_np_gateway /database /start_np_gateway_new /announce",
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
        cid  = decode_hash(hash_part)
        sub  = sub_part if sub_part else "n/a"
        try:
            global_sub_value = float(sub)
        except ValueError:
            global_sub_value = 0
        await update.message.reply_text(
            f"🔓 Decoded ID: <code>{cid}</code>\n"
            f"👤 User ID: <code>{update.effective_user.id}</code>\n"
            f"📦 sub value: <code>{escape(sub)}</code> - <code>{global_sub_value}</code>",
            parse_mode="HTML",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ decode error: {e}")
# ------------------------------------------------------------------------------

# Script 2: WebApp
async def start_np_gateway(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Please press the button below to choose a color via the WebApp.",
        reply_markup=ReplyKeyboardMarkup.from_button(
            KeyboardButton(
                text="Open the NowPayments Gateway!",
                web_app=WebAppInfo(url="https://nowpayments.io/payment/?iid=6200386335"),
            )
        ),
    )
# ------------------------------------------------------------------------------

# Script 3: /database Conversation
async def start_database(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["_conversation"] = "database"
    await update.message.reply_text("Please enter the ID (integer):")
    return ID_INPUT

async def receive_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = int(update.message.text)
        context.user_data["id"] = user_id
        await update.message.reply_text("Now enter the name:")
        return NAME_INPUT
    except ValueError:
        await update.message.reply_text("Invalid ID. Please enter a valid integer:")
        return ID_INPUT

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    context.user_data["name"] = name
    await update.message.reply_text("Now enter the age (integer):")
    return AGE_INPUT

async def receive_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        age = int(update.message.text)
        user_id = context.user_data["id"]
        name = context.user_data["name"]

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO test_table (id, name, age) VALUES (%s, %s, %s)", (user_id, name, age))
        conn.commit()
        cur.close()
        conn.close()

        await update.message.reply_text(f"✅ Saved to database: ID={user_id}, Name={name}, Age={age}")
    except ValueError:
        await update.message.reply_text("Invalid age. Please enter a valid integer:")
        return AGE_INPUT
    except Exception as e:
        await update.message.reply_text(f"❌ Error inserting into database: {e}")
    context.user_data.pop("_conversation", None)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("_conversation", None)
    await update.message.reply_text("❌ Operation cancelled.")
    return ConversationHandler.END
# ------------------------------------------------------------------------------

# NowPayment Static INFO
CALLBACK_URL = "https://us-central1-rikky-telebot1.cloudfunctions.net/simplecallback"

INVOICE_PAYLOAD = {
    "price_amount": float(global_sub_value),
    "price_currency": "USD",
    "order_id": "MP1TLZ8JAL9U-123456789",
    "order_description": "5-28-25",
    "ipn_callback_url": CALLBACK_URL,
    "success_url": CALLBACK_URL,
    "cancel_url": CALLBACK_URL
}

async def start_np_gateway_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
            "Please click on the 'Open Payment Gateway' button you see at the bottom of the screen to inniate the payment process - You have a 20 minute window within which you can submit the payment, if the payment isn't submitted withint that timeframe you will need to request the payment gateway again - thank you!",
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

    # Database feature
    database_handler = ConversationHandler(
        entry_points=[CommandHandler("database", start_database)],
        states={
            ID_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_id)],
            NAME_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            AGE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_age)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(database_handler)

    # Echo bot (last to avoid overriding input during conversation)
    application.add_handler(CommandHandler("start", start_bot))

    # WebApp
    application.add_handler(CommandHandler("start_np_gateway", start_np_gateway))
    application.add_handler(CommandHandler("start_np_gateway_new", start_np_gateway_new))
    application.add_handler(CommandHandler("announce", announce_command))
    application.run_polling(allowed_updates=Update.ALL_TYPES)
    return application
# ------------------------------------------------------------------------------

# START MAIN    
if __name__ == "__main__":
    fetch_tele_open_list()
    broadcast_hash_links()
    main()
    bot_app = make_bot()
    loop = asyncio.get_event_loop()
    loop.create_task(bot_app.run_polling())
    app.run(host="0.0.0.0", port=5000)
# ------------------------------------------------------------------------------
