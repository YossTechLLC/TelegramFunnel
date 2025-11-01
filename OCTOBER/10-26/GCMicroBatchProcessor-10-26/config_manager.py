#!/usr/bin/env python
"""
Configuration Manager for GCMicroBatchProcessor-10-26 (Micro-Batch Conversion Service).
Handles fetching configuration values from Google Cloud Secret Manager and environment variables.
"""
import os
from decimal import Decimal
from google.cloud import secretmanager
from typing import Optional


class ConfigManager:
    """
    Manages configuration and secrets for the GCMicroBatchProcessor-10-26 service.
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
            secret_value = os.getenv(secret_name_env)
            if not secret_value:
                print(f"❌ [CONFIG] Environment variable {secret_name_env} is not set")
                return None

            print(f"✅ [CONFIG] Successfully loaded {description or secret_name_env}")
            return secret_value

        except Exception as e:
            print(f"❌ [CONFIG] Error loading {description or secret_name_env}: {e}")
            return None

    def get_micro_batch_threshold(self) -> Decimal:
        """
        Fetch micro-batch threshold from Google Cloud Secret Manager.

        Returns:
            Decimal threshold value (e.g., Decimal('20.00'))
        """
        try:
            # Try to get from env variable first (for Cloud Run deployment)
            threshold_str = os.getenv('MICRO_BATCH_THRESHOLD_USD')

            if not threshold_str:
                # Fallback to direct Secret Manager access
                project_id = os.getenv('CLOUD_TASKS_PROJECT_ID', 'telepay-459221')
                secret_name = f"projects/{project_id}/secrets/MICRO_BATCH_THRESHOLD_USD/versions/latest"

                print(f"🔐 [CONFIG] Fetching threshold from Secret Manager")
                response = self.client.access_secret_version(request={"name": secret_name})
                threshold_str = response.payload.data.decode('UTF-8')

            threshold = Decimal(threshold_str)
            print(f"✅ [CONFIG] Threshold fetched: ${threshold}")
            return threshold

        except Exception as e:
            print(f"❌ [CONFIG] Failed to fetch threshold: {e}")
            print(f"⚠️ [CONFIG] Using fallback threshold: $20.00")
            return Decimal('20.00')

    def initialize_config(self) -> dict:
        """
        Initialize and return all configuration values for GCMicroBatchProcessor.

        Returns:
            Dictionary containing all configuration values
        """
        print(f"⚙️ [CONFIG] Initializing GCMicroBatchProcessor-10-26 configuration")

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

        # GCHostPay1 batch configuration
        gchostpay1_batch_queue = self.fetch_secret(
            "GCHOSTPAY1_BATCH_QUEUE",
            "GCHostPay1 batch queue name"
        )

        gchostpay1_url = self.fetch_secret(
            "GCHOSTPAY1_URL",
            "GCHostPay1 service URL"
        )

        # ChangeNow API key
        changenow_api_key = self.fetch_secret(
            "CHANGENOW_API_KEY",
            "ChangeNow API key"
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
            'gchostpay1_batch_queue': gchostpay1_batch_queue,
            'gchostpay1_url': gchostpay1_url,

            # ChangeNow configuration
            'changenow_api_key': changenow_api_key,

            # Wallet configuration
            'host_wallet_usdt_address': host_wallet_usdt_address,

            # Database configuration (all from Secret Manager)
            'instance_connection_name': cloud_sql_connection_name,
            'db_name': database_name,
            'db_user': database_user,
            'db_password': database_password
        }

        # Log configuration status
        print(f"📊 [CONFIG] Configuration status:")
        print(f"   SUCCESS_URL_SIGNING_KEY: {'✅' if config['success_url_signing_key'] else '❌'}")
        print(f"   Cloud Tasks Project: {'✅' if config['cloud_tasks_project_id'] else '❌'}")
        print(f"   Cloud Tasks Location: {'✅' if config['cloud_tasks_location'] else '❌'}")
        print(f"   GCHostPay1 Batch Queue: {'✅' if config['gchostpay1_batch_queue'] else '❌'}")
        print(f"   GCHostPay1 URL: {'✅' if config['gchostpay1_url'] else '❌'}")
        print(f"   ChangeNow API Key: {'✅' if config['changenow_api_key'] else '❌'}")
        print(f"   Host USDT Wallet: {'✅' if config['host_wallet_usdt_address'] else '❌'}")
        print(f"   CLOUD_SQL_CONNECTION_NAME: {'✅' if config['instance_connection_name'] else '❌'}")
        print(f"   DATABASE_NAME_SECRET: {'✅' if config['db_name'] else '❌'}")
        print(f"   DATABASE_USER_SECRET: {'✅' if config['db_user'] else '❌'}")
        print(f"   DATABASE_PASSWORD_SECRET: {'✅' if config['db_password'] else '❌'}")

        return config
