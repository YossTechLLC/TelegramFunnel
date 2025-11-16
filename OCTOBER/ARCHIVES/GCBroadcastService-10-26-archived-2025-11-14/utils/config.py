#!/usr/bin/env python3
"""
Configuration Management
Self-contained config module for GCBroadcastService
"""

import os
import logging
from typing import Optional, Dict, Any
from google.cloud import secretmanager

logger = logging.getLogger(__name__)


class Config:
    """
    Manages configuration from Google Cloud Secret Manager.

    Self-contained - no external dependencies on shared modules.
    """

    def __init__(self):
        """Initialize the Config manager."""
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
                return self._cache[secret_path]

            # Fetch from Secret Manager
            response = self.client.access_secret_version(request={"name": secret_path})
            value = response.payload.data.decode("UTF-8").strip()

            # Cache value
            self._cache[secret_path] = value
            return value

        except Exception as e:
            self.logger.error(f"❌ Error fetching secret {secret_env_var}: {e}")
            if default is not None:
                return default
            raise

    # Configuration getters
    def get_broadcast_auto_interval(self) -> float:
        """Get automated broadcast interval in hours (default: 24.0)"""
        try:
            value = self._fetch_secret('BROADCAST_AUTO_INTERVAL_SECRET', default='24')
            return float(value)
        except (ValueError, TypeError):
            return 24.0

    def get_broadcast_manual_interval(self) -> float:
        """Get manual trigger rate limit interval in hours (default: 0.0833 = 5 minutes)"""
        try:
            value = self._fetch_secret('BROADCAST_MANUAL_INTERVAL_SECRET', default='0.0833')
            return float(value)
        except (ValueError, TypeError):
            return 0.0833

    def get_bot_token(self) -> str:
        """Get Telegram bot token"""
        token = self._fetch_secret('BOT_TOKEN_SECRET')
        if not token:
            raise ValueError("Bot token is required but not found")
        return token

    def get_bot_username(self) -> str:
        """Get Telegram bot username"""
        username = self._fetch_secret('BOT_USERNAME_SECRET')
        if not username:
            raise ValueError("Bot username is required but not found")
        return username

    def get_jwt_secret_key(self) -> str:
        """Get JWT secret key for authentication"""
        secret_key = self._fetch_secret('JWT_SECRET_KEY_SECRET')
        if not secret_key:
            raise ValueError("JWT secret key is required but not found")
        return secret_key

    def get_database_host(self) -> str:
        """Get database host from Secret Manager"""
        return self._fetch_secret('DATABASE_HOST_SECRET')

    def get_database_name(self) -> str:
        """Get database name from Secret Manager"""
        return self._fetch_secret('DATABASE_NAME_SECRET')

    def get_database_user(self) -> str:
        """Get database user from Secret Manager"""
        return self._fetch_secret('DATABASE_USER_SECRET')

    def get_database_password(self) -> str:
        """Get database password from Secret Manager"""
        return self._fetch_secret('DATABASE_PASSWORD_SECRET')

    def get_cloud_sql_connection_name(self) -> str:
        """Get Cloud SQL instance connection name from Secret Manager"""
        return self._fetch_secret('CLOUD_SQL_CONNECTION_NAME_SECRET')

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert config to dictionary for Flask app.config.

        Returns:
            Dictionary with JWT_SECRET_KEY and JWT_ALGORITHM
        """
        return {
            'JWT_SECRET_KEY': self.get_jwt_secret_key(),
            'JWT_ALGORITHM': 'HS256',
            'JWT_DECODE_LEEWAY': 10  # 10 seconds leeway for clock skew
        }

    def clear_cache(self):
        """Clear the configuration cache (useful for testing)"""
        self._cache.clear()
