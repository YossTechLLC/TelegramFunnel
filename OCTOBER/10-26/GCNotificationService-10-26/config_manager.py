#!/usr/bin/env python
"""
🔐 Configuration Manager for GCNotificationService
Fetches secrets from Google Secret Manager
"""
import os
from google.cloud import secretmanager
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages configuration and secrets for notification service"""

    def __init__(self):
        """Initialize configuration manager"""
        self.bot_token = None
        self.database_credentials = {}

    def fetch_secret(self, env_var_name: str, secret_name: str) -> Optional[str]:
        """
        Fetch a secret from Google Secret Manager

        Args:
            env_var_name: Name of environment variable containing secret path
            secret_name: Human-readable name for logging

        Returns:
            Secret value or None if error
        """
        try:
            client = secretmanager.SecretManagerServiceClient()
            secret_path = os.getenv(env_var_name)

            if not secret_path:
                logger.error(f"❌ [CONFIG] Environment variable {env_var_name} is not set")
                return None

            response = client.access_secret_version(request={"name": secret_path})
            secret_value = response.payload.data.decode("UTF-8").strip()

            logger.info(f"✅ [CONFIG] Successfully fetched {secret_name}")
            return secret_value

        except Exception as e:
            logger.error(f"❌ [CONFIG] Error fetching {secret_name}: {e}")
            return None

    def fetch_telegram_token(self) -> Optional[str]:
        """Fetch Telegram bot token from Secret Manager"""
        return self.fetch_secret(
            env_var_name="TELEGRAM_BOT_TOKEN_SECRET",
            secret_name="Telegram Bot Token"
        )

    def fetch_database_credentials(self) -> Dict[str, Optional[str]]:
        """
        Fetch all database credentials from Secret Manager (NEW_ARCHITECTURE pattern)

        Returns:
            Dictionary with keys: instance_connection_name, dbname, user, password
        """
        # Get Cloud SQL connection name from environment (required for Cloud SQL Connector)
        instance_connection_name = os.getenv("CLOUD_SQL_CONNECTION_NAME")

        if not instance_connection_name:
            logger.error("❌ [CONFIG] CLOUD_SQL_CONNECTION_NAME not set in environment")
        else:
            logger.info(f"✅ [CONFIG] Using Cloud SQL instance: {instance_connection_name}")

        return {
            'instance_connection_name': instance_connection_name,
            'dbname': self.fetch_secret(
                env_var_name="DATABASE_NAME_SECRET",
                secret_name="Database Name"
            ),
            'user': self.fetch_secret(
                env_var_name="DATABASE_USER_SECRET",
                secret_name="Database User"
            ),
            'password': self.fetch_secret(
                env_var_name="DATABASE_PASSWORD_SECRET",
                secret_name="Database Password"
            )
        }

    def initialize_config(self) -> Dict:
        """
        Initialize and return all configuration values

        Returns:
            Dictionary containing all config values
        """
        logger.info("🔐 [CONFIG] Initializing configuration...")

        # Fetch bot token
        self.bot_token = self.fetch_telegram_token()

        # Fetch database credentials
        self.database_credentials = self.fetch_database_credentials()

        # Validate critical config
        if not self.bot_token:
            logger.error("❌ [CONFIG] Bot token is missing")

        if not all([
            self.database_credentials['instance_connection_name'],
            self.database_credentials['dbname'],
            self.database_credentials['user'],
            self.database_credentials['password']
        ]):
            logger.error("❌ [CONFIG] Database credentials are incomplete")

        logger.info("✅ [CONFIG] Configuration initialized")

        return {
            'bot_token': self.bot_token,
            'database_credentials': self.database_credentials
        }
