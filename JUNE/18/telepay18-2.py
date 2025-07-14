#!/usr/bin/env python
import requests
import asyncio
from flask import Flask, request
import nest_asyncio
import socket

import os
import logging
from google.cloud import secretmanager

# Import our custom modules
from database import DatabaseManager
from secure_webhook import SecureWebhookManager
from start_np_gateway import PaymentGatewayManager
from broadcast_manager import BroadcastManager
from input_handlers import InputHandlers
from menu_handlers import MenuHandlers
from bot_manager import BotManager

# Global Setup
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

nest_asyncio.apply()
flask_app = Flask(__name__)

# Initialize our managers
db_manager = DatabaseManager()
webhook_manager = SecureWebhookManager()
payment_manager = PaymentGatewayManager()
broadcast_manager = None  # Will be initialized after fetching BOT_TOKEN
input_handlers = InputHandlers(db_manager)

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

def fetch_closed_channel_id(open_channel_id):
    return db_manager.fetch_closed_channel_id(open_channel_id)

# Database connection moved to database.py module

BOT_TOKEN = fetch_telegram_token()
BOT_USERNAME = "PayGatePrime_bot"
NOW_WEBHOOK_KEY = fetch_now_webhook_key()

# Initialize broadcast manager after BOT_TOKEN is available
if BOT_TOKEN:
    broadcast_manager = BroadcastManager(BOT_TOKEN, BOT_USERNAME, db_manager)

# Initialize menu handlers and bot manager
menu_handlers = None
bot_manager = None

if BOT_TOKEN:
    # Create payment gateway wrapper function
    async def payment_gateway_wrapper(update, context):
        global_values = menu_handlers.get_global_values() if menu_handlers else {'sub_value': 5.0, 'open_channel_id': ''}
        await payment_manager.start_np_gateway_new(
            update, context, 
            global_values['sub_value'], 
            global_values['open_channel_id'],
            webhook_manager, 
            db_manager
        )
    
    menu_handlers = MenuHandlers(input_handlers, payment_gateway_wrapper)
    bot_manager = BotManager(input_handlers, menu_handlers.main_menu_callback, menu_handlers.start_bot, payment_gateway_wrapper)

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

async def run_telegram_bot():
    """Main bot runner function - now uses bot_manager"""
    if not bot_manager:
        raise RuntimeError("Bot manager not initialized. Check BOT_TOKEN and dependencies.")
    
    await bot_manager.run_telegram_bot(
        telegram_token=BOT_TOKEN,
        payment_token=payment_manager.payment_token
    )

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
    if broadcast_manager:
        broadcast_manager.fetch_tele_open_list()
        broadcast_manager.broadcast_hash_links()
    from threading import Thread
    flask_thread = Thread(target=run_flask_server, daemon=True)
    flask_thread.start()
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(run_telegram_bot())
    except KeyboardInterrupt:
        print("\nShutting down gracefully. Goodbye!")