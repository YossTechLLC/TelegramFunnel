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
import uuid
import aiohttp
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
ID_INPUT, NAME_INPUT, AGE_INPUT = range(3)

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
                web_app=WebAppInfo(url=dynamic_invoice_url),
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
# Script 4: /newpayment Conversation
NEWPAYMENT_AMOUNT, NEWPAYMENT_DESCRIPTION = range(2)

async def start_newpayment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Enter the price amount (e.g., 100.0):")
    return NEWPAYMENT_AMOUNT

async def receive_price_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price_amount = float(update.message.text)
        context.user_data["price_amount"] = price_amount
        await update.message.reply_text("Enter the order description:")
        return NEWPAYMENT_DESCRIPTION
    except ValueError:
        await update.message.reply_text("Invalid amount. Please enter a number (e.g., 100.0):")
        return NEWPAYMENT_AMOUNT

async def receive_description_and_submit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    description = update.message.text
    price_amount = context.user_data["price_amount"]
    order_id = f"MP1TLZ8JAL9U-{uuid.uuid4().hex[:9].upper()}"

    payload = {
        "price_amount": price_amount,
        "price_currency": "USD",
        "order_id": order_id,
        "order_description": description,
        "ipn_callback_url": "https://us-central1-rikky-telebot1.cloudfunctions.net/simplecallback",
        "success_url": "https://us-central1-rikky-telebot1.cloudfunctions.net/simplecallback",
        "cancel_url": "https://us-central1-rikky-telebot1.cloudfunctions.net/simplecallback"
    }

    headers = {
        "x-api-key": "WHY9KS4-DCZ45QZ-P6PZWA5-BV87D9J",
        "Content-Type": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post("https://api.nowpayments.io/v1/invoice", headers=headers, json=payload) as response:
            if response.status == 200:
                result = await response.json()
                invoice_url = result.get("invoice_url", "")
                context.user_data["invoice_url"] = invoice_url
                await update.message.reply_text(f"✅ Payment created! Invoice URL: {invoice_url}")
            else:
                error_text = await response.text()
                await update.message.reply_text(f"❌ Failed to create payment. Response: {error_text}")
    return ConversationHandler.END

# Script 5: /database Conversation
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
        cur.execute("INSERT INTO users (id, name, age) VALUES (%s, %s, %s)", (user_id, name, age))
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
# ------------------------------------------------------------------------------
dynamic_invoice_url = "https://nowpayments.io/payment/?iid=6200386335"

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
            AGE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_age)],
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

    newpayment_handler = ConversationHandler(
        entry_points=[CommandHandler("newpayment", start_newpayment)],
        states={
            NEWPAYMENT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_price_amount)],
            NEWPAYMENT_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_description_and_submit)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(newpayment_handler)

    # Update invoice url in color picker button
    async def update_invoice_url(application):
        await application.bot.initialize()
        async with aiohttp.ClientSession() as session:
            headers = {
                "x-api-key": "WHY9KS4-DCZ45QZ-P6PZWA5-BV87D9J",
                "Content-Type": "application/json"
            }
            payload = {
                "price_amount": 1.0,
                "price_currency": "USD",
                "order_id": "TEST1",
                "order_description": "INIT",
                "ipn_callback_url": "https://us-central1-rikky-telebot1.cloudfunctions.net/simplecallback",
                "success_url": "https://us-central1-rikky-telebot1.cloudfunctions.net/simplecallback",
                "cancel_url": "https://us-central1-rikky-telebot1.cloudfunctions.net/simplecallback"
            }
            async with session.post("https://api.nowpayments.io/v1/invoice", headers=headers, json=payload) as res:
                result = await res.json()
                updated_url = result.get("invoice_url", "https://nowpayments.io/payment")
                global dynamic_invoice_url
                dynamic_invoice_url = updated_url

    application.post_init(update_invoice_url)

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
