#!/usr/bin/env python
"""
Configuration Manager for GCDonationHandler
Fetches configuration from Google Secret Manager

This module handles all Secret Manager operations for the donation handler service.
It is a self-contained module with no internal dependencies.
"""

import os
import logging
from typing import Optional, Dict, Any
from google.cloud import secretmanager

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    Manages configuration fetching from Google Secret Manager.

    This class provides centralized access to all secrets required by the
    donation handler service, including bot token, database credentials,
    and payment gateway configuration.

    Attributes:
        client: SecretManagerServiceClient instance for accessing secrets
    """

    def __init__(self):
        """Initialize the ConfigManager with Secret Manager client."""
        self.client = secretmanager.SecretManagerServiceClient()
        logger.info("🔧 ConfigManager initialized")

    def fetch_secret(self, secret_env_var: str) -> Optional[str]:
        """
        Fetch a secret value from Google Secret Manager.

        Args:
            secret_env_var: Environment variable name containing secret path
                          (e.g., "TELEGRAM_BOT_SECRET_NAME")

        Returns:
            Secret value as string, or None if fetching failed

        Example:
            >>> config = ConfigManager()
            >>> token = config.fetch_secret("TELEGRAM_BOT_SECRET_NAME")
            >>> print(f"Token: {token[:10]}...")
        """
        try:
            secret_path = os.getenv(secret_env_var)
            if not secret_path:
                logger.error(f"❌ Environment variable {secret_env_var} is not set")
                return None

            response = self.client.access_secret_version(request={"name": secret_path})
            secret_value = response.payload.data.decode("UTF-8")
            logger.info(f"✅ Successfully fetched secret: {secret_env_var}")
            return secret_value

        except Exception as e:
            logger.error(f"❌ Error fetching secret {secret_env_var}: {e}")
            return None

    def initialize_config(self) -> Dict[str, Any]:
        """
        Initialize and return all configuration values.

        Fetches all required secrets from Secret Manager and returns them
        in a dictionary. This method should be called once during service
        startup to load all configuration.

        Returns:
            Dictionary containing all configuration values:
            {
                'bot_token': str,
                'db_host': str,
                'db_port': int,
                'db_name': str,
                'db_user': str,
                'db_password': str,
                'payment_token': str,
                'ipn_callback_url': str
            }

        Raises:
            RuntimeError: If critical secrets cannot be fetched
        """
        logger.info("🔧 Initializing configuration from Secret Manager...")

        config = {}

        # Fetch Telegram bot token
        config['bot_token'] = self.fetch_secret("TELEGRAM_BOT_SECRET_NAME")

        # Fetch database credentials
        config['db_host'] = self.fetch_secret("DATABASE_HOST_SECRET")
        config['db_port'] = int(os.getenv("DATABASE_PORT", "5432"))  # Default to 5432
        config['db_name'] = self.fetch_secret("DATABASE_NAME_SECRET")
        config['db_user'] = self.fetch_secret("DATABASE_USER_SECRET")
        config['db_password'] = self.fetch_secret("DATABASE_PASSWORD_SECRET")

        # Fetch payment gateway configuration
        config['payment_token'] = self.fetch_secret("PAYMENT_PROVIDER_SECRET_NAME")
        config['ipn_callback_url'] = self.fetch_secret("NOWPAYMENTS_IPN_CALLBACK_URL")

        # Validate critical configuration
        critical_keys = ['bot_token', 'db_host', 'db_name', 'db_user', 'db_password', 'payment_token']
        missing_keys = [key for key in critical_keys if not config.get(key)]

        if missing_keys:
            error_msg = f"❌ Critical configuration missing: {', '.join(missing_keys)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        # IPN callback URL is optional (service will work without it, just won't capture payment_id)
        if not config.get('ipn_callback_url'):
            logger.warning("⚠️ IPN callback URL not configured - payment_id capture will not work")

        logger.info("✅ Configuration successfully loaded from Secret Manager")
        logger.info(f"🔧 Database: {config['db_user']}@{config['db_host']}:{config['db_port']}/{config['db_name']}")
        logger.info(f"🔧 Bot token: {'*' * 10}...{config['bot_token'][-4:]}")
        logger.info(f"🔧 Payment token: {'*' * 10}...{config['payment_token'][-4:]}")

        return config
