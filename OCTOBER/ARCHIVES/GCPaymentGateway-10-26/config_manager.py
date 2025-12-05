#!/usr/bin/env python
"""
Configuration Manager for GCPaymentGateway-10-26
Handles fetching secrets from Google Secret Manager
"""

import os
from google.cloud import secretmanager
from typing import Optional, Dict, Any


class ConfigManager:
    """
    Manages configuration and secrets for the payment gateway service.
    All secrets are fetched from Google Secret Manager.
    """

    def __init__(self):
        """Initialize the ConfigManager."""
        self.client = secretmanager.SecretManagerServiceClient()
        self.config = {}

    def fetch_secret(self, env_var_name: str, secret_description: str) -> Optional[str]:
        """
        Generic method to fetch a secret from Secret Manager.

        Args:
            env_var_name: Environment variable containing secret path
            secret_description: Human-readable description for logging

        Returns:
            Secret value as string, or None if not found
        """
        try:
            secret_path = os.getenv(env_var_name)
            if not secret_path:
                print(f"⚠️ [CONFIG] Environment variable {env_var_name} is not set")
                return None

            response = self.client.access_secret_version(request={"name": secret_path})
            secret_value = response.payload.data.decode("UTF-8")
            print(f"✅ [CONFIG] Successfully fetched {secret_description}")
            return secret_value

        except Exception as e:
            print(f"❌ [CONFIG] Error fetching {secret_description} ({env_var_name}): {e}")
            return None

    def fetch_payment_provider_token(self) -> Optional[str]:
        """
        Fetch the NowPayments API token from Secret Manager.

        Environment variable: PAYMENT_PROVIDER_SECRET_NAME

        Returns:
            NowPayments API token as string
        """
        return self.fetch_secret(
            "PAYMENT_PROVIDER_SECRET_NAME",
            "NowPayments API token"
        )

    def fetch_ipn_callback_url(self) -> Optional[str]:
        """
        Fetch the IPN callback URL from Secret Manager.
        This URL is used by NowPayments to send payment_id updates.

        Environment variable: NOWPAYMENTS_IPN_CALLBACK_URL

        Returns:
            IPN callback URL as string
        """
        return self.fetch_secret(
            "NOWPAYMENTS_IPN_CALLBACK_URL",
            "IPN callback URL"
        )

    def fetch_database_host(self) -> str:
        """
        Fetch database host from Secret Manager.

        Environment variable: DATABASE_HOST_SECRET

        Returns:
            Database host (Cloud SQL connection name)

        Raises:
            ValueError: If database host is not configured
        """
        host = self.fetch_secret("DATABASE_HOST_SECRET", "Database host")
        if not host:
            raise ValueError("Database host is required but not configured")
        return host

    def fetch_database_name(self) -> str:
        """Fetch database name from Secret Manager."""
        name = self.fetch_secret("DATABASE_NAME_SECRET", "Database name")
        if not name:
            raise ValueError("Database name is required but not configured")
        return name

    def fetch_database_user(self) -> str:
        """Fetch database user from Secret Manager."""
        user = self.fetch_secret("DATABASE_USER_SECRET", "Database user")
        if not user:
            raise ValueError("Database user is required but not configured")
        return user

    def fetch_database_password(self) -> str:
        """Fetch database password from Secret Manager."""
        password = self.fetch_secret("DATABASE_PASSWORD_SECRET", "Database password")
        if not password:
            raise ValueError("Database password is required but not configured")
        return password

    def initialize_config(self) -> Dict[str, Any]:
        """
        Initialize and return all configuration values.
        This method should be called once at application startup.

        Returns:
            Dictionary containing all configuration values

        Raises:
            ValueError: If critical configuration is missing
        """
        print("🔧 [CONFIG] Initializing configuration...")

        # Fetch payment provider configuration
        payment_token = self.fetch_payment_provider_token()
        if not payment_token:
            raise ValueError("Payment provider token is required")

        ipn_callback_url = self.fetch_ipn_callback_url()
        if not ipn_callback_url:
            print("⚠️ [CONFIG] IPN callback URL not configured - payment_id capture may not work")

        # Fetch database configuration
        db_host = self.fetch_database_host()
        db_name = self.fetch_database_name()
        db_user = self.fetch_database_user()
        db_password = self.fetch_database_password()

        # Build configuration dictionary
        self.config = {
            "payment_provider_token": payment_token,
            "ipn_callback_url": ipn_callback_url,
            "database_host": db_host,
            "database_name": db_name,
            "database_user": db_user,
            "database_password": db_password,
            "database_port": 5432,  # PostgreSQL default port
            "nowpayments_api_url": "https://api.nowpayments.io/v1/invoice",
            "landing_page_base_url": "https://storage.googleapis.com/paygateprime-static/payment-processing.html"
        }

        print("✅ [CONFIG] Configuration initialized successfully")
        print(f"   🌐 Payment Provider: NowPayments")
        print(f"   💰 IPN Callback: {'Configured' if ipn_callback_url else 'Not configured'}")
        print(f"   🗄️ Database: {db_name}")

        return self.config

    def get_config(self) -> Dict[str, Any]:
        """
        Get current configuration.

        Returns:
            Configuration dictionary
        """
        return self.config
