#!/usr/bin/env python
"""
Configuration Manager for GCHostPay3-10-26 (ETH Payment Executor Service).
Extends shared ConfigManager with GCHostPay3-specific configuration.

Migration Date: 2025-11-15
Extends: _shared/config_manager.ConfigManager
"""
import sys

# Add parent directory to Python path for shared library access
sys.path.insert(0, '/home/user/TelegramFunnel/OCTOBER/10-26')

from _shared.config_manager import ConfigManager as SharedConfigManager


class ConfigManager(SharedConfigManager):
    """
    GCHostPay3-specific configuration manager.
    Extends shared ConfigManager with ETH payment execution configuration.
    """

    def initialize_config(self) -> dict:
        """
        Initialize and return all configuration values for GCHostPay3.

        Extends parent's initialize_config() to add:
        - Host wallet address and private key
        - Ethereum RPC URLs
        - Etherscan API key
        - Cloud Tasks configuration
        - Database credentials

        Returns:
            Dictionary containing all configuration values
        """
        print(f"⚙️ [CONFIG] Initializing GCHostPay3-10-26 configuration")

        # Call parent to get base configuration (SUCCESS_URL_SIGNING_KEY)
        config = super().initialize_config()

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
            "Ethereum RPC URL with API key"
        )

        # Fetch Etherscan API key
        etherscan_api_key = self.fetch_secret(
            "ETHERSCAN_API_KEY",
            "Etherscan API key"
        )

        # Fetch Cloud Tasks configuration using shared method
        cloud_tasks_config = self.fetch_common_cloud_tasks_config()

        # Fetch database credentials using shared method
        db_config = self.fetch_common_database_config()

        # Validate critical configurations
        if not host_wallet_address or not host_wallet_private_key:
            print(f"⚠️ [CONFIG] Warning: Host wallet credentials not available")
        if not ethereum_rpc_url:
            print(f"⚠️ [CONFIG] Warning: ETHEREUM_RPC_URL not available")
        if not cloud_tasks_config['cloud_tasks_project_id'] or not cloud_tasks_config['cloud_tasks_location']:
            print(f"⚠️ [CONFIG] Warning: Cloud Tasks configuration incomplete")

        # Merge all configuration
        config.update({
            # GCHostPay3-specific secrets
            'host_wallet_address': host_wallet_address,
            'host_wallet_private_key': host_wallet_private_key,
            'ethereum_rpc_url': ethereum_rpc_url,
            'ethereum_rpc_url_api': ethereum_rpc_url_api,
            'etherscan_api_key': etherscan_api_key,

            # Cloud Tasks configuration
            'cloud_tasks_project_id': cloud_tasks_config['cloud_tasks_project_id'],
            'cloud_tasks_location': cloud_tasks_config['cloud_tasks_location'],

            # Database configuration
            'instance_connection_name': db_config['instance_connection_name'],
            'db_name': db_config['db_name'],
            'db_user': db_config['db_user'],
            'db_password': db_config['db_password']
        })

        # Log configuration status
        print(f"📊 [CONFIG] Configuration status:")
        print(f"   SUCCESS_URL_SIGNING_KEY: {'✅' if config['success_url_signing_key'] else '❌'}")
        print(f"   HOST_WALLET_ETH_ADDRESS: {'✅' if config['host_wallet_address'] else '❌'}")
        print(f"   HOST_WALLET_PRIVATE_KEY: {'✅' if config['host_wallet_private_key'] else '❌'}")
        print(f"   ETHEREUM_RPC_URL: {'✅' if config['ethereum_rpc_url'] else '❌'}")
        print(f"   ETHEREUM_RPC_URL_API: {'✅' if config['ethereum_rpc_url_api'] else '❌'}")
        print(f"   ETHERSCAN_API_KEY: {'✅' if config['etherscan_api_key'] else '❌'}")
        print(f"   Cloud Tasks Project: {'✅' if config['cloud_tasks_project_id'] else '❌'}")
        print(f"   Cloud Tasks Location: {'✅' if config['cloud_tasks_location'] else '❌'}")
        print(f"   Database: {'✅' if all([config['instance_connection_name'], config['db_name'], config['db_user'], config['db_password']]) else '❌'}")

        return config
