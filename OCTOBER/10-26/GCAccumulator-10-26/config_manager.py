#!/usr/bin/env python
"""
Configuration Manager for GCAccumulator-10-26 (Payment Accumulation Service).
Extends shared ConfigManager with GCAccumulator-specific configuration.

Migration Date: 2025-11-15
Extends: _shared/config_manager.ConfigManager
"""
import sys

# Add parent directory to Python path for shared library access
sys.path.insert(0, '/home/user/TelegramFunnel/OCTOBER/10-26')

from _shared.config_manager import ConfigManager as SharedConfigManager


class ConfigManager(SharedConfigManager):
    """
    GCAccumulator-specific configuration manager.
    Extends shared ConfigManager with accumulation and threshold payout configuration.
    """

    def initialize_config(self) -> dict:
        """
        Initialize and return all configuration values for GCAccumulator.

        Extends parent's initialize_config() to add:
        - Cloud Tasks configuration
        - GCSplit2 queue and URL (for USDT conversion estimates)
        - GCSplit3 queue and URL (for ETH→USDT swap creation)
        - GCHostPay1 queue and URL (for swap execution)
        - Platform USDT wallet address
        - Database credentials

        Returns:
            Dictionary containing all configuration values
        """
        print(f"⚙️ [CONFIG] Initializing GCAccumulator-10-26 configuration")

        # Call parent to get base configuration (SUCCESS_URL_SIGNING_KEY)
        config = super().initialize_config()

        # Fetch Cloud Tasks configuration using shared method
        cloud_tasks_config = self.fetch_common_cloud_tasks_config()

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

        # Platform wallet address
        platform_usdt_wallet_address = self.fetch_secret(
            "PLATFORM_USDT_WALLET_ADDRESS",
            "Platform USDT wallet address"
        )

        # Fetch database credentials using shared method
        db_config = self.fetch_common_database_config()

        # Validate critical configurations
        if not cloud_tasks_config['cloud_tasks_project_id'] or not cloud_tasks_config['cloud_tasks_location']:
            print(f"⚠️ [CONFIG] Warning: Cloud Tasks configuration incomplete")
        if not platform_usdt_wallet_address:
            print(f"⚠️ [CONFIG] Warning: PLATFORM_USDT_WALLET_ADDRESS not available")

        # Merge all configuration
        config.update({
            # Cloud Tasks configuration
            'cloud_tasks_project_id': cloud_tasks_config['cloud_tasks_project_id'],
            'cloud_tasks_location': cloud_tasks_config['cloud_tasks_location'],

            # Service queues and URLs
            'gcsplit2_queue': gcsplit2_queue,
            'gcsplit2_url': gcsplit2_url,
            'gcsplit3_queue': gcsplit3_queue,
            'gcsplit3_url': gcsplit3_url,
            'gchostpay1_queue': gchostpay1_queue,
            'gchostpay1_url': gchostpay1_url,

            # Platform configuration
            'platform_usdt_wallet_address': platform_usdt_wallet_address,

            # Database configuration
            'instance_connection_name': db_config['instance_connection_name'],
            'db_name': db_config['db_name'],
            'db_user': db_config['db_user'],
            'db_password': db_config['db_password']
        })

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
        print(f"   Platform USDT Wallet: {'✅' if config['platform_usdt_wallet_address'] else '❌'}")
        print(f"   Database: {'✅' if all([config['instance_connection_name'], config['db_name'], config['db_user'], config['db_password']]) else '❌'}")

        return config
