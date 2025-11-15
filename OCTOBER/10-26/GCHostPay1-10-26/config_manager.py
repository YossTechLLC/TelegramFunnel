#!/usr/bin/env python
"""
Configuration Manager for GCHostPay1-10-26 (Validator & Orchestrator Service).
Extends shared ConfigManager with GCHostPay1-specific configuration.

Migration Date: 2025-11-15
Extends: _shared/config_manager.ConfigManager
"""
import sys

# Add parent directory to Python path for shared library access
sys.path.insert(0, '/home/user/TelegramFunnel/OCTOBER/10-26')

from _shared.config_manager import ConfigManager as SharedConfigManager


class ConfigManager(SharedConfigManager):
    """
    GCHostPay1-specific configuration manager.
    Extends shared ConfigManager with host payout orchestration configuration.
    """

    def initialize_config(self) -> dict:
        """
        Initialize and return all configuration values for GCHostPay1.

        Extends parent's initialize_config() to add:
        - TPS HostPay signing key
        - ChangeNOW API key
        - Cloud Tasks configuration
        - GCHostPay2 queue and URL (Status Checker)
        - GCHostPay3 queue and URL (Payment Executor)
        - GCHostPay1 response queue (Self retry)
        - Database credentials

        Returns:
            Dictionary containing all configuration values
        """
        print(f"⚙️ [CONFIG] Initializing GCHostPay1-10-26 configuration")

        # Call parent to get base configuration (SUCCESS_URL_SIGNING_KEY)
        config = super().initialize_config()

        # Fetch GCHostPay1-specific secrets
        tps_hostpay_signing_key = self.fetch_secret(
            "TPS_HOSTPAY_SIGNING_KEY",
            "TPS HostPay signing key (for GCSplit1 → GCHostPay1)"
        )

        changenow_api_key = self.fetch_secret(
            "CHANGENOW_API_KEY",
            "ChangeNow API key"
        )

        # Fetch Cloud Tasks configuration using shared method
        cloud_tasks_config = self.fetch_common_cloud_tasks_config()

        # Get GCHostPay2 (Status Checker) configuration
        gchostpay2_queue = self.fetch_secret(
            "GCHOSTPAY2_QUEUE",
            "GCHostPay2 queue name"
        )

        gchostpay2_url = self.fetch_secret(
            "GCHOSTPAY2_URL",
            "GCHostPay2 service URL"
        )

        # Get GCHostPay3 (Payment Executor) configuration
        gchostpay3_queue = self.fetch_secret(
            "GCHOSTPAY3_QUEUE",
            "GCHostPay3 queue name"
        )

        gchostpay3_url = self.fetch_secret(
            "GCHOSTPAY3_URL",
            "GCHostPay3 service URL"
        )

        # Get GCHostPay1 (Self) configuration for retry callbacks
        gchostpay1_response_queue = self.fetch_secret(
            "GCHOSTPAY1_RESPONSE_QUEUE",
            "GCHostPay1 response queue name (self retry)"
        )

        # Fetch database credentials using shared method
        db_config = self.fetch_common_database_config()

        # Validate critical configurations
        if not tps_hostpay_signing_key:
            print(f"⚠️ [CONFIG] Warning: TPS_HOSTPAY_SIGNING_KEY not available")
        if not changenow_api_key:
            print(f"⚠️ [CONFIG] Warning: CHANGENOW_API_KEY not available")
        if not cloud_tasks_config['cloud_tasks_project_id'] or not cloud_tasks_config['cloud_tasks_location']:
            print(f"⚠️ [CONFIG] Warning: Cloud Tasks configuration incomplete")

        # Merge all configuration
        config.update({
            # GCHostPay1-specific secrets
            'tps_hostpay_signing_key': tps_hostpay_signing_key,
            'changenow_api_key': changenow_api_key,

            # Cloud Tasks configuration
            'cloud_tasks_project_id': cloud_tasks_config['cloud_tasks_project_id'],
            'cloud_tasks_location': cloud_tasks_config['cloud_tasks_location'],
            'gchostpay2_queue': gchostpay2_queue,
            'gchostpay2_url': gchostpay2_url,
            'gchostpay3_queue': gchostpay3_queue,
            'gchostpay3_url': gchostpay3_url,
            'gchostpay1_response_queue': gchostpay1_response_queue,

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
        print(f"   CHANGENOW_API_KEY: {'✅' if config['changenow_api_key'] else '❌'}")
        print(f"   Cloud Tasks Project: {'✅' if config['cloud_tasks_project_id'] else '❌'}")
        print(f"   Cloud Tasks Location: {'✅' if config['cloud_tasks_location'] else '❌'}")
        print(f"   GCHostPay2 Queue: {'✅' if config['gchostpay2_queue'] else '❌'}")
        print(f"   GCHostPay2 URL: {'✅' if config['gchostpay2_url'] else '❌'}")
        print(f"   GCHostPay3 Queue: {'✅' if config['gchostpay3_queue'] else '❌'}")
        print(f"   GCHostPay3 URL: {'✅' if config['gchostpay3_url'] else '❌'}")
        print(f"   GCHostPay1 Response Queue: {'✅' if config['gchostpay1_response_queue'] else '❌'}")
        print(f"   Database: {'✅' if all([config['instance_connection_name'], config['db_name'], config['db_user'], config['db_password']]) else '❌'}")

        return config
