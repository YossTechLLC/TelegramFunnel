#!/usr/bin/env python
"""
Configuration Manager for GCBatchProcessor-10-26 (Batch Payout Processor Service).
Extends shared ConfigManager with GCBatchProcessor-specific configuration.

Migration Date: 2025-11-15
Extends: _shared/config_manager.ConfigManager
"""
import sys

# Add parent directory to Python path for shared library access
sys.path.insert(0, '/home/user/TelegramFunnel/OCTOBER/10-26')

from _shared.config_manager import ConfigManager as SharedConfigManager


class ConfigManager(SharedConfigManager):
    """
    GCBatchProcessor-specific configuration manager.
    Extends shared ConfigManager with batch processing and payout configuration.
    """

    def initialize_config(self) -> dict:
        """
        Initialize and return all configuration values for GCBatchProcessor.

        Extends parent's initialize_config() to add:
        - TPS HostPay signing key
        - Cloud Tasks configuration
        - GCSplit1 batch queue and URL
        - Database credentials

        Returns:
            Dictionary containing all configuration values
        """
        print(f"⚙️ [CONFIG] Initializing GCBatchProcessor-10-26 configuration")

        # Call parent to get base configuration (SUCCESS_URL_SIGNING_KEY)
        config = super().initialize_config()

        # Fetch GCBatchProcessor-specific secrets
        tps_hostpay_signing_key = self.fetch_secret(
            "TPS_HOSTPAY_SIGNING_KEY",
            "TPS-HostPay signing key (for batch payout tokens)"
        )

        # Fetch Cloud Tasks configuration using shared method
        cloud_tasks_config = self.fetch_common_cloud_tasks_config()

        # GCSplit1 configuration (for batch payout execution)
        gcsplit1_batch_queue = self.fetch_secret(
            "GCSPLIT1_BATCH_QUEUE",
            "GCSplit1 batch queue name"
        )

        gcsplit1_url = self.fetch_secret(
            "GCSPLIT1_URL",
            "GCSplit1 service URL"
        )

        # Fetch database credentials using shared method
        db_config = self.fetch_common_database_config()

        # Validate critical configurations
        if not tps_hostpay_signing_key:
            print(f"⚠️ [CONFIG] Warning: TPS_HOSTPAY_SIGNING_KEY not available")
        if not cloud_tasks_config['cloud_tasks_project_id'] or not cloud_tasks_config['cloud_tasks_location']:
            print(f"⚠️ [CONFIG] Warning: Cloud Tasks configuration incomplete")

        # Merge all configuration
        config.update({
            # GCBatchProcessor-specific secrets
            'tps_hostpay_signing_key': tps_hostpay_signing_key,

            # Cloud Tasks configuration
            'cloud_tasks_project_id': cloud_tasks_config['cloud_tasks_project_id'],
            'cloud_tasks_location': cloud_tasks_config['cloud_tasks_location'],
            'gcsplit1_batch_queue': gcsplit1_batch_queue,
            'gcsplit1_url': gcsplit1_url,

            # Database configuration
            'instance_connection_name': db_config['instance_connection_name'],
            'db_name': db_config['db_name'],
            'db_user': db_config['db_user'],
            'db_password': db_config['db_password']
        })

        # Log configuration status
        print(f"📊 [CONFIG] Configuration status:")
        print(f"   SUCCESS_URL_SIGNING_KEY: {'✅' if config['success_url_signing_key'] else '❌'}")
        print(f"   TPS_HOSTPAY_SIGNING_KEY: {'✅' if config['tps_hostpay_signing_key'] else '❌'}")
        print(f"   Cloud Tasks Project: {'✅' if config['cloud_tasks_project_id'] else '❌'}")
        print(f"   Cloud Tasks Location: {'✅' if config['cloud_tasks_location'] else '❌'}")
        print(f"   GCSplit1 Batch Queue: {'✅' if config['gcsplit1_batch_queue'] else '❌'}")
        print(f"   GCSplit1 URL: {'✅' if config['gcsplit1_url'] else '❌'}")
        print(f"   Database: {'✅' if all([config['instance_connection_name'], config['db_name'], config['db_user'], config['db_password']]) else '❌'}")

        return config
