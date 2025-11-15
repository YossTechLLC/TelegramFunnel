#!/usr/bin/env python
"""
Configuration Manager for GCSplit1-10-26 (Orchestrator Service).
Extends shared ConfigManager with GCSplit1-specific configuration.

Migration Date: 2025-11-15
Extends: _shared/config_manager.ConfigManager
"""
import sys

# Add parent directory to Python path for shared library access
sys.path.insert(0, '/home/user/TelegramFunnel/OCTOBER/10-26')

from _shared.config_manager import ConfigManager as SharedConfigManager


class ConfigManager(SharedConfigManager):
    """
    GCSplit1-specific configuration manager.
    Extends shared ConfigManager with GCSplit1-specific secrets and queues.
    """

    def initialize_config(self) -> dict:
        """
        Initialize and return all configuration values for GCSplit1.

        Extends parent's initialize_config() to add:
        - TPS HostPay signing key
        - TelePay flat fee
        - HostPay webhook URL
        - GCSplit2 queue and URL
        - GCSplit3 queue and URL
        - HostPay queue
        - Cloud Tasks configuration
        - Database credentials

        Returns:
            Dictionary containing all configuration values
        """
        print(f"⚙️ [CONFIG] Initializing GCSplit1-10-26 configuration")

        # Call parent to get base configuration (SUCCESS_URL_SIGNING_KEY)
        config = super().initialize_config()

        # Fetch GCSplit1-specific secrets
        tps_hostpay_signing_key = self.fetch_secret(
            "TPS_HOSTPAY_SIGNING_KEY",
            "TPS HostPay signing key (for GCHostPay tokens)"
        )

        tp_flat_fee = self.fetch_secret(
            "TP_FLAT_FEE",
            "TelePay flat fee percentage"
        )

        hostpay_webhook_url = self.fetch_secret(
            "HOSTPAY_WEBHOOK_URL",
            "GCHostPay webhook URL"
        )

        # Fetch Cloud Tasks configuration using shared method
        cloud_tasks_config = self.fetch_common_cloud_tasks_config()

        # Fetch queue/URL configurations
        gcsplit2_queue = self.fetch_secret(
            "GCSPLIT2_QUEUE",
            "GCSplit2 queue name"
        )

        gcsplit2_url = self.fetch_secret(
            "GCSPLIT2_URL",
            "GCSplit2 service URL"
        )

        gcsplit3_queue = self.fetch_secret(
            "GCSPLIT3_QUEUE",
            "GCSplit3 queue name"
        )

        gcsplit3_url = self.fetch_secret(
            "GCSPLIT3_URL",
            "GCSplit3 service URL"
        )

        hostpay_queue = self.fetch_secret(
            "HOSTPAY_QUEUE",
            "HostPay trigger queue name"
        )

        # Fetch database credentials using shared method
        db_config = self.fetch_common_database_config()

        # Validate critical configurations
        if not tp_flat_fee:
            print(f"⚠️ [CONFIG] Warning: TP_FLAT_FEE not available, will default to 3%")
        if not cloud_tasks_config['cloud_tasks_project_id'] or not cloud_tasks_config['cloud_tasks_location']:
            print(f"⚠️ [CONFIG] Warning: Cloud Tasks configuration incomplete")

        # Merge all configuration
        config.update({
            # GCSplit1-specific secrets
            'tps_hostpay_signing_key': tps_hostpay_signing_key,
            'tp_flat_fee': tp_flat_fee,
            'hostpay_webhook_url': hostpay_webhook_url,

            # Cloud Tasks configuration
            'cloud_tasks_project_id': cloud_tasks_config['cloud_tasks_project_id'],
            'cloud_tasks_location': cloud_tasks_config['cloud_tasks_location'],
            'gcsplit2_queue': gcsplit2_queue,
            'gcsplit2_url': gcsplit2_url,
            'gcsplit3_queue': gcsplit3_queue,
            'gcsplit3_url': gcsplit3_url,
            'hostpay_queue': hostpay_queue,

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
        print(f"   TP_FLAT_FEE: {'✅' if config['tp_flat_fee'] else '❌'}")
        print(f"   HOSTPAY_WEBHOOK_URL: {'✅' if config['hostpay_webhook_url'] else '❌'}")
        print(f"   Cloud Tasks Project: {'✅' if config['cloud_tasks_project_id'] else '❌'}")
        print(f"   Cloud Tasks Location: {'✅' if config['cloud_tasks_location'] else '❌'}")
        print(f"   GCSplit2 Queue: {'✅' if config['gcsplit2_queue'] else '❌'}")
        print(f"   GCSplit2 URL: {'✅' if config['gcsplit2_url'] else '❌'}")
        print(f"   GCSplit3 Queue: {'✅' if config['gcsplit3_queue'] else '❌'}")
        print(f"   GCSplit3 URL: {'✅' if config['gcsplit3_url'] else '❌'}")
        print(f"   HostPay Queue: {'✅' if config['hostpay_queue'] else '❌'}")
        print(f"   CLOUD_SQL_CONNECTION_NAME: {'✅' if config['instance_connection_name'] else '❌'}")
        print(f"   DATABASE_NAME_SECRET: {'✅' if config['db_name'] else '❌'}")
        print(f"   DATABASE_USER_SECRET: {'✅' if config['db_user'] else '❌'}")
        print(f"   DATABASE_PASSWORD_SECRET: {'✅' if config['db_password'] else '❌'}")

        return config
