#!/usr/bin/env python
"""
Configuration Manager for GCSplit3-10-26 (ETH→ClientCurrency Swapper Service).
Extends shared ConfigManager with GCSplit3-specific configuration.

Migration Date: 2025-11-15
Extends: _shared/config_manager.ConfigManager
"""
import sys

# Add parent directory to Python path for shared library access
sys.path.insert(0, '/home/user/TelegramFunnel/OCTOBER/10-26')

from _shared.config_manager import ConfigManager as SharedConfigManager


class ConfigManager(SharedConfigManager):
    """
    GCSplit3-specific configuration manager.
    Extends shared ConfigManager with ChangeNOW API and GCAccumulator queue configuration.
    """

    def initialize_config(self) -> dict:
        """
        Initialize and return all configuration values for GCSplit3.

        Extends parent's initialize_config() to add:
        - ChangeNOW API key
        - Cloud Tasks configuration
        - GCAccumulator response queue and URL
        - Database credentials (if needed)

        Returns:
            Dictionary containing all configuration values
        """
        print(f"⚙️ [CONFIG] Initializing GCSplit3-10-26 configuration")

        # Call parent to get base configuration (SUCCESS_URL_SIGNING_KEY)
        config = super().initialize_config()

        # Fetch GCSplit3-specific secrets
        changenow_api_key = self.fetch_secret(
            "CHANGENOW_API_KEY",
            "ChangeNow API key"
        )

        # Fetch Cloud Tasks configuration using shared method
        cloud_tasks_config = self.fetch_common_cloud_tasks_config()

        # Fetch queue/URL configurations
        gcaccumulator_response_queue = self.fetch_secret(
            "GCACCUMULATOR_RESPONSE_QUEUE",
            "GCAccumulator response queue name"
        )

        gcaccumulator_url = self.fetch_secret(
            "GCACCUMULATOR_URL",
            "GCAccumulator service URL"
        )

        # Validate critical configurations
        if not changenow_api_key:
            print(f"⚠️ [CONFIG] Warning: CHANGENOW_API_KEY not available")
        if not cloud_tasks_config['cloud_tasks_project_id'] or not cloud_tasks_config['cloud_tasks_location']:
            print(f"⚠️ [CONFIG] Warning: Cloud Tasks configuration incomplete")

        # Merge all configuration
        config.update({
            # GCSplit3-specific secrets
            'changenow_api_key': changenow_api_key,

            # Cloud Tasks configuration
            'cloud_tasks_project_id': cloud_tasks_config['cloud_tasks_project_id'],
            'cloud_tasks_location': cloud_tasks_config['cloud_tasks_location'],
            'gcaccumulator_response_queue': gcaccumulator_response_queue,
            'gcaccumulator_url': gcaccumulator_url
        })

        # Log configuration status
        print(f"📊 [CONFIG] Configuration status:")
        print(f"   SUCCESS_URL_SIGNING_KEY: {'✅' if config['success_url_signing_key'] else '❌'}")
        print(f"   CHANGENOW_API_KEY: {'✅' if config['changenow_api_key'] else '❌'}")
        print(f"   Cloud Tasks Project: {'✅' if config['cloud_tasks_project_id'] else '❌'}")
        print(f"   Cloud Tasks Location: {'✅' if config['cloud_tasks_location'] else '❌'}")
        print(f"   GCAccumulator Response Queue: {'✅' if config['gcaccumulator_response_queue'] else '❌'}")
        print(f"   GCAccumulator URL: {'✅' if config['gcaccumulator_url'] else '❌'}")

        return config
