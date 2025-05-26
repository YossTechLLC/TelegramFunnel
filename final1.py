#!/usr/bin/env python
import os
import logging
import json
import psycopg2
from google.cloud import secretmanager

from telegram import (
    Update,
    ForceReply,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    WebAppInfo,
    LabeledPrice,
    ShippingOption,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    ShippingQueryHandler,
    PreCheckoutQueryHandler,
    ConversationHandler,
)

# === PostgreSQL Connection Details ===
DB_HOST = '34.58.246.248'
DB_PORT = 5432
DB_NAME = 'client_table'
DB_USER = 'postgres'
DB_PASSWORD = 'Chigdabeast123$'

# Conversation states for /database
ID_INPUT, NAME_INPUT = range(2)

# ------------------------------------------------------------------------------
# Global Setup
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# ------------------------------------------------------------------------------
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
async def script1_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! (EchoBot) - here are the commands you are use right now /start /help /start_crypto /start_payment /shipping /noshipping /database",
        reply_markup=ForceReply(selective=True),
    )

async def script1_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Help! (EchoBot)")

async def script1_echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Prevent echoing during an active conversation
    if context.user_data.get("_conversation") == "database":
        return
    await update.message.reply_text(update.message.text)

# ------------------------------------------------------------------------------
# Script 2: WebApp
async def script2_start_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Please press the button below to choose a color via the WebApp.",
        reply_markup=ReplyKeyboardMarkup.from_button(
            KeyboardButton(
                text="Open the NowPayments Gateway!",
                web_app=WebAppInfo(url="https://nowpayments.io/payment/?iid=6200386335"),
            )
        ),
    )

async def script2_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = json.loads(update.effective_message.web_app_data.data)
    await update.message.reply_html(
        text=(
            f"You selected the color with the HEX value <code>{data['hex']}</code>. "
            f"The corresponding RGB value is <code>{tuple(data['rgb'].values())}</code>."
        ),
        reply_markup=ReplyKeyboardRemove(),
    )

# ------------------------------------------------------------------------------
# Script 3: Payments
async def script3_start_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "Use /shipping to receive an invoice with shipping included, or /noshipping "
        "for an invoice without shipping."
    )
    await update.message.reply_text(msg)

async def script3_start_with_shipping_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    await context.bot.send_invoice(
        chat_id,
        title="Payment Example",
        description="Example of a payment process using the python-telegram-bot library.",
        payload="Custom-Payload",
        provider_token=context.bot_data["PAYMENT_PROVIDER_TOKEN"],
        currency="USD",
        prices=[LabeledPrice("Test", 100)],
        need_name=True,
        need_phone_number=True,
        need_email=True,
        need_shipping_address=True,
        is_flexible=True,
    )

async def script3_start_without_shipping_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    await context.bot.send_invoice(
        chat_id,
        title="Payment Example",
        description="Example of a payment process using the python-telegram-bot library.",
        payload="Custom-Payload",
        provider_token=context.bot_data["PAYMENT_PROVIDER_TOKEN"],
        currency="USD",
        prices=[LabeledPrice("Test", 100)],
    )

async def script3_shipping_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.shipping_query
    if query.invoice_payload != "Custom-Payload":
        await query.answer(ok=False, error_message="Something went wrong...")
        return

    options = [ShippingOption("1", "Shipping Option A", [LabeledPrice("A", 100)])]
    price_list = [LabeledPrice("B1", 150), LabeledPrice("B2", 200)]
    options.append(ShippingOption("2", "Shipping Option B", price_list))
    await query.answer(ok=True, shipping_options=options)

async def script3_precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    if query.invoice_payload != "Custom-Payload":
        await query.answer(ok=False, error_message="Something went wrong...")
    else:
        await query.answer(ok=True)

async def script3_successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Thank you for your payment.")

# ------------------------------------------------------------------------------
# Script 4: /database Conversation
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
    user_id = context.user_data["id"]
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO users (id, name) VALUES (%s, %s)", (user_id, name))
        conn.commit()
        cur.close()
        conn.close()
        await update.message.reply_text(f"✅ Saved to database: ID={user_id}, Name={name}")
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
# ------------------------------------------------------------------------------
def main():
    telegram_token = fetch_telegram_token()
    payment_provider_token = fetch_payment_provider_token()

    if not telegram_token:
        raise RuntimeError("Bot cannot start: TELEGRAM_BOT_SECRET_NAME is missing or invalid.")
    if not payment_provider_token:
        raise RuntimeError("Bot cannot start: PAYMENT_PROVIDER_SECRET_NAME is missing or invalid.")

    application = Application.builder().token(telegram_token).build()
    application.bot_data["PAYMENT_PROVIDER_TOKEN"] = payment_provider_token

    # Database feature
    database_handler = ConversationHandler(
        entry_points=[CommandHandler("database", start_database)],
        states={
            ID_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_id)],
            NAME_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(database_handler)

    # Echo bot (last to avoid overriding input during conversation)
    application.add_handler(CommandHandler("start", script1_start))
    application.add_handler(CommandHandler("help", script1_help))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, script1_echo))

    # WebApp
    application.add_handler(CommandHandler("start_crypto", script2_start_crypto))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, script2_web_app_data))

    # Payments
    application.add_handler(CommandHandler("start_payment", script3_start_payment))
    application.add_handler(CommandHandler("shipping", script3_start_with_shipping_callback))
    application.add_handler(CommandHandler("noshipping", script3_start_without_shipping_callback))
    application.add_handler(ShippingQueryHandler(script3_shipping_callback))
    application.add_handler(PreCheckoutQueryHandler(script3_precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, script3_successful_payment_callback))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
