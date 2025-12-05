#!/usr/bin/env python
"""
Configuration Manager for GCSubscriptionMonitor
Fetches secrets from Google Secret Manager
"""
import os
from google.cloud import secretmanager
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages configuration and secret fetching"""

    def __init__(self):
        self.client = secretmanager.SecretManagerServiceClient()
        logger.info("🔧 ConfigManager initialized")

    def fetch_secret(self, env_var_name: str, secret_name_for_logging: str) -> Optional[str]:
        """
        Generic method to fetch a secret from Secret Manager.

        Args:
            env_var_name: Environment variable containing secret path
            secret_name_for_logging: Human-readable name for logging

        Returns:
            Secret value as string, or None if error
        """
        try:
            secret_path = os.getenv(env_var_name)
            if not secret_path:
                logger.error(f"❌ Environment variable {env_var_name} is not set")
                return None

            response = self.client.access_secret_version(request={"name": secret_path})
            secret_value = response.payload.data.decode("UTF-8").strip()

            logger.info(f"✅ Successfully fetched {secret_name_for_logging}")
            return secret_value

        except Exception as e:
            logger.error(f"❌ Error fetching {secret_name_for_logging}: {e}")
            return None

    def fetch_telegram_token(self) -> Optional[str]:
        """Fetch Telegram bot token from Secret Manager"""
        return self.fetch_secret(
            env_var_name="TELEGRAM_BOT_TOKEN_SECRET",
            secret_name_for_logging="Telegram bot token"
        )

    def fetch_database_host(self) -> Optional[str]:
        """Fetch database host (instance connection name) from Secret Manager"""
        return self.fetch_secret(
            env_var_name="DATABASE_HOST_SECRET",
            secret_name_for_logging="database host"
        )

    def fetch_database_name(self) -> Optional[str]:
        """Fetch database name from Secret Manager"""
        return self.fetch_secret(
            env_var_name="DATABASE_NAME_SECRET",
            secret_name_for_logging="database name"
        )

    def fetch_database_user(self) -> Optional[str]:
        """Fetch database user from Secret Manager"""
        return self.fetch_secret(
            env_var_name="DATABASE_USER_SECRET",
            secret_name_for_logging="database user"
        )

    def fetch_database_password(self) -> Optional[str]:
        """Fetch database password from Secret Manager"""
        return self.fetch_secret(
            env_var_name="DATABASE_PASSWORD_SECRET",
            secret_name_for_logging="database password"
        )

    def initialize_config(self) -> Dict[str, Optional[str]]:
        """
        Initialize and return all configuration values.

        Returns:
            Dictionary with all configuration values

        Raises:
            RuntimeError: If any critical configuration is missing
        """
        logger.info("🔧 Initializing configuration...")

        config = {
            'bot_token': self.fetch_telegram_token(),
            'instance_connection_name': self.fetch_database_host(),
            'db_name': self.fetch_database_name(),
            'db_user': self.fetch_database_user(),
            'db_password': self.fetch_database_password()
        }

        # Validate critical configuration
        missing = [k for k, v in config.items() if v is None]
        if missing:
            logger.error(f"❌ Missing critical configuration: {', '.join(missing)}")
            raise RuntimeError(f"Cannot initialize without: {', '.join(missing)}")

        logger.info("✅ Configuration initialized successfully")
        return config
