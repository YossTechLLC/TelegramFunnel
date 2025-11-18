#!/usr/bin/env python
"""
🔐 Configuration Manager for PGP_NOTIFICATIONS_v1
Fetches secrets from Google Secret Manager
Inherits from BaseConfigManager for common functionality
"""
import os
from typing import Optional, Dict
import logging
from PGP_COMMON.config import BaseConfigManager

logger = logging.getLogger(__name__)


class ConfigManager(BaseConfigManager):
    """
    Manages configuration and secrets for notification service.
    Inherits common secret fetching from BaseConfigManager.
    """

    def __init__(self):
        """Initialize configuration manager"""
        super().__init__(service_name="PGP_NOTIFICATIONS_v1")
        self.bot_token = None
        self.database_credentials = {}

    # ========== HOT-RELOADABLE SECRET GETTERS ==========

    def get_telegram_token(self) -> Optional[str]:
        """
        Get Telegram bot token (HOT-RELOADABLE).

        Returns:
            Telegram bot token or None if not available
        """
        secret_path = self.build_secret_path("TELEGRAM_BOT_API_TOKEN")
        return self.fetch_secret_dynamic(
            secret_path,
            "Telegram bot token",
            cache_key="telegram_bot_token"
        )

    def fetch_database_credentials(self) -> Dict[str, Optional[str]]:
        """
        Fetch all database credentials from Secret Manager (NEW_ARCHITECTURE pattern).

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
        Initialize and return all configuration values.

        Returns:
            Dictionary containing all config values
        """
        logger.info("🔐 [CONFIG] Initializing configuration...")

        # Fetch database credentials (STATIC - loaded at startup)
        self.database_credentials = self.fetch_database_credentials()

        # Validate critical config
        if not all([
            self.database_credentials['instance_connection_name'],
            self.database_credentials['dbname'],
            self.database_credentials['user'],
            self.database_credentials['password']
        ]):
            logger.error("❌ [CONFIG] Database credentials are incomplete")

        logger.info("✅ [CONFIG] Configuration initialized")
        logger.info("   Hot-reloadable secrets: TELEGRAM_BOT_API_TOKEN")

        return {
            'database_credentials': self.database_credentials
            # Note: bot_token is NOT fetched here - use get_telegram_token() for hot-reload
        }
