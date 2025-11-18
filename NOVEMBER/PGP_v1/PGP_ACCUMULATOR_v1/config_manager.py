#!/usr/bin/env python
"""
Configuration Manager for PGP_ACCUMULATOR_v1 (Payment Accumulation Service).
Handles fetching configuration values from Google Cloud Secret Manager.
"""
from PGP_COMMON.config import BaseConfigManager


class ConfigManager(BaseConfigManager):
    """
    Manages configuration and secrets for the PGP_ACCUMULATOR_v1 service.
    Inherits common methods from BaseConfigManager.
    """

    def __init__(self):
        """Initialize the ConfigManager."""
        super().__init__(service_name="PGP_ACCUMULATOR_v1")

    # ========== HOT-RELOADABLE SECRET GETTERS ==========

    def get_flat_fee(self) -> str:
        """Get TP flat fee percentage (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("TP_FLAT_FEE")
        return self.fetch_secret_dynamic(
            secret_path,
            "TP flat fee",
            cache_key="tp_flat_fee"
        ) or "3"

    def get_split2_queue(self) -> str:
        """Get PGP Split2 estimate queue name (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("PGP_SPLIT2_ESTIMATE_QUEUE")
        return self.fetch_secret_dynamic(
            secret_path,
            "PGP Split2 queue",
            cache_key="pgp_split2_queue"
        )

    def get_split2_url(self) -> str:
        """Get PGP Split2 service URL (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("PGP_SPLIT2_URL")
        return self.fetch_secret_dynamic(
            secret_path,
            "PGP Split2 URL",
            cache_key="pgp_split2_url"
        )

    def get_split3_queue(self) -> str:
        """Get PGP Split3 swap queue name (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("PGP_SPLIT3_SWAP_QUEUE")
        return self.fetch_secret_dynamic(
            secret_path,
            "PGP Split3 queue",
            cache_key="pgp_split3_queue"
        )

    def get_split3_url(self) -> str:
        """Get PGP Split3 service URL (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("PGP_SPLIT3_URL")
        return self.fetch_secret_dynamic(
            secret_path,
            "PGP Split3 URL",
            cache_key="pgp_split3_url"
        )

    def get_hostpay1_queue(self) -> str:
        """Get PGP HostPay1 trigger queue name (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("PGP_HOSTPAY_TRIGGER_QUEUE")
        return self.fetch_secret_dynamic(
            secret_path,
            "PGP HostPay1 queue",
            cache_key="pgp_hostpay1_queue"
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

    # ========== INITIALIZATION ==========

    def initialize_config(self) -> dict:
        """
        Initialize and return all configuration values for PGP_ACCUMULATOR_v1.

        Returns:
            Dictionary containing all configuration values
        """
        print(f"⚙️ [CONFIG] Initializing PGP_ACCUMULATOR_v1 configuration")

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
        print(f"   Hot-reloadable secrets: TP_FLAT_FEE, PGP_SPLIT2_*, PGP_SPLIT3_*, PGP_HOSTPAY1_*, HOST_WALLET_USDT_ADDRESS")

        return config
