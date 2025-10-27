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
        Fetch a secret from Google Cloud Secret Manager.

        Args:
            secret_name_env: Environment variable containing the secret path
            description: Description for logging purposes

        Returns:
            Secret value or None if failed
        """
        try:
            secret_path = os.getenv(secret_name_env)
            if not secret_path:
                print(f"❌ [CONFIG] Environment variable {secret_name_env} is not set")
                return None

            print(f"🔐 [CONFIG] Fetching {description or secret_name_env}")
            response = self.client.access_secret_version(request={"name": secret_path})
            secret_value = response.payload.data.decode("UTF-8")

            print(f"✅ [CONFIG] Successfully fetched {description or secret_name_env}")
            return secret_value

        except Exception as e:
            print(f"❌ [CONFIG] Error fetching {description or secret_name_env}: {e}")
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
        print(f"   CLOUD_SQL_CONNECTION_NAME: {'✅' if config['instance_connection_name'] else '❌'}")
        print(f"   DATABASE_NAME_SECRET: {'✅' if config['db_name'] else '❌'}")
        print(f"   DATABASE_USER_SECRET: {'✅' if config['db_user'] else '❌'}")
        print(f"   DATABASE_PASSWORD_SECRET: {'✅' if config['db_password'] else '❌'}")

        return config
