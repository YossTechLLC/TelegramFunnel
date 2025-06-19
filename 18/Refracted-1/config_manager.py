#!/usr/bin/env python
import os
from google.cloud import secretmanager
from typing import Optional

class ConfigManager:
    def __init__(self):
        self.bot_token = None
        self.webhook_key = None
        # Get bot username from environment variable with fallback
        self.bot_username = os.getenv("BOT_USERNAME", "PayGatePrime_bot")
    
    def fetch_telegram_token(self) -> Optional[str]:
        """Fetch the Telegram bot token from Google Secret Manager."""
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

    def fetch_now_webhook_key(self) -> Optional[str]:
        """Fetch the NowPayments webhook key from Google Secret Manager."""
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
    
    def initialize_config(self) -> dict:
        """Initialize and return all configuration values."""
        self.bot_token = self.fetch_telegram_token()
        self.webhook_key = self.fetch_now_webhook_key()
        
        return {
            'bot_token': self.bot_token,
            'webhook_key': self.webhook_key,
            'bot_username': self.bot_username
        }
    
    def get_config(self) -> dict:
        """Get current configuration values."""
        return {
            'bot_token': self.bot_token,
            'webhook_key': self.webhook_key,
            'bot_username': self.bot_username
        }