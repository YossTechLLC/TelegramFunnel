#!/usr/bin/env python
"""
Configuration Manager for GCSplit2-10-26 (USDT→ETH Estimator Service).
Extends shared ConfigManager with GCSplit2-specific configuration.

Migration Date: 2025-11-15
Extends: _shared/config_manager.ConfigManager
"""
import sys

# Add parent directory to Python path for shared library access
sys.path.insert(0, '/home/user/TelegramFunnel/OCTOBER/10-26')

from _shared.config_manager import ConfigManager as SharedConfigManager


class ConfigManager(SharedConfigManager):
    """
    GCSplit2-specific configuration manager.
    Extends shared ConfigManager with ChangeNOW API and GCSplit3 queue configuration.
    """

    def initialize_config(self) -> dict:
        """
        Initialize and return all configuration values for GCSplit2.

        Extends parent's initialize_config() to add:
        - ChangeNOW API key
        - Cloud Tasks configuration
        - GCSplit3 queue and URL
        - Database credentials

        Returns:
            Dictionary containing all configuration values
        """
        print(f"⚙️ [CONFIG] Initializing GCSplit2-10-26 configuration")

        # Call parent to get base configuration (SUCCESS_URL_SIGNING_KEY)
        config = super().initialize_config()

        # Fetch GCSplit2-specific secrets
        changenow_api_key = self.fetch_secret(
            "CHANGENOW_API_KEY",
            "ChangeNow API key"
        )

        # Fetch Cloud Tasks configuration using shared method
        cloud_tasks_config = self.fetch_common_cloud_tasks_config()

        # Fetch queue/URL configurations
        gcsplit1_response_queue = self.fetch_secret(
            "GCSPLIT2_RESPONSE_QUEUE",
            "GCSplit1 response queue name (GCSplit2 → GCSplit1)"
        )

        gcsplit1_url = self.fetch_secret(
            "GCSPLIT1_ESTIMATE_RESPONSE_URL",
            "GCSplit1 /usdt-eth-estimate endpoint URL"
        )

        # GCBatchProcessor configuration (for threshold checking)
        gcbatchprocessor_queue = self.fetch_secret(
            "GCBATCHPROCESSOR_QUEUE",
            "GCBatchProcessor queue name"
        )

        gcbatchprocessor_url = self.fetch_secret(
            "GCBATCHPROCESSOR_URL",
            "GCBatchProcessor service URL"
        )

        # Fetch database credentials using shared method
        db_config = self.fetch_common_database_config()

        # Validate critical configurations
        if not changenow_api_key:
            print(f"⚠️ [CONFIG] Warning: CHANGENOW_API_KEY not available")
        if not cloud_tasks_config['cloud_tasks_project_id'] or not cloud_tasks_config['cloud_tasks_location']:
            print(f"⚠️ [CONFIG] Warning: Cloud Tasks configuration incomplete")

        # Merge all configuration
        config.update({
            # GCSplit2-specific secrets
            'changenow_api_key': changenow_api_key,

            # Cloud Tasks configuration
            'cloud_tasks_project_id': cloud_tasks_config['cloud_tasks_project_id'],
            'cloud_tasks_location': cloud_tasks_config['cloud_tasks_location'],
            'gcsplit1_response_queue': gcsplit1_response_queue,
            'gcsplit1_url': gcsplit1_url,
            'gcbatchprocessor_queue': gcbatchprocessor_queue,
            'gcbatchprocessor_url': gcbatchprocessor_url,

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
        print(f"   Cloud Tasks Project: {'✅' if config['cloud_tasks_project_id'] else '❌'}")
        print(f"   Cloud Tasks Location: {'✅' if config['cloud_tasks_location'] else '❌'}")
        print(f"   GCSplit1 Response Queue: {'✅' if config['gcsplit1_response_queue'] else '❌'}")
        print(f"   GCSplit1 URL: {'✅' if config['gcsplit1_url'] else '❌'}")

        return config
