#!/usr/bin/env python
"""
🔐 Configuration Manager for GCRegisterAPI-10-26
Handles Secret Manager integration for all sensitive configuration
"""
import os
from google.cloud import secretmanager


class ConfigManager:
    """Manages configuration from Google Secret Manager"""

    def __init__(self):
        self.project_id = "telepay-459221"
        self.client = secretmanager.SecretManagerServiceClient()

    def access_secret(self, secret_name: str) -> str:
        """
        Access a secret from Google Secret Manager

        Args:
            secret_name: Name of the secret (e.g., 'JWT_SECRET_KEY')

        Returns:
            The secret value as a string
        """
        try:
            secret_path = f"projects/{self.project_id}/secrets/{secret_name}/versions/latest"
            response = self.client.access_secret_version(request={"name": secret_path})
            secret_value = response.payload.data.decode('UTF-8')
            print(f"✅ Secret '{secret_name}' loaded successfully")
            return secret_value
        except Exception as e:
            print(f"❌ Error accessing secret '{secret_name}': {e}")
            raise

    def get_config(self):
        """
        Load all configuration from Secret Manager

        Returns:
            dict: Configuration dictionary
        """
        print("🔐 Loading configuration from Secret Manager...")

        config = {
            # JWT Configuration
            'jwt_secret_key': self.access_secret('JWT_SECRET_KEY'),

            # Database Configuration
            'cloud_sql_connection_name': self.access_secret('CLOUD_SQL_CONNECTION_NAME'),
            'database_name': self.access_secret('DATABASE_NAME_SECRET'),
            'database_user': self.access_secret('DATABASE_USER_SECRET'),
            'database_password': self.access_secret('DATABASE_PASSWORD_SECRET'),

            # CORS Configuration
            'cors_origin': self.access_secret('CORS_ORIGIN') if self._secret_exists('CORS_ORIGIN') else 'https://www.paygateprime.com',
        }

        print("✅ Configuration loaded successfully")
        return config

    def _secret_exists(self, secret_name: str) -> bool:
        """Check if a secret exists in Secret Manager"""
        try:
            secret_path = f"projects/{self.project_id}/secrets/{secret_name}"
            self.client.get_secret(request={"name": secret_path})
            return True
        except Exception:
            return False


# Global config manager instance
config_manager = ConfigManager()
