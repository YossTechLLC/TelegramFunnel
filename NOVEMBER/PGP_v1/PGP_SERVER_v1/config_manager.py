#!/usr/bin/env python
import os
from typing import Optional
from PGP_COMMON.config import BaseConfigManager

#LIST OF ENVIRONMENT VARIABLES
# TELEGRAM_BOT_SECRET_NAME: Path to Telegram bot token in Secret Manager
# NOWPAYMENT_WEBHOOK_KEY: Path to NowPayments webhook key in Secret Manager
# TELEGRAM_BOT_USERNAME: Path to Telegram bot username in Secret Manager
# TELEGRAM_BOT_WEBHOOK_URL: URL for the Telegram bot webhook endpoint
# DATABASE_HOST_SECRET: Path to database host in Secret Manager
# DATABASE_NAME_SECRET: Path to database name in Secret Manager
# DATABASE_USER_SECRET: Path to database user in Secret Manager
# DATABASE_PASSWORD_SECRET: Path to database password in Secret Manager
# CLOUD_SQL_CONNECTION_NAME: Cloud SQL instance connection name (or path to secret)


class ConfigManager(BaseConfigManager):
    """
    Manages configuration and secrets for PGP_SERVER_v1.
    Inherits SecretManager client from BaseConfigManager.
    """

    def __init__(self):
        """Initialize configuration manager with base SecretManager client."""
        super().__init__(service_name="PGP_SERVER_v1")
        self.bot_token = None
        self.webhook_key = None
        # Get bot username from environment variable
        self.bot_username = self.fetch_bot_username()

    def fetch_telegram_token(self) -> Optional[str]:
        """Fetch the Telegram bot token from Secret Manager."""
        try:
            secret_path = os.getenv("TELEGRAM_BOT_SECRET_NAME")
            if not secret_path:
                raise ValueError("Environment variable TELEGRAM_BOT_SECRET_NAME is not set.")
            # Use base class SecretManager client
            response = self.client.access_secret_version(request={"name": secret_path})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            print(f"❌ Error fetching the Telegram bot TOKEN: {e}")
            return None

    def fetch_now_webhook_key(self) -> Optional[str]:
        """Fetch the NowPayments webhook key from Secret Manager."""
        try:
            secret_path = os.getenv("NOWPAYMENT_WEBHOOK_KEY")
            if not secret_path:
                raise ValueError("Environment variable NOWPAYMENT_WEBHOOK_KEY is not set.")
            # Use base class SecretManager client
            response = self.client.access_secret_version(request={"name": secret_path})
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
            secret_path = os.getenv("TELEGRAM_BOT_USERNAME")
            if not secret_path:
                raise ValueError("Environment variable TELEGRAM_BOT_USERNAME is not set.")
            # Use base class SecretManager client
            response = self.client.access_secret_version(request={"name": secret_path})
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

    # 🆕 Database credential methods (used by database.py)
    def fetch_database_host(self) -> str:
        """Fetch database host from Secret Manager."""
        try:
            secret_path = os.getenv("DATABASE_HOST_SECRET")
            if not secret_path:
                raise ValueError("Environment variable DATABASE_HOST_SECRET is not set.")
            response = self.client.access_secret_version(request={"name": secret_path})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            print(f"❌ Error fetching DATABASE_HOST_SECRET: {e}")
            raise

    def fetch_database_name(self) -> str:
        """Fetch database name from Secret Manager."""
        try:
            secret_path = os.getenv("DATABASE_NAME_SECRET")
            if not secret_path:
                raise ValueError("Environment variable DATABASE_NAME_SECRET is not set.")
            response = self.client.access_secret_version(request={"name": secret_path})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            print(f"❌ Error fetching DATABASE_NAME_SECRET: {e}")
            raise

    def fetch_database_user(self) -> str:
        """Fetch database user from Secret Manager."""
        try:
            secret_path = os.getenv("DATABASE_USER_SECRET")
            if not secret_path:
                raise ValueError("Environment variable DATABASE_USER_SECRET is not set.")
            response = self.client.access_secret_version(request={"name": secret_path})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            print(f"❌ Error fetching DATABASE_USER_SECRET: {e}")
            raise

    def fetch_database_password(self) -> str:
        """
        Fetch database password from Secret Manager.

        🔐 SECURITY: Fails hard if password cannot be fetched (no fallback).
        """
        try:
            secret_path = os.getenv("DATABASE_PASSWORD_SECRET")
            if not secret_path:
                raise ValueError("Environment variable DATABASE_PASSWORD_SECRET is not set.")
            response = self.client.access_secret_version(request={"name": secret_path})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            print(f"❌ Error fetching DATABASE_PASSWORD_SECRET: {e}")
            raise

    def fetch_cloud_sql_connection_name(self) -> str:
        """
        Fetch Cloud SQL connection name from Secret Manager.

        Supports two modes:
        1. Direct format: "project:region:instance" in environment variable
        2. Secret Manager: Fetch from Secret Manager path

        🔐 SECURITY: Fails hard on errors, but allows backward-compatible default with loud warnings.
        """
        try:
            secret_path = os.getenv("CLOUD_SQL_CONNECTION_NAME")
            if not secret_path:
                # Backward compatibility with loud warnings
                print("⚠️ WARNING: CLOUD_SQL_CONNECTION_NAME not set, using default: telepay-459221:us-central1:telepaypsql")
                print("⚠️ WARNING: This is deprecated. Please set CLOUD_SQL_CONNECTION_NAME environment variable.")
                return "telepay-459221:us-central1:telepaypsql"

            # Check if it's already in correct format (PROJECT:REGION:INSTANCE)
            if ':' in secret_path and not secret_path.startswith('projects/'):
                print(f"✅ CLOUD_SQL_CONNECTION_NAME already in correct format: {secret_path}")
                return secret_path

            # Otherwise, fetch from Secret Manager
            response = self.client.access_secret_version(request={"name": secret_path})
            connection_name = response.payload.data.decode("UTF-8").strip()
            print(f"✅ Fetched Cloud SQL connection name from Secret Manager: {connection_name}")
            return connection_name
        except Exception as e:
            print(f"❌ Error fetching CLOUD_SQL_CONNECTION_NAME: {e}")
            raise RuntimeError(f"Failed to fetch Cloud SQL connection name: {e}")
