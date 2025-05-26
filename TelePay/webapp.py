# webapp.py
import json
import aiohttp
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, WebAppInfo
from telegram.ext import ContextTypes

# Dynamic invoice URL placeholder
dynamic_invoice_url = "https://nowpayments.io/payment/?iid=6200386335"

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

async def update_invoice_url(application):
    global dynamic_invoice_url
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
            dynamic_invoice_url = result.get("invoice_url", dynamic_invoice_url)

webapp_handlers = []  # registered individually in main
