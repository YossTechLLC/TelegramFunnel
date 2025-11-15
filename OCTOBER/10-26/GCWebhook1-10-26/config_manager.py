#!/usr/bin/env python
"""
Configuration Manager for GCWebhook1-10-26 (Payment Processor Service).
Extends shared ConfigManager with GCWebhook1-specific configuration.

Migration Date: 2025-11-15
Extends: _shared/config_manager.ConfigManager
"""
import os
import sys

# Add parent directory to Python path for shared library access
sys.path.insert(0, '/home/user/TelegramFunnel/OCTOBER/10-26')

from _shared.config_manager import ConfigManager as SharedConfigManager


class ConfigManager(SharedConfigManager):
    """
    GCWebhook1-specific configuration manager.
    Extends shared ConfigManager with Cloud Tasks queue/URL configuration.
    """

    def initialize_config(self) -> dict:
        """
        Initialize and return all configuration values for GCWebhook1.

        Extends parent's initialize_config() to add:
        - Cloud Tasks project/location configuration
        - GCWebhook2 queue and URL
        - GCSplit1 queue and URL
        - GCAccumulator queue and URL
        - Database credentials

        Returns:
            Dictionary containing all configuration values
        """
        print(f"⚙️ [CONFIG] Initializing GCWebhook1-10-26 configuration")

        # Call parent to get base configuration (SUCCESS_URL_SIGNING_KEY)
        config = super().initialize_config()

        # Fetch Cloud Tasks configuration using shared method
        cloud_tasks_config = self.fetch_common_cloud_tasks_config()

        # Fetch service-specific queue/URL configurations
        gcwebhook2_queue = self.fetch_secret(
            "GCWEBHOOK2_QUEUE",
            "GCWebhook2 queue name"
        )

        gcwebhook2_url = self.fetch_secret(
            "GCWEBHOOK2_URL",
            "GCWebhook2 service URL"
        )

        gcsplit1_queue = self.fetch_secret(
            "GCSPLIT1_QUEUE",
            "GCSplit1 queue name"
        )

        gcsplit1_url = self.fetch_secret(
            "GCSPLIT1_URL",
            "GCSplit1 service URL"
        )

        # GCAccumulator configuration (for threshold payout)
        gcaccumulator_queue = self.fetch_secret(
            "GCACCUMULATOR_QUEUE",
            "GCAccumulator queue name"
        )

        gcaccumulator_url = self.fetch_secret(
            "GCACCUMULATOR_URL",
            "GCAccumulator service URL"
        )

        # Fetch database credentials using shared method
        db_config = self.fetch_common_database_config()

        # Validate critical configurations
        if not cloud_tasks_config['cloud_tasks_project_id'] or not cloud_tasks_config['cloud_tasks_location']:
            print(f"⚠️ [CONFIG] Warning: Cloud Tasks configuration incomplete")

        # Merge all configuration
        config.update({
            # Cloud Tasks configuration
            'cloud_tasks_project_id': cloud_tasks_config['cloud_tasks_project_id'],
            'cloud_tasks_location': cloud_tasks_config['cloud_tasks_location'],
            'gcwebhook2_queue': gcwebhook2_queue,
            'gcwebhook2_url': gcwebhook2_url,
            'gcsplit1_queue': gcsplit1_queue,
            'gcsplit1_url': gcsplit1_url,
            'gcaccumulator_queue': gcaccumulator_queue,
            'gcaccumulator_url': gcaccumulator_url,

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
        print(f"   GCWebhook2 Queue: {'✅' if config['gcwebhook2_queue'] else '❌'}")
        print(f"   GCWebhook2 URL: {'✅' if config['gcwebhook2_url'] else '❌'}")
        print(f"   GCSplit1 Queue: {'✅' if config['gcsplit1_queue'] else '❌'}")
        print(f"   GCSplit1 URL: {'✅' if config['gcsplit1_url'] else '❌'}")
        print(f"   GCAccumulator Queue: {'✅' if config['gcaccumulator_queue'] else '❌'}")
        print(f"   GCAccumulator URL: {'✅' if config['gcaccumulator_url'] else '❌'}")
        print(f"   CLOUD_SQL_CONNECTION_NAME: {'✅' if config['instance_connection_name'] else '❌'}")
        print(f"   DATABASE_NAME_SECRET: {'✅' if config['db_name'] else '❌'}")
        print(f"   DATABASE_USER_SECRET: {'✅' if config['db_user'] else '❌'}")
        print(f"   DATABASE_PASSWORD_SECRET: {'✅' if config['db_password'] else '❌'}")

        return config
