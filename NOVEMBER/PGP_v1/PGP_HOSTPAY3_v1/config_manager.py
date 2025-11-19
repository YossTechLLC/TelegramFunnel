#!/usr/bin/env python
"""
Configuration Manager for PGP_HOSTPAY3_v1 (ETH Payment Executor Service).
Handles fetching configuration values from Google Cloud Secret Manager.
"""
from PGP_COMMON.config import BaseConfigManager


class ConfigManager(BaseConfigManager):
    """
    Manages configuration and secrets for the PGP_HOSTPAY3_v1 service.
    Inherits common methods from BaseConfigManager.
    """

    def __init__(self):
        """Initialize the ConfigManager."""
        super().__init__(service_name="PGP_HOSTPAY3_v1")

    # ========== HOT-RELOADABLE SECRET GETTERS ==========

    def get_ethereum_rpc_url(self) -> str:
        """Get Ethereum RPC URL (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("ETHEREUM_RPC_URL")
        return self.fetch_secret_dynamic(
            secret_path,
            "Ethereum RPC URL",
            cache_key="ethereum_rpc_url"
        )

    def get_ethereum_rpc_url_api(self) -> str:
        """Get Ethereum RPC URL API key (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("ETHEREUM_RPC_URL_API")
        return self.fetch_secret_dynamic(
            secret_path,
            "Ethereum RPC URL API key",
            cache_key="ethereum_rpc_url_api"
        )

    def get_pgp_hostpay1_response_queue(self) -> str:
        """Get PGP HostPay1 response queue name (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("PGP_HOSTPAY1_RESPONSE_QUEUE")
        return self.fetch_secret_dynamic(
            secret_path,
            "PGP HostPay1 response queue",
            cache_key="pgp_hostpay1_response_queue"
        )

    def get_pgp_hostpay1_url(self) -> str:
        """Get PGP HostPay1 service URL (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("PGP_HOSTPAY1_URL")
        return self.fetch_secret_dynamic(
            secret_path,
            "PGP HostPay1 URL",
            cache_key="pgp_hostpay1_url"
        )

    def get_pgp_hostpay3_retry_queue(self) -> str:
        """Get PGP HostPay3 self-retry queue name (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("PGP_HOSTPAY3_RETRY_QUEUE")
        return self.fetch_secret_dynamic(
            secret_path,
            "PGP HostPay3 retry queue",
            cache_key="pgp_hostpay3_retry_queue"
        )

    def get_pgp_hostpay3_url(self) -> str:
        """Get PGP HostPay3 service URL (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("PGP_HOSTPAY3_URL")
        return self.fetch_secret_dynamic(
            secret_path,
            "PGP HostPay3 URL",
            cache_key="pgp_hostpay3_url"
        )

    # ========== INITIALIZATION ==========

    def initialize_config(self) -> dict:
        """
        Initialize and return all configuration values for PGP_HOSTPAY3_v1.

        Returns:
            Dictionary containing all configuration values
        """
        print(f"⚙️ [CONFIG] Initializing PGP_HOSTPAY3_v1 configuration")

        # Use base methods to fetch common configurations
        ct_config = self.fetch_cloud_tasks_config()
        db_config = self.fetch_database_config()

        # Fetch STATIC signing key (security-critical)
        success_url_signing_key = self.fetch_secret(
            "SUCCESS_URL_SIGNING_KEY",
            "Success URL signing key (for internal PGP HostPay communication) - STATIC"
        )

        # Fetch STATIC wallet credentials (security-critical)
        host_wallet_address = self.fetch_secret(
            "HOST_WALLET_ETH_ADDRESS",
            "Host wallet ETH address - STATIC"
        )

        host_wallet_private_key = self.fetch_secret(
            "HOST_WALLET_PRIVATE_KEY",
            "Host wallet private key - STATIC"
        )

        # Validate critical configurations
        if not success_url_signing_key:
            print(f"⚠️ [CONFIG] Warning: SUCCESS_URL_SIGNING_KEY not available")
        if not host_wallet_address or not host_wallet_private_key:
            print(f"⚠️ [CONFIG] Warning: Wallet credentials not available")
        if not ct_config['cloud_tasks_project_id'] or not ct_config['cloud_tasks_location']:
            print(f"⚠️ [CONFIG] Warning: Cloud Tasks configuration incomplete")

        # Combine all configurations
        # Note: Hot-reloadable secrets are NOT fetched here - they are fetched on-demand via getter methods
        config = {
            # STATIC Signing key (loaded once at startup)
            'success_url_signing_key': success_url_signing_key,

            # STATIC Wallet credentials (loaded once at startup - security-critical)
            'host_wallet_address': host_wallet_address,
            'host_wallet_private_key': host_wallet_private_key,

            # Cloud Tasks configuration (from base method)
            **ct_config,

            # Database configuration (from base method)
            **db_config
        }

        # Log configuration status
        print(f"📊 [CONFIG] Configuration status:")
        print(f"   SUCCESS_URL_SIGNING_KEY (static): {'✅' if config['success_url_signing_key'] else '❌'}")
        print(f"   HOST_WALLET_ETH_ADDRESS (static): {'✅' if config['host_wallet_address'] else '❌'}")
        print(f"   HOST_WALLET_PRIVATE_KEY (static): {'✅' if config['host_wallet_private_key'] else '❌'}")
        print(f"   Cloud Tasks Project: {'✅' if config['cloud_tasks_project_id'] else '❌'}")
        print(f"   Cloud Tasks Location: {'✅' if config['cloud_tasks_location'] else '❌'}")
        print(f"   CLOUD_SQL_CONNECTION_NAME: {'✅' if config['instance_connection_name'] else '❌'}")
        print(f"   DATABASE_NAME_SECRET: {'✅' if config['db_name'] else '❌'}")
        print(f"   DATABASE_USER_SECRET: {'✅' if config['db_user'] else '❌'}")
        print(f"   DATABASE_PASSWORD_SECRET: {'✅' if config['db_password'] else '❌'}")
        print(f"   Hot-reloadable secrets: ETHEREUM_RPC_URL/API, PGP_HOSTPAY1_URL/QUEUE, PGP_HOSTPAY3_URL/RETRY_QUEUE")

        return config
