#!/usr/bin/env python
import os
import logging
import json
import psycopg2
from google.cloud import secretmanager
import httpx

from telegram import (
    Update,
    ForceReply,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    WebAppInfo,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler,
)
# ------------------------------------------------------------------------------

# NowPayment Static INFO
NOWPAYMENTS_API_KEY = "WHY9KS4-DCZ45QZ-P6PZWA5-BV87D9J"
CALLBACK_URL = "https://us-central1-rikky-telebot1.cloudfunctions.net/simplecallback"

INVOICE_PAYLOAD = {
    "price_amount": 100.0,
    "price_currency": "USD",
    "order_id": "MP1TLZ8JAL9U-123456789",
    "order_description": "TEST123",
    "ipn_callback_url": CALLBACK_URL,
    "success_url": CALLBACK_URL,
    "cancel_url": CALLBACK_URL
}



async def start_np_gateway_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """creates invoice & shows ‘pay now’ web-app button."""
    headers = {"x-api-key": NOWPAYMENTS_API_KEY, "Content-Type": "application/json"}

    # call nowpayments
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(NOWPAYMENTS_API_KEY, headers=headers, json=INVOICE_PAYLOAD)

    if resp.status_code != 200:
        await update.message.reply_text(
            f"nowpayments error ❌\nstatus {resp.status_code}\n{resp.text}"
        )
        return

    invoice_url = resp.json().get("invoice_url")
    if not invoice_url:
        await update.message.reply_text("❌ invoice_url missing in response.")
        return

    # build a single-button reply keyboard that opens in-app
    pay_button = KeyboardButton(
        text="🔗 pay $100 via crypto",
        web_app=WebAppInfo(url=invoice_url),
    )
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[pay_button]],
        resize_keyboard=True,
        one_time_keyboard=True,   # hides keyboard after tap
    )

    await update.message.reply_text(
        "tap the button below to pay without leaving telegram.",
        reply_markup=keyboard,
    )

    logging.log.info("invoice %s sent to %s", invoice_url, update.effective_user.id)

# === PostgreSQL Connection Details ===
DB_HOST = '34.58.246.248'
DB_PORT = 5432
DB_NAME = 'client_table'
DB_USER = 'postgres'
DB_PASSWORD = 'Chigdabeast123$'

# Conversation states for /database
ID_INPUT, NAME_INPUT, AGE_INPUT = range(3)
# ------------------------------------------------------------------------------

# Global Setup
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
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
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! (EchoBot) - here are the commands you are use right now /start /start_np_gateway /database /start_np_gateway_new",
        reply_markup=ForceReply(selective=True),
    )
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

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
# ------------------------------------------------------------------------------
