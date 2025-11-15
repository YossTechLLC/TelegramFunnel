#!/usr/bin/env python
"""
🔐 Configuration Manager for PGP_WEBAPI_v1
Handles Secret Manager integration for all sensitive configuration
Inherits from BaseConfigManager for common functionality
"""
import os
from PGP_COMMON.config import BaseConfigManager


class ConfigManager(BaseConfigManager):
    """
    Manages configuration from Google Secret Manager.
    Inherits common secret fetching from BaseConfigManager.
    """

    def __init__(self):
        # Initialize base class
        super().__init__(service_name="PGP_WEBAPI_v1")

        # 🔐 SECURITY FIX: Use environment variable for project ID instead of hardcoding
        self.project_id = os.getenv("GCP_PROJECT_ID", "telepay-459221")
        if os.getenv("GCP_PROJECT_ID") is None:
            print("⚠️ GCP_PROJECT_ID not set, using default: telepay-459221")

    def access_secret(self, secret_name: str) -> str:
        """
        Access a secret from Google Secret Manager.

        Args:
            secret_name: Name of the secret (e.g., 'JWT_SECRET_KEY')

        Returns:
            The secret value as a string (whitespace stripped)
        """
        try:
            secret_path = f"projects/{self.project_id}/secrets/{secret_name}/versions/latest"
            response = self.client.access_secret_version(request={"name": secret_path})
            secret_value = response.payload.data.decode('UTF-8').strip()  # Strip whitespace/newlines
            print(f"✅ Secret '{secret_name}' loaded successfully")
            return secret_value
        except Exception as e:
            print(f"❌ Error accessing secret '{secret_name}': {e}")
            raise

    def get_config(self):
        """
        Load all configuration from Secret Manager.

        Returns:
            dict: Configuration dictionary
        """
        print("🔐 Loading configuration from Secret Manager...")

        config = {
            # JWT Configuration
            'jwt_secret_key': self.access_secret('JWT_SECRET_KEY'),

            # Email Verification & Password Reset Token Signing
            'signup_secret_key': self.access_secret('SIGNUP_SECRET_KEY'),

            # Database Configuration
            'cloud_sql_connection_name': self.access_secret('CLOUD_SQL_CONNECTION_NAME'),
            'database_name': self.access_secret('DATABASE_NAME_SECRET'),
            'database_user': self.access_secret('DATABASE_USER_SECRET'),
            'database_password': self.access_secret('DATABASE_PASSWORD_SECRET'),

            # CORS Configuration
            'cors_origin': self.access_secret('CORS_ORIGIN') if self._secret_exists('CORS_ORIGIN') else 'https://www.paygateprime.com',

            # Email Service Configuration
            'sendgrid_api_key': self.access_secret('SENDGRID_API_KEY'),
            'from_email': self.access_secret('FROM_EMAIL'),
            'from_name': self.access_secret('FROM_NAME'),
            # Frontend URL for email links (password reset, email verification, etc.)
            'base_url': self.access_secret('BASE_URL') if self._secret_exists('BASE_URL') else 'https://www.paygateprime.com',
        }

        print("✅ Configuration loaded successfully")
        return config

    def _secret_exists(self, secret_name: str) -> bool:
        """
        Check if a secret exists in Secret Manager.

        Args:
            secret_name: Name of the secret

        Returns:
            True if secret exists, False otherwise
        """
        try:
            secret_path = f"projects/{self.project_id}/secrets/{secret_name}"
            self.client.get_secret(request={"name": secret_path})
            return True
        except Exception:
            return False


# Global config manager instance
config_manager = ConfigManager()
