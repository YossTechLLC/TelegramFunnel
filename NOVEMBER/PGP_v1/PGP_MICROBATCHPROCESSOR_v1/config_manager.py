#!/usr/bin/env python
"""
Configuration Manager for PGP_MICROBATCHPROCESSOR_v1 (Micro-Batch Conversion Service).
Handles fetching configuration values from Google Cloud Secret Manager.
"""
import os
from decimal import Decimal
from typing import Optional
from PGP_COMMON.config import BaseConfigManager


class ConfigManager(BaseConfigManager):
    """
    Manages configuration and secrets for the PGP_MICROBATCHPROCESSOR_v1 service.
    Inherits common methods from BaseConfigManager.
    """

    def __init__(self):
        """Initialize the ConfigManager."""
        super().__init__(service_name="PGP_MICROBATCHPROCESSOR_v1")

    def get_micro_batch_threshold(self) -> Decimal:
        """
        Fetch micro-batch threshold from Google Cloud Secret Manager.

        Returns:
            Decimal threshold value (e.g., Decimal('20.00'))
        """
        try:
            # Try to get from env variable first (for Cloud Run deployment)
            threshold_str = os.getenv('MICRO_BATCH_THRESHOLD_USD')

            if not threshold_str:
                # Fallback to direct Secret Manager access
                project_id = os.getenv('CLOUD_TASKS_PROJECT_ID', 'telepay-459221')
                secret_name = f"projects/{project_id}/secrets/MICRO_BATCH_THRESHOLD_USD/versions/latest"

                print(f"🔐 [CONFIG] Fetching threshold from Secret Manager")
                response = self.client.access_secret_version(request={"name": secret_name})
                threshold_str = response.payload.data.decode('UTF-8')

            threshold = Decimal(threshold_str)
            print(f"✅ [CONFIG] Threshold fetched: ${threshold}")
            return threshold

        except Exception as e:
            print(f"❌ [CONFIG] Failed to fetch threshold: {e}")
            print(f"⚠️ [CONFIG] Using fallback threshold: $20.00")
            return Decimal('20.00')

    def initialize_config(self) -> dict:
        """
        Initialize and return all configuration values for PGP_MICROBATCHPROCESSOR_v1.

        Returns:
            Dictionary containing all configuration values
        """
        print(f"⚙️ [CONFIG] Initializing PGP_MICROBATCHPROCESSOR_v1 configuration")

        # Use base methods to fetch common configurations
        ct_config = self.fetch_cloud_tasks_config()
        db_config = self.fetch_database_config()

        # Fetch signing key for internal communication
        success_url_signing_key = self.fetch_secret(
            "SUCCESS_URL_SIGNING_KEY",
            "Success URL signing key (for token verification and encryption)"
        )

        # PGP HostPay1 batch configuration
        pgp_hostpay1_batch_queue = self.fetch_secret(
            "PGP_HOSTPAY1_BATCH_QUEUE",
            "PGP HostPay1 batch queue name"
        )

        pgp_hostpay1_url = self.fetch_secret(
            "PGP_HOSTPAY1_URL",
            "PGP HostPay1 service URL"
        )

        # ChangeNow API key
        changenow_api_key = self.fetch_secret(
            "CHANGENOW_API_KEY",
            "ChangeNow API key"
        )

        # Host wallet configuration
        host_wallet_usdt_address = self.fetch_secret(
            "HOST_WALLET_USDT_ADDRESS",
            "Host USDT wallet address"
        )

        # Fetch micro-batch threshold (service-specific method)
        threshold = self.get_micro_batch_threshold()

        # Validate critical configurations
        if not success_url_signing_key:
            print(f"⚠️ [CONFIG] Warning: SUCCESS_URL_SIGNING_KEY not available")
        if not ct_config['cloud_tasks_project_id'] or not ct_config['cloud_tasks_location']:
            print(f"⚠️ [CONFIG] Warning: Cloud Tasks configuration incomplete")

        # Combine all configurations
        config = {
            # Signing key
            'success_url_signing_key': success_url_signing_key,

            # Threshold configuration
            'micro_batch_threshold': threshold,

            # Cloud Tasks configuration (from base method)
            **ct_config,

            # Service-specific queues and URLs
            'pgp_hostpay1_batch_queue': pgp_hostpay1_batch_queue,
            'pgp_hostpay1_url': pgp_hostpay1_url,

            # ChangeNow configuration
            'changenow_api_key': changenow_api_key,

            # Wallet configuration
            'host_wallet_usdt_address': host_wallet_usdt_address,

            # Database configuration (from base method)
            **db_config
        }

        # Log configuration status
        print(f"📊 [CONFIG] Configuration status:")
        print(f"   SUCCESS_URL_SIGNING_KEY: {'✅' if config['success_url_signing_key'] else '❌'}")
        print(f"   Micro-Batch Threshold: {'✅' if config['micro_batch_threshold'] else '❌'} (${config['micro_batch_threshold']})")
        print(f"   Cloud Tasks Project: {'✅' if config['cloud_tasks_project_id'] else '❌'}")
        print(f"   Cloud Tasks Location: {'✅' if config['cloud_tasks_location'] else '❌'}")
        print(f"   PGP HostPay1 Batch Queue: {'✅' if config['pgp_hostpay1_batch_queue'] else '❌'}")
        print(f"   PGP HostPay1 URL: {'✅' if config['pgp_hostpay1_url'] else '❌'}")
        print(f"   ChangeNow API Key: {'✅' if config['changenow_api_key'] else '❌'}")
        print(f"   Host USDT Wallet: {'✅' if config['host_wallet_usdt_address'] else '❌'}")
        print(f"   CLOUD_SQL_CONNECTION_NAME: {'✅' if config['instance_connection_name'] else '❌'}")
        print(f"   DATABASE_NAME_SECRET: {'✅' if config['db_name'] else '❌'}")
        print(f"   DATABASE_USER_SECRET: {'✅' if config['db_user'] else '❌'}")
        print(f"   DATABASE_PASSWORD_SECRET: {'✅' if config['db_password'] else '❌'}")

        return config
