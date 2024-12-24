#!/usr/bin/env python
import logging
import json

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
)

# ------------------------------------------------------------------------------
# 0. Global Setup
# ------------------------------------------------------------------------------
TOKEN = "7840817495:AAFHnDBauWmAPGy_X1F4-JU0CaAv8C7a0VQ"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# Reduce chatter from httpx
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

PAYMENT_PROVIDER_TOKEN = "1877036958:TEST:ce5259b22362fee371e40b36a44941a30f6a668a"

# ------------------------------------------------------------------------------
# 1. Script 1 Functionality (Basic Echo Bot)
#    Original commands: /start, /help, echo all other text
#    To avoid collision with Script 2 and 3, we keep /start as is for the echo bot.
# ------------------------------------------------------------------------------
async def script1_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Script1's /start command: Greets user & sets up ForceReply."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! (EchoBot)",
        reply_markup=ForceReply(selective=True),
    )

async def script1_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Script1's /help command."""
    await update.message.reply_text("Help! (EchoBot)")

async def script1_echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Script1's echo handler for non-command text."""
    await update.message.reply_text(update.message.text)

# ------------------------------------------------------------------------------
# 2. Script 2 Functionality (Color Picker WebApp)
#    Renamed /start -> /start_color to avoid conflict
# ------------------------------------------------------------------------------
async def script2_start_color(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Script2's command to open the color picker WebApp.
    (Originally /start, now /start_color to avoid collision)
    """
    await update.message.reply_text(
        "Please press the button below to choose a color via the WebApp.",
        reply_markup=ReplyKeyboardMarkup.from_button(
            KeyboardButton(
                text="Open the color picker!",
                # You can change this URL to any valid WebApp
                web_app=WebAppInfo(url="https://nowpayments.io/payment?iid=6066212911"),
            )
        ),
    )

async def script2_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Script2's handler for incoming WebAppData.
    Shows the user the color they picked (HEX, RGB).
    """
    data = json.loads(update.effective_message.web_app_data.data)
    await update.message.reply_html(
        text=(
            f"You selected the color with the HEX value <code>{data['hex']}</code>. "
            f"The corresponding RGB value is <code>{tuple(data['rgb'].values())}</code>."
        ),
        reply_markup=ReplyKeyboardRemove(),
    )

# ------------------------------------------------------------------------------
# 3. Script 3 Functionality (Payments)
#    Original /start -> renamed to /start_payment
#    Additional commands: /shipping, /noshipping
# ------------------------------------------------------------------------------
async def script3_start_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Provides instructions on how to use the payment commands."""
    msg = (
        "Use /shipping to receive an invoice with shipping included, or /noshipping "
        "for an invoice without shipping."
    )
    await update.message.reply_text(msg)

async def script3_start_with_shipping_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends an invoice with shipping included (Triggers shipping query)."""
    chat_id = update.message.chat_id
    title = "Payment Example"
    description = "Example of a payment process using the python-telegram-bot library."
    payload = "Custom-Payload"
    currency = "USD"
    price = 1
    prices = [LabeledPrice("Test", price * 100)]

    await context.bot.send_invoice(
        chat_id,
        title,
        description,
        payload,
        PAYMENT_PROVIDER_TOKEN,
        currency,
        prices,
        need_name=True,
        need_phone_number=True,
        need_email=True,
        need_shipping_address=True,
        is_flexible=True,
    )

async def script3_start_without_shipping_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends an invoice without requiring shipping details."""
    chat_id = update.message.chat_id
    title = "Payment Example"
    description = "Example of a payment process using the python-telegram-bot library."
    payload = "Custom-Payload"
    currency = "USD"
    price = 1
    prices = [LabeledPrice("Test", price * 100)]

    await context.bot.send_invoice(
        chat_id, title, description, payload, PAYMENT_PROVIDER_TOKEN, currency, prices
    )

async def script3_shipping_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the ShippingQuery with available shipping options."""
    query = update.shipping_query
    if query.invoice_payload != "Custom-Payload":
        await query.answer(ok=False, error_message="Something went wrong...")
        return

    options = [ShippingOption("1", "Shipping Option A", [LabeledPrice("A", 100)])]
    price_list = [LabeledPrice("B1", 150), LabeledPrice("B2", 200)]
    options.append(ShippingOption("2", "Shipping Option B", price_list))
    await query.answer(ok=True, shipping_options=options)

async def script3_precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Respond to PreCheckoutQuery for final confirmation."""
    query = update.pre_checkout_query
    if query.invoice_payload != "Custom-Payload":
        await query.answer(ok=False, error_message="Something went wrong...")
    else:
        await query.answer(ok=True)

async def script3_successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Thank user for successful payment."""
    await update.message.reply_text("Thank you for your payment.")

# ------------------------------------------------------------------------------
# 4. Combined Main
# ------------------------------------------------------------------------------
def main() -> None:
    """Single entry point that merges all three scripts into one bot."""
    # Create one Application for everything
    application = Application.builder().token(TOKEN).build()

    # --- Script 1 handlers (Echo Bot) ---
    application.add_handler(CommandHandler("start", script1_start))
    application.add_handler(CommandHandler("help", script1_help))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, script1_echo)
    )

    # --- Script 2 handlers (Color Picker) ---
    # Re-labeled /start -> /start_color
    application.add_handler(CommandHandler("start_color", script2_start_color))
    application.add_handler(
        MessageHandler(filters.StatusUpdate.WEB_APP_DATA, script2_web_app_data)
    )

    # --- Script 3 handlers (Payments) ---
    # Re-labeled /start -> /start_payment
    application.add_handler(CommandHandler("start_payment", script3_start_payment))
    application.add_handler(CommandHandler("shipping", script3_start_with_shipping_callback))
    application.add_handler(CommandHandler("noshipping", script3_start_without_shipping_callback))
    application.add_handler(ShippingQueryHandler(script3_shipping_callback))
    application.add_handler(PreCheckoutQueryHandler(script3_precheckout_callback))
    application.add_handler(
        MessageHandler(filters.SUCCESSFUL_PAYMENT, script3_successful_payment_callback)
    )

    # Start the bot, combining everything
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()