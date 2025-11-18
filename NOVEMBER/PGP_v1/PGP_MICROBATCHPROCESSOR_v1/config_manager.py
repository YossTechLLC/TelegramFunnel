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

    # ========== HOT-RELOADABLE SECRET GETTERS ==========

    def get_changenow_api_key(self) -> str:
        """Get ChangeNow API key (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("CHANGENOW_API_KEY")
        return self.fetch_secret_dynamic(
            secret_path,
            "ChangeNow API key",
            cache_key="changenow_api_key"
        )

    def get_hostpay1_batch_queue(self) -> str:
        """Get PGP HostPay1 batch queue name (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("PGP_HOSTPAY1_BATCH_QUEUE")
        return self.fetch_secret_dynamic(
            secret_path,
            "PGP HostPay1 batch queue",
            cache_key="pgp_hostpay1_batch_queue"
        )

    def get_hostpay1_url(self) -> str:
        """Get PGP HostPay1 service URL (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("PGP_HOSTPAY1_URL")
        return self.fetch_secret_dynamic(
            secret_path,
            "PGP HostPay1 URL",
            cache_key="pgp_hostpay1_url"
        )

    def get_host_wallet_usdt_address(self) -> str:
        """Get host USDT wallet address (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("HOST_WALLET_USDT_ADDRESS")
        return self.fetch_secret_dynamic(
            secret_path,
            "Host USDT wallet address",
            cache_key="host_wallet_usdt_address"
        )

    def get_micro_batch_threshold_dynamic(self) -> Decimal:
        """Get micro-batch threshold (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("MICRO_BATCH_THRESHOLD_USD")
        threshold_str = self.fetch_secret_dynamic(
            secret_path,
            "Micro-batch threshold USD",
            cache_key="micro_batch_threshold"
        ) or "20.00"
        try:
            return Decimal(threshold_str)
        except (ValueError, TypeError):
            print(f"⚠️ [CONFIG] Invalid threshold value, using default: 20.00")
            return Decimal('20.00')

    # ========== DEPRECATED METHOD (kept for backward compatibility) ==========

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

        # Fetch STATIC signing key (security-critical)
        success_url_signing_key = self.fetch_secret(
            "SUCCESS_URL_SIGNING_KEY",
            "Success URL signing key (for token verification and encryption) - STATIC"
        )

        # Validate critical configurations
        if not success_url_signing_key:
            print(f"⚠️ [CONFIG] Warning: SUCCESS_URL_SIGNING_KEY not available")
        if not ct_config['cloud_tasks_project_id'] or not ct_config['cloud_tasks_location']:
            print(f"⚠️ [CONFIG] Warning: Cloud Tasks configuration incomplete")

        # Combine all configurations
        # Note: Hot-reloadable secrets are NOT fetched here - they are fetched on-demand via getter methods
        config = {
            # STATIC Signing key
            'success_url_signing_key': success_url_signing_key,

            # Cloud Tasks configuration (from base method)
            **ct_config,

            # Database configuration (from base method)
            **db_config
        }

        # Log configuration status
        print(f"📊 [CONFIG] Configuration status:")
        print(f"   SUCCESS_URL_SIGNING_KEY (static): {'✅' if config['success_url_signing_key'] else '❌'}")
        print(f"   Cloud Tasks Project: {'✅' if config['cloud_tasks_project_id'] else '❌'}")
        print(f"   Cloud Tasks Location: {'✅' if config['cloud_tasks_location'] else '❌'}")
        print(f"   CLOUD_SQL_CONNECTION_NAME: {'✅' if config['instance_connection_name'] else '❌'}")
        print(f"   DATABASE_NAME_SECRET: {'✅' if config['db_name'] else '❌'}")
        print(f"   DATABASE_USER_SECRET: {'✅' if config['db_user'] else '❌'}")
        print(f"   DATABASE_PASSWORD_SECRET: {'✅' if config['db_password'] else '❌'}")
        print(f"   Hot-reloadable secrets: CHANGENOW_API_KEY, PGP_HOSTPAY1_*, HOST_WALLET_USDT_ADDRESS, MICRO_BATCH_THRESHOLD_USD")

        return config
