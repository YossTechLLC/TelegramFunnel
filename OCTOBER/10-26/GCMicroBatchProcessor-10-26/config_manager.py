#!/usr/bin/env python
"""
Configuration Manager for GCMicroBatchProcessor-10-26 (Micro-Batch Conversion Service).
Extends shared ConfigManager with GCMicroBatchProcessor-specific configuration.

Migration Date: 2025-11-15
Extends: _shared/config_manager.ConfigManager
"""
import sys
from decimal import Decimal

# Add parent directory to Python path for shared library access
sys.path.insert(0, '/home/user/TelegramFunnel/OCTOBER/10-26')

from _shared.config_manager import ConfigManager as SharedConfigManager


class ConfigManager(SharedConfigManager):
    """
    GCMicroBatchProcessor-specific configuration manager.
    Extends shared ConfigManager with micro-batch processing and ChangeNOW configuration.
    """

    def get_micro_batch_threshold(self) -> Decimal:
        """
        Fetch micro-batch threshold from Google Cloud Secret Manager.

        Returns:
            Decimal: Micro-batch threshold value (default 10.00 USDT)
        """
        try:
            threshold_str = self.fetch_secret(
                "MICRO_BATCH_THRESHOLD",
                "Micro-batch threshold in USDT"
            )
            if threshold_str:
                return Decimal(threshold_str)
            else:
                print(f"⚠️ [CONFIG] MICRO_BATCH_THRESHOLD not set, defaulting to 10.00")
                return Decimal("10.00")
        except Exception as e:
            print(f"❌ [CONFIG] Error fetching micro-batch threshold: {e}")
            print(f"⚠️ [CONFIG] Defaulting to 10.00")
            return Decimal("10.00")

    def initialize_config(self) -> dict:
        """
        Initialize and return all configuration values for GCMicroBatchProcessor.

        Extends parent's initialize_config() to add:
        - ChangeNOW API key
        - Micro-batch threshold
        - Cloud Tasks configuration
        - Database credentials

        Returns:
            Dictionary containing all configuration values
        """
        print(f"⚙️ [CONFIG] Initializing GCMicroBatchProcessor-10-26 configuration")

        # Call parent to get base configuration (SUCCESS_URL_SIGNING_KEY)
        config = super().initialize_config()

        # Fetch GCMicroBatchProcessor-specific secrets
        changenow_api_key = self.fetch_secret(
            "CHANGENOW_API_KEY",
            "ChangeNow API key"
        )

        # Get micro-batch threshold
        micro_batch_threshold = self.get_micro_batch_threshold()

        # Fetch Cloud Tasks configuration using shared method
        cloud_tasks_config = self.fetch_common_cloud_tasks_config()

        # Fetch database credentials using shared method
        db_config = self.fetch_common_database_config()

        # Validate critical configurations
        if not changenow_api_key:
            print(f"⚠️ [CONFIG] Warning: CHANGENOW_API_KEY not available")
        if not cloud_tasks_config['cloud_tasks_project_id'] or not cloud_tasks_config['cloud_tasks_location']:
            print(f"⚠️ [CONFIG] Warning: Cloud Tasks configuration incomplete")

        # Merge all configuration
        config.update({
            # GCMicroBatchProcessor-specific secrets
            'changenow_api_key': changenow_api_key,
            'micro_batch_threshold': micro_batch_threshold,

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
        print(f"   CHANGENOW_API_KEY: {'✅' if config['changenow_api_key'] else '❌'}")
        print(f"   MICRO_BATCH_THRESHOLD: {micro_batch_threshold} USDT")
        print(f"   Cloud Tasks Project: {'✅' if config['cloud_tasks_project_id'] else '❌'}")
        print(f"   Cloud Tasks Location: {'✅' if config['cloud_tasks_location'] else '❌'}")
        print(f"   Database: {'✅' if all([config['instance_connection_name'], config['db_name'], config['db_user'], config['db_password']]) else '❌'}")

        return config
