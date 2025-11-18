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
        self.project_id = os.getenv("GCP_PROJECT_ID", "pgp-live")
        if os.getenv("GCP_PROJECT_ID") is None:
            print("⚠️ GCP_PROJECT_ID not set, using default: pgp-live")

    # ========== HOT-RELOADABLE SECRET GETTERS ==========

    def get_jwt_secret_key(self) -> str:
        """Get JWT secret key (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("JWT_SECRET_KEY")
        return self.fetch_secret_dynamic(
            secret_path,
            "JWT secret key",
            cache_key="jwt_secret_key"
        )

    def get_signup_secret_key(self) -> str:
        """Get signup secret key for email verification (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("SIGNUP_SECRET_KEY")
        return self.fetch_secret_dynamic(
            secret_path,
            "Signup secret key",
            cache_key="signup_secret_key"
        )

    def get_sendgrid_api_key(self) -> str:
        """Get SendGrid API key (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("SENDGRID_API_KEY")
        return self.fetch_secret_dynamic(
            secret_path,
            "SendGrid API key",
            cache_key="sendgrid_api_key"
        )

    def get_from_email(self) -> str:
        """Get from email address (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("FROM_EMAIL")
        return self.fetch_secret_dynamic(
            secret_path,
            "From email",
            cache_key="from_email"
        )

    def get_from_name(self) -> str:
        """Get from name (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("FROM_NAME")
        return self.fetch_secret_dynamic(
            secret_path,
            "From name",
            cache_key="from_name"
        )

    def get_cors_origin(self) -> str:
        """Get CORS origin (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("CORS_ORIGIN")
        return self.fetch_secret_dynamic(
            secret_path,
            "CORS origin",
            cache_key="cors_origin"
        ) or "https://www.paygateprime.com"

    def get_base_url(self) -> str:
        """Get base URL for email links (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("BASE_URL")
        return self.fetch_secret_dynamic(
            secret_path,
            "Base URL",
            cache_key="base_url"
        ) or "https://www.paygateprime.com"

    def get_cloud_sql_connection_name(self) -> str:
        """Get Cloud SQL connection name (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("CLOUD_SQL_CONNECTION_NAME")
        return self.fetch_secret_dynamic(
            secret_path,
            "Cloud SQL connection name",
            cache_key="cloud_sql_connection_name"
        )

    def get_database_name(self) -> str:
        """Get database name (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("DATABASE_NAME_SECRET")
        return self.fetch_secret_dynamic(
            secret_path,
            "Database name",
            cache_key="database_name"
        )

    def get_database_user(self) -> str:
        """Get database user (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("DATABASE_USER_SECRET")
        return self.fetch_secret_dynamic(
            secret_path,
            "Database user",
            cache_key="database_user"
        )

    # ========== DEPRECATED METHODS (kept for backward compatibility) ==========

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
