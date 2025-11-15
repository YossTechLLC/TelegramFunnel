#!/usr/bin/env python
"""
Configuration Manager for GCHostPay3-10-26 (ETH Payment Executor Service).
Handles fetching configuration values from Google Cloud Secret Manager.
"""
import os
from google.cloud import secretmanager
from typing import Optional


class ConfigManager:
    """
    Manages configuration and secrets for the GCHostPay3-10-26 service.
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
        Initialize and return all configuration values for GCHostPay3.

        Returns:
            Dictionary containing all configuration values
        """
        print(f"⚙️ [CONFIG] Initializing GCHostPay3-10-26 configuration")

        # Fetch signing key for internal communication
        success_url_signing_key = self.fetch_secret(
            "SUCCESS_URL_SIGNING_KEY",
            "Success URL signing key (for internal GCHostPay communication)"
        )

        # Fetch wallet credentials
        host_wallet_address = self.fetch_secret(
            "HOST_WALLET_ETH_ADDRESS",
            "Host wallet ETH address"
        )

        host_wallet_private_key = self.fetch_secret(
            "HOST_WALLET_PRIVATE_KEY",
            "Host wallet private key"
        )

        # Fetch Ethereum RPC configuration
        ethereum_rpc_url = self.fetch_secret(
            "ETHEREUM_RPC_URL",
            "Ethereum RPC URL"
        )

        ethereum_rpc_url_api = self.fetch_secret(
            "ETHEREUM_RPC_URL_API",
            "Ethereum RPC URL API key"
        )

        # Get Cloud Tasks configuration
        cloud_tasks_project_id = self.fetch_secret(
            "CLOUD_TASKS_PROJECT_ID",
            "Cloud Tasks project ID"
        )

        cloud_tasks_location = self.fetch_secret(
            "CLOUD_TASKS_LOCATION",
            "Cloud Tasks location/region"
        )

        # Get GCHostPay1 response queue configuration
        gchostpay1_response_queue = self.fetch_secret(
            "GCHOSTPAY1_RESPONSE_QUEUE",
            "GCHostPay1 response queue name"
        )

        gchostpay1_url = self.fetch_secret(
            "GCHOSTPAY1_URL",
            "GCHostPay1 service URL"
        )

        # Get GCAccumulator response queue configuration (for threshold payouts)
        gcaccumulator_response_queue = self.fetch_secret(
            "GCACCUMULATOR_RESPONSE_QUEUE",
            "GCAccumulator response queue name"
        )

        gcaccumulator_url = self.fetch_secret(
            "GCACCUMULATOR_URL",
            "GCAccumulator service URL"
        )

        # NEW: Get GCHostPay3 self-retry configuration (for error handling)
        gchostpay3_retry_queue = self.fetch_secret(
            "GCHOSTPAY3_RETRY_QUEUE",
            "GCHostPay3 self-retry queue name"
        )

        gchostpay3_url = self.fetch_secret(
            "GCHOSTPAY3_URL",
            "GCHostPay3 service URL"
        )

        # NEW: Get alerting configuration (optional)
        alerting_enabled = self.fetch_secret(
            "ALERTING_ENABLED",
            "Alerting enabled flag"
        )

        slack_alert_webhook = self.fetch_secret(
            "SLACK_ALERT_WEBHOOK",
            "Slack webhook URL for alerts (optional)"
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
        if not host_wallet_address or not host_wallet_private_key:
            print(f"⚠️ [CONFIG] Warning: Wallet credentials not available")
        if not ethereum_rpc_url:
            print(f"⚠️ [CONFIG] Warning: Ethereum RPC URL not available")
        if not cloud_tasks_project_id or not cloud_tasks_location:
            print(f"⚠️ [CONFIG] Warning: Cloud Tasks configuration incomplete")

        config = {
            # Signing key
            'success_url_signing_key': success_url_signing_key,

            # Wallet credentials
            'host_wallet_address': host_wallet_address,
            'host_wallet_private_key': host_wallet_private_key,

            # Ethereum RPC
            'ethereum_rpc_url': ethereum_rpc_url,
            'ethereum_rpc_url_api': ethereum_rpc_url_api,

            # Cloud Tasks configuration
            'cloud_tasks_project_id': cloud_tasks_project_id,
            'cloud_tasks_location': cloud_tasks_location,
            'gchostpay1_response_queue': gchostpay1_response_queue,
            'gchostpay1_url': gchostpay1_url,
            'gcaccumulator_response_queue': gcaccumulator_response_queue,
            'gcaccumulator_url': gcaccumulator_url,

            # NEW: Self-retry configuration (error handling)
            'gchostpay3_retry_queue': gchostpay3_retry_queue,
            'gchostpay3_url': gchostpay3_url,

            # NEW: Alerting configuration (optional)
            'alerting_enabled': alerting_enabled,
            'slack_alert_webhook': slack_alert_webhook,

            # Database configuration
            'instance_connection_name': cloud_sql_connection_name,
            'db_name': database_name,
            'db_user': database_user,
            'db_password': database_password
        }

        # Log configuration status
        print(f"📊 [CONFIG] Configuration status:")
        print(f"   SUCCESS_URL_SIGNING_KEY: {'✅' if config['success_url_signing_key'] else '❌'}")
        print(f"   HOST_WALLET_ETH_ADDRESS: {'✅' if config['host_wallet_address'] else '❌'}")
        print(f"   HOST_WALLET_PRIVATE_KEY: {'✅' if config['host_wallet_private_key'] else '❌'}")
        print(f"   ETHEREUM_RPC_URL: {'✅' if config['ethereum_rpc_url'] else '❌'}")
        print(f"   ETHEREUM_RPC_URL_API: {'✅' if config['ethereum_rpc_url_api'] else '❌'}")
        print(f"   Cloud Tasks Project: {'✅' if config['cloud_tasks_project_id'] else '❌'}")
        print(f"   Cloud Tasks Location: {'✅' if config['cloud_tasks_location'] else '❌'}")
        print(f"   GCHostPay1 Response Queue: {'✅' if config['gchostpay1_response_queue'] else '❌'}")
        print(f"   GCHostPay1 URL: {'✅' if config['gchostpay1_url'] else '❌'}")
        print(f"   GCAccumulator Response Queue: {'✅' if config['gcaccumulator_response_queue'] else '❌'}")
        print(f"   GCAccumulator URL: {'✅' if config['gcaccumulator_url'] else '❌'}")
        print(f"   GCHostPay3 Retry Queue: {'✅' if config['gchostpay3_retry_queue'] else '❌'}")
        print(f"   GCHostPay3 URL: {'✅' if config['gchostpay3_url'] else '❌'}")
        print(f"   Alerting Enabled: {'✅' if config['alerting_enabled'] else '⚠️ (optional)'}")
        print(f"   Slack Alert Webhook: {'✅' if config['slack_alert_webhook'] else '⚠️ (optional)'}")
        print(f"   CLOUD_SQL_CONNECTION_NAME: {'✅' if config['instance_connection_name'] else '❌'}")
        print(f"   DATABASE_NAME_SECRET: {'✅' if config['db_name'] else '❌'}")
        print(f"   DATABASE_USER_SECRET: {'✅' if config['db_user'] else '❌'}")
        print(f"   DATABASE_PASSWORD_SECRET: {'✅' if config['db_password'] else '❌'}")

        return config
