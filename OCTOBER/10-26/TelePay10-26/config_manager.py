#!/usr/bin/env python
import os
from google.cloud import secretmanager
from typing import Optional

#LIST OF ENVIRONMENT VARIABLES
# TELEGRAM_BOT_SECRET_NAME: Path to Telegram bot token in Secret Manager
# NOWPAYMENT_WEBHOOK_KEY: Path to NowPayments webhook key in Secret Manager 
# TELEGRAM_BOT_USERNAME: Path to Telegram bot username in Secret Manager
# TELEGRAM_BOT_WEBHOOK_URL: URL for the Telegram bot webhook endpoint


class ConfigManager:
    def __init__(self):
        self.bot_token = None
        self.webhook_key = None
        # Get bot username from environment variable
        self.bot_username = self.fetch_bot_username()
    
    def fetch_telegram_token(self) -> Optional[str]:
        """Fetch the Telegram bot token from Secret Manager."""
        try:
            client = secretmanager.SecretManagerServiceClient()
            secret_path = os.getenv("TELEGRAM_BOT_SECRET_NAME")
            if not secret_path:
                raise ValueError("Environment variable TELEGRAM_BOT_SECRET_NAME is not set.")
            response = client.access_secret_version(request={"name": secret_path})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            print(f"❌ Error fetching the Telegram bot TOKEN: {e}")
            return None

    def fetch_now_webhook_key(self) -> Optional[str]:
        """Fetch the NowPayments webhook key from Secret Manager."""
        try:
            client = secretmanager.SecretManagerServiceClient()
            secret_path = os.getenv("NOWPAYMENT_WEBHOOK_KEY")
            if not secret_path:
                raise ValueError("Environment variable NOWPAYMENT_WEBHOOK_KEY is not set.")
            response = client.access_secret_version(request={"name": secret_path})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            print(f"❌ Error fetching the NOWPAYMENT_WEBHOOK_KEY: {e}")
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
    
    def fetch_bot_username(self) -> Optional[str]:
        """Fetch the bot username from Secret Manager."""
        try:
            client = secretmanager.SecretManagerServiceClient()
            secret_path = os.getenv("TELEGRAM_BOT_USERNAME")
            if not secret_path:
                raise ValueError("Environment variable TELEGRAM_BOT_USERNAME is not set.")
            response = client.access_secret_version(request={"name": secret_path})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            print(f"❌ Error fetching the TELEGRAM_BOT_USERNAME: {e}")
            return None
    
    def get_config(self) -> dict:
        """Get current configuration values."""
        return {
            'bot_token': self.bot_token,
            'webhook_key': self.webhook_key,
            'bot_username': self.bot_username
        }