# payment.py
import uuid
import aiohttp
from telegram import Update, LabeledPrice, ShippingOption
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, ConversationHandler, filters, ShippingQueryHandler, PreCheckoutQueryHandler

# Conversation states for /newpayment
NEWPAYMENT_AMOUNT, NEWPAYMENT_DESCRIPTION = range(2)

async def script3_start_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Use /shipping to receive an invoice with shipping included, or /noshipping for an invoice without shipping."
    )

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

newpayment_handler = ConversationHandler(
    entry_points=[CommandHandler("newpayment", start_newpayment)],
    states={
        NEWPAYMENT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_price_amount)],
        NEWPAYMENT_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_description_and_submit)],
    },
    fallbacks=[CommandHandler("cancel", script3_successful_payment_callback)],
)

payment_handlers = [
    CommandHandler("start_payment", script3_start_payment),
    CommandHandler("shipping", script3_start_with_shipping_callback),
    CommandHandler("noshipping", script3_start_without_shipping_callback),
    ShippingQueryHandler(script3_shipping_callback),
    PreCheckoutQueryHandler(script3_precheckout_callback),
    MessageHandler(filters.SUCCESSFUL_PAYMENT, script3_successful_payment_callback)
]
