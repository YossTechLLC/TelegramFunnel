#!/usr/bin/env python
"""
Configuration Manager for GCHostPay2-10-26 (ChangeNow Status Checker Service).
Extends shared ConfigManager with GCHostPay2-specific configuration.

Migration Date: 2025-11-15
Extends: _shared/config_manager.ConfigManager
"""
import sys

# Add parent directory to Python path for shared library access
sys.path.insert(0, '/home/user/TelegramFunnel/OCTOBER/10-26')

from _shared.config_manager import ConfigManager as SharedConfigManager


class ConfigManager(SharedConfigManager):
    """
    GCHostPay2-specific configuration manager.
    Extends shared ConfigManager with ChangeNOW status checking configuration.
    """

    def initialize_config(self) -> dict:
        """
        Initialize and return all configuration values for GCHostPay2.

        Extends parent's initialize_config() to add:
        - ChangeNOW API key
        - Cloud Tasks configuration
        - GCHostPay3 queue and URL (Payment Executor)

        Returns:
            Dictionary containing all configuration values
        """
        print(f"⚙️ [CONFIG] Initializing GCHostPay2-10-26 configuration")

        # Call parent to get base configuration (SUCCESS_URL_SIGNING_KEY)
        config = super().initialize_config()

        # Fetch GCHostPay2-specific secrets
        changenow_api_key = self.fetch_secret(
            "CHANGENOW_API_KEY",
            "ChangeNow API key"
        )

        # Fetch Cloud Tasks configuration using shared method
        cloud_tasks_config = self.fetch_common_cloud_tasks_config()

        # Get GCHostPay3 (Payment Executor) configuration
        gchostpay3_queue = self.fetch_secret(
            "GCHOSTPAY3_QUEUE",
            "GCHostPay3 queue name"
        )

        gchostpay3_url = self.fetch_secret(
            "GCHOSTPAY3_URL",
            "GCHostPay3 service URL"
        )

        # Validate critical configurations
        if not changenow_api_key:
            print(f"⚠️ [CONFIG] Warning: CHANGENOW_API_KEY not available")
        if not cloud_tasks_config['cloud_tasks_project_id'] or not cloud_tasks_config['cloud_tasks_location']:
            print(f"⚠️ [CONFIG] Warning: Cloud Tasks configuration incomplete")

        # Merge all configuration
        config.update({
            # GCHostPay2-specific secrets
            'changenow_api_key': changenow_api_key,

            # Cloud Tasks configuration
            'cloud_tasks_project_id': cloud_tasks_config['cloud_tasks_project_id'],
            'cloud_tasks_location': cloud_tasks_config['cloud_tasks_location'],
            'gchostpay3_queue': gchostpay3_queue,
            'gchostpay3_url': gchostpay3_url
        })

        # Log configuration status
        print(f"📊 [CONFIG] Configuration status:")
        print(f"   SUCCESS_URL_SIGNING_KEY: {'✅' if config['success_url_signing_key'] else '❌'}")
        print(f"   CHANGENOW_API_KEY: {'✅' if config['changenow_api_key'] else '❌'}")
        print(f"   Cloud Tasks Project: {'✅' if config['cloud_tasks_project_id'] else '❌'}")
        print(f"   Cloud Tasks Location: {'✅' if config['cloud_tasks_location'] else '❌'}")
        print(f"   GCHostPay3 Queue: {'✅' if config['gchostpay3_queue'] else '❌'}")
        print(f"   GCHostPay3 URL: {'✅' if config['gchostpay3_url'] else '❌'}")

        return config
