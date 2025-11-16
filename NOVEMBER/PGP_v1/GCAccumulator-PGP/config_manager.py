#!/usr/bin/env python
"""
Configuration Manager for GCAccumulator-10-26 (Payment Accumulation Service).
Handles fetching configuration values from Google Cloud Secret Manager and environment variables.
"""
import os
from google.cloud import secretmanager
from typing import Optional


class ConfigManager:
    """
    Manages configuration and secrets for the GCAccumulator-10-26 service.
    """

    def __init__(self):
        """Initialize the ConfigManager."""
        self.client = secretmanager.SecretManagerServiceClient()
        print(f"⚙️ [CONFIG] ConfigManager initialized")

    def fetch_secret(self, secret_name_env: str, description: str = "") -> Optional[str]:
        """
        Fetch a secret value from environment variable.
        Cloud Run automatically injects secret values when using --set-secrets.

        Args:
            secret_name_env: Environment variable name containing the secret value
            description: Description for logging purposes

        Returns:
            Secret value or None if failed
        """
        try:
            # Defensive pattern: handle None, strip whitespace, return None if empty
            secret_value = (os.getenv(secret_name_env) or '').strip() or None
            if not secret_value:
                print(f"❌ [CONFIG] Environment variable {secret_name_env} is not set or empty")
                return None

            print(f"✅ [CONFIG] Successfully loaded {description or secret_name_env}")
            return secret_value

        except Exception as e:
            print(f"❌ [CONFIG] Error loading {description or secret_name_env}: {e}")
            return None

    def initialize_config(self) -> dict:
        """
        Initialize and return all configuration values for GCAccumulator.

        Returns:
            Dictionary containing all configuration values
        """
        print(f"⚙️ [CONFIG] Initializing GCAccumulator-10-26 configuration")

        # Fetch secrets from Secret Manager
        success_url_signing_key = self.fetch_secret(
            "SUCCESS_URL_SIGNING_KEY",
            "Success URL signing key (for token verification and encryption)"
        )

        # Get Cloud Tasks configuration from Secret Manager
        cloud_tasks_project_id = self.fetch_secret(
            "CLOUD_TASKS_PROJECT_ID",
            "Cloud Tasks project ID"
        )

        cloud_tasks_location = self.fetch_secret(
            "CLOUD_TASKS_LOCATION",
            "Cloud Tasks location/region"
        )

        # GCSplit2 configuration (for USDT conversion estimates)
        gcsplit2_queue = self.fetch_secret(
            "GCSPLIT2_QUEUE",
            "GCSplit2 queue name"
        )

        gcsplit2_url = self.fetch_secret(
            "GCSPLIT2_URL",
            "GCSplit2 service URL"
        )

        # GCSplit3 configuration (for ETH→USDT swap creation)
        gcsplit3_queue = self.fetch_secret(
            "GCSPLIT3_QUEUE",
            "GCSplit3 queue name"
        )

        gcsplit3_url = self.fetch_secret(
            "GCSPLIT3_URL",
            "GCSplit3 service URL"
        )

        # GCHostPay1 configuration (for swap execution)
        gchostpay1_queue = self.fetch_secret(
            "GCHOSTPAY1_QUEUE",
            "GCHostPay1 queue name"
        )

        gchostpay1_url = self.fetch_secret(
            "GCHOSTPAY1_URL",
            "GCHostPay1 service URL"
        )

        # Host wallet configuration
        host_wallet_usdt_address = self.fetch_secret(
            "HOST_WALLET_USDT_ADDRESS",
            "Host USDT wallet address"
        )

        # Fetch database configuration from Secret Manager
        cloud_sql_connection_name = self.fetch_secret(
            "CLOUD_SQL_CONNECTION_NAME",
            "Cloud SQL instance connection name"
        )

        database_name = self.fetch_secret(
            "DATABASE_NAME_SECRET",
            "Database name"
        )

        database_user = self.fetch_secret(
            "DATABASE_USER_SECRET",
            "Database user"
        )

        database_password = self.fetch_secret(
            "DATABASE_PASSWORD_SECRET",
            "Database password"
        )

        # TP fee configuration (for fee calculation)
        tp_flat_fee = self.fetch_secret(
            "TP_FLAT_FEE",
            "TP flat fee percentage"
        ) or "3"  # Default 3%

        # Validate critical configurations
        if not success_url_signing_key:
            print(f"⚠️ [CONFIG] Warning: SUCCESS_URL_SIGNING_KEY not available")
        if not cloud_tasks_project_id or not cloud_tasks_location:
            print(f"⚠️ [CONFIG] Warning: Cloud Tasks configuration incomplete")

        config = {
            # Secrets
            'success_url_signing_key': success_url_signing_key,

            # Cloud Tasks configuration
            'cloud_tasks_project_id': cloud_tasks_project_id,
            'cloud_tasks_location': cloud_tasks_location,
            'gcsplit2_queue': gcsplit2_queue,
            'gcsplit2_url': gcsplit2_url,
            'gcsplit3_queue': gcsplit3_queue,
            'gcsplit3_url': gcsplit3_url,
            'gchostpay1_queue': gchostpay1_queue,
            'gchostpay1_url': gchostpay1_url,

            # Wallet configuration
            'host_wallet_usdt_address': host_wallet_usdt_address,

            # Database configuration (all from Secret Manager)
            'instance_connection_name': cloud_sql_connection_name,
            'db_name': database_name,
            'db_user': database_user,
            'db_password': database_password,

            # Fee configuration
            'tp_flat_fee': tp_flat_fee
        }

        # Log configuration status
        print(f"📊 [CONFIG] Configuration status:")
        print(f"   SUCCESS_URL_SIGNING_KEY: {'✅' if config['success_url_signing_key'] else '❌'}")
        print(f"   Cloud Tasks Project: {'✅' if config['cloud_tasks_project_id'] else '❌'}")
        print(f"   Cloud Tasks Location: {'✅' if config['cloud_tasks_location'] else '❌'}")
        print(f"   GCSplit2 Queue: {'✅' if config['gcsplit2_queue'] else '❌'}")
        print(f"   GCSplit2 URL: {'✅' if config['gcsplit2_url'] else '❌'}")
        print(f"   GCSplit3 Queue: {'✅' if config['gcsplit3_queue'] else '❌'}")
        print(f"   GCSplit3 URL: {'✅' if config['gcsplit3_url'] else '❌'}")
        print(f"   GCHostPay1 Queue: {'✅' if config['gchostpay1_queue'] else '❌'}")
        print(f"   GCHostPay1 URL: {'✅' if config['gchostpay1_url'] else '❌'}")
        print(f"   Host USDT Wallet: {'✅' if config['host_wallet_usdt_address'] else '❌'}")
        print(f"   CLOUD_SQL_CONNECTION_NAME: {'✅' if config['instance_connection_name'] else '❌'}")
        print(f"   DATABASE_NAME_SECRET: {'✅' if config['db_name'] else '❌'}")
        print(f"   DATABASE_USER_SECRET: {'✅' if config['db_user'] else '❌'}")
        print(f"   DATABASE_PASSWORD_SECRET: {'✅' if config['db_password'] else '❌'}")
        print(f"   TP_FLAT_FEE: {config['tp_flat_fee']}%")

        return config
