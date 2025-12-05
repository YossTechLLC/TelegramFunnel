#!/usr/bin/env python
"""
Configuration Manager for GCBotCommand
Fetches secrets from Google Secret Manager
"""
import os
from google.cloud import secretmanager
from typing import Optional, Dict

class ConfigManager:
    def __init__(self):
        self.bot_token = None
        self.bot_username = None
        self.gcpaymentgateway_url = None
        self.gcdonationhandler_url = None
        self.client = secretmanager.SecretManagerServiceClient()

    def _fetch_secret(self, env_var_name: str) -> Optional[str]:
        """Generic secret fetcher from Secret Manager"""
        try:
            secret_path = os.getenv(env_var_name)
            if not secret_path:
                raise ValueError(f"Environment variable {env_var_name} is not set.")
            response = self.client.access_secret_version(request={"name": secret_path})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            print(f"❌ Error fetching {env_var_name}: {e}")
            return None

    def fetch_telegram_token(self) -> Optional[str]:
        """Fetch Telegram bot token from Secret Manager"""
        return self._fetch_secret("TELEGRAM_BOT_SECRET_NAME")

    def fetch_bot_username(self) -> Optional[str]:
        """Fetch bot username from Secret Manager"""
        return self._fetch_secret("TELEGRAM_BOT_USERNAME")

    def fetch_gcpaymentgateway_url(self) -> str:
        """Fetch GCPaymentGateway URL from environment"""
        url = os.getenv("GCPAYMENTGATEWAY_URL")
        if not url:
            raise ValueError("GCPAYMENTGATEWAY_URL not set")
        return url

    def fetch_gcdonationhandler_url(self) -> str:
        """Fetch GCDonationHandler URL from environment"""
        url = os.getenv("GCDONATIONHANDLER_URL")
        if not url:
            raise ValueError("GCDONATIONHANDLER_URL not set")
        return url

    def initialize_config(self) -> Dict[str, str]:
        """Initialize and return all configuration values"""
        self.bot_token = self.fetch_telegram_token()
        self.bot_username = self.fetch_bot_username()
        self.gcpaymentgateway_url = self.fetch_gcpaymentgateway_url()
        self.gcdonationhandler_url = self.fetch_gcdonationhandler_url()

        if not self.bot_token:
            raise RuntimeError("Bot token is required to start GCBotCommand")

        print("✅ Configuration loaded successfully")
        print(f"  📱 Bot username: {self.bot_username}")
        print(f"  💳 Payment Gateway URL: {self.gcpaymentgateway_url}")
        print(f"  💝 Donation Handler URL: {self.gcdonationhandler_url}")

        return {
            'bot_token': self.bot_token,
            'bot_username': self.bot_username,
            'gcpaymentgateway_url': self.gcpaymentgateway_url,
            'gcdonationhandler_url': self.gcdonationhandler_url
        }

    def get_config(self) -> Dict[str, str]:
        """Get current configuration values"""
        return {
            'bot_token': self.bot_token,
            'bot_username': self.bot_username,
            'gcpaymentgateway_url': self.gcpaymentgateway_url,
            'gcdonationhandler_url': self.gcdonationhandler_url
        }
