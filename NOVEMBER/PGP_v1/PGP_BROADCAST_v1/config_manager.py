#!/usr/bin/env python3
"""
ConfigManager - Manages configuration from Secret Manager
Fetches and caches broadcast intervals and bot credentials
"""

import os
import logging
from typing import Optional
from google.cloud import secretmanager

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    Manages configuration from Google Cloud Secret Manager.

    Responsibilities:
    - Fetch configuration from Secret Manager
    - Cache values for performance
    - Provide type-safe access to config values
    - Handle fallback to default values on errors
    """

    def __init__(self):
        """Initialize the ConfigManager."""
        self.client = secretmanager.SecretManagerServiceClient()
        self.logger = logging.getLogger(__name__)
        self._cache = {}

    def _fetch_secret(self, secret_env_var: str, default: Optional[str] = None) -> Optional[str]:
        """
        Fetch a secret from Secret Manager.

        Args:
            secret_env_var: Environment variable containing secret path
            default: Default value if secret cannot be fetched

        Returns:
            Secret value as string, or default if error occurs
        """
        try:
            secret_path = os.getenv(secret_env_var)
            if not secret_path:
                if default is not None:
                    self.logger.warning(f"⚠️ Environment variable {secret_env_var} not set, using default")
                    return default
                raise ValueError(f"Environment variable {secret_env_var} not set and no default provided")

            # Check cache
            if secret_path in self._cache:
                self.logger.debug(f"📦 Using cached value for {secret_env_var}")
                return self._cache[secret_path]

            # Fetch from Secret Manager
            self.logger.info(f"🔐 Fetching secret: {secret_env_var}")
            response = self.client.access_secret_version(request={"name": secret_path})
            value = response.payload.data.decode("UTF-8").strip()  # Strip whitespace/newlines

            # Cache value
            self._cache[secret_path] = value
            self.logger.debug(f"✅ Secret fetched and cached: {secret_env_var}")

            return value

        except Exception as e:
            self.logger.error(f"❌ Error fetching secret {secret_env_var}: {e}")
            if default is not None:
                self.logger.warning(f"⚠️ Using default value for {secret_env_var}")
                return default
            raise

    def get_broadcast_auto_interval(self) -> float:
        """
        Get automated broadcast interval in hours.

        Returns:
            Interval in hours (default: 24.0)
        """
        try:
            value = self._fetch_secret('BROADCAST_AUTO_INTERVAL_SECRET', default='24')
            interval = float(value)
            self.logger.info(f"⏰ Automated broadcast interval: {interval} hours")
            return interval
        except (ValueError, TypeError) as e:
            self.logger.warning(f"⚠️ Invalid auto interval value, using default (24h): {e}")
            return 24.0

    def get_broadcast_manual_interval(self) -> float:
        """
        Get manual trigger rate limit interval in hours.

        Returns:
            Interval in hours (default: 0.0833 = 5 minutes)
        """
        try:
            value = self._fetch_secret('BROADCAST_MANUAL_INTERVAL_SECRET', default='0.0833')
            interval = float(value)
            self.logger.info(f"⏰ Manual trigger interval: {interval} hours ({interval * 60:.1f} minutes)")
            return interval
        except (ValueError, TypeError) as e:
            self.logger.warning(f"⚠️ Invalid manual interval value, using default (5min): {e}")
            return 0.0833  # 5 minutes

    def get_bot_token(self) -> str:
        """
        Get Telegram bot token.

        Returns:
            Bot token string

        Raises:
            ValueError: If token cannot be fetched
        """
        token = self._fetch_secret('BOT_TOKEN_SECRET')
        if not token:
            raise ValueError("Bot token is required but not found")
        self.logger.info(f"🤖 Bot token loaded (length: {len(token)})")
        return token

    def get_bot_username(self) -> str:
        """
        Get Telegram bot username.

        Returns:
            Bot username string

        Raises:
            ValueError: If username cannot be fetched
        """
        username = self._fetch_secret('BOT_USERNAME_SECRET')
        if not username:
            raise ValueError("Bot username is required but not found")
        self.logger.info(f"🤖 Bot username: @{username}")
        return username

    def get_jwt_secret_key(self) -> str:
        """
        Get JWT secret key for authentication.

        Returns:
            JWT secret key string

        Raises:
            ValueError: If secret key cannot be fetched
        """
        secret_key = self._fetch_secret('JWT_SECRET_KEY_SECRET')
        if not secret_key:
            raise ValueError("JWT secret key is required but not found")
        self.logger.info(f"🔑 JWT secret key loaded (length: {len(secret_key)})")
        return secret_key

    def get_database_host(self) -> str:
        """Get database host from Secret Manager."""
        return self._fetch_secret('DATABASE_HOST_SECRET')

    def get_database_name(self) -> str:
        """Get database name from Secret Manager."""
        return self._fetch_secret('DATABASE_NAME_SECRET')

    def get_database_user(self) -> str:
        """Get database user from Secret Manager."""
        return self._fetch_secret('DATABASE_USER_SECRET')

    def get_database_password(self) -> str:
        """Get database password from Secret Manager."""
        return self._fetch_secret('DATABASE_PASSWORD_SECRET')

    def get_cloud_sql_connection_name(self) -> str:
        """Get Cloud SQL instance connection name from Secret Manager."""
        return self._fetch_secret('CLOUD_SQL_CONNECTION_NAME_SECRET')

    def clear_cache(self):
        """Clear the configuration cache (useful for testing)."""
        self._cache.clear()
        self.logger.info("🗑️  Configuration cache cleared")


# Global instance for convenience
_config_manager_instance = None


def get_config_manager() -> ConfigManager:
    """
    Get or create a global ConfigManager instance.

    Returns:
        ConfigManager instance
    """
    global _config_manager_instance
    if _config_manager_instance is None:
        _config_manager_instance = ConfigManager()
    return _config_manager_instance
