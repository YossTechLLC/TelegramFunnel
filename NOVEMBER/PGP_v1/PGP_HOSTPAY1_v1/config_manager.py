#!/usr/bin/env python
"""
Configuration Manager for PGP_HOSTPAY1_v1 (Validator & Orchestrator Service).
Handles fetching configuration values from Google Cloud Secret Manager.
"""
from PGP_COMMON.config import BaseConfigManager


class ConfigManager(BaseConfigManager):
    """
    Manages configuration and secrets for the PGP_HOSTPAY1_v1 service.
    Inherits common methods from BaseConfigManager.
    """

    def __init__(self):
        """Initialize the ConfigManager."""
        super().__init__(service_name="PGP_HOSTPAY1_v1")

    # ========== HOT-RELOADABLE SECRET GETTERS ==========

    def get_changenow_api_key(self) -> str:
        """Get ChangeNow API key (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("CHANGENOW_API_KEY")
        return self.fetch_secret_dynamic(
            secret_path,
            "ChangeNow API key",
            cache_key="changenow_api_key"
        )

    def get_pgp_hostpay1_url(self) -> str:
        """Get PGP HostPay1 service URL (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("PGP_HOSTPAY1_URL")
        return self.fetch_secret_dynamic(
            secret_path,
            "PGP HostPay1 URL",
            cache_key="pgp_hostpay1_url"
        )

    def get_pgp_hostpay1_response_queue(self) -> str:
        """Get PGP HostPay1 response queue name (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("PGP_HOSTPAY1_RESPONSE_QUEUE")
        return self.fetch_secret_dynamic(
            secret_path,
            "PGP HostPay1 response queue",
            cache_key="pgp_hostpay1_response_queue"
        )

    def get_pgp_hostpay2_queue(self) -> str:
        """Get PGP HostPay2 status queue name (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("PGP_HOSTPAY2_STATUS_QUEUE")
        return self.fetch_secret_dynamic(
            secret_path,
            "PGP HostPay2 status queue",
            cache_key="pgp_hostpay2_queue"
        )

    def get_pgp_hostpay2_url(self) -> str:
        """Get PGP HostPay2 service URL (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("PGP_HOSTPAY2_URL")
        return self.fetch_secret_dynamic(
            secret_path,
            "PGP HostPay2 URL",
            cache_key="pgp_hostpay2_url"
        )

    def get_pgp_hostpay3_queue(self) -> str:
        """Get PGP HostPay3 payment queue name (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("PGP_HOSTPAY3_PAYMENT_QUEUE")
        return self.fetch_secret_dynamic(
            secret_path,
            "PGP HostPay3 payment queue",
            cache_key="pgp_hostpay3_queue"
        )

    def get_pgp_hostpay3_url(self) -> str:
        """Get PGP HostPay3 service URL (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("PGP_HOSTPAY3_URL")
        return self.fetch_secret_dynamic(
            secret_path,
            "PGP HostPay3 URL",
            cache_key="pgp_hostpay3_url"
        )

    def get_pgp_microbatch_response_queue(self) -> str:
        """Get PGP MicroBatch response queue name (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("PGP_MICROBATCH_RESPONSE_QUEUE")
        return self.fetch_secret_dynamic(
            secret_path,
            "PGP MicroBatch response queue",
            cache_key="pgp_microbatch_response_queue"
        )

    def get_pgp_microbatch_url(self) -> str:
        """Get PGP MicroBatch service URL (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("PGP_MICROBATCH_URL")
        return self.fetch_secret_dynamic(
            secret_path,
            "PGP MicroBatch URL",
            cache_key="pgp_microbatch_url"
        )

    # ========== INITIALIZATION ==========

    def initialize_config(self) -> dict:
        """
        Initialize and return all configuration values for PGP_HOSTPAY1_v1.

        Returns:
            Dictionary containing all configuration values
        """
        print(f"⚙️ [CONFIG] Initializing PGP_HOSTPAY1_v1 configuration")

        # Use base methods to fetch common configurations
        ct_config = self.fetch_cloud_tasks_config()
        db_config = self.fetch_database_config()

        # Fetch STATIC signing keys (security-critical)
        tps_hostpay_signing_key = self.fetch_secret(
            "TPS_HOSTPAY_SIGNING_KEY",
            "TPS HostPay signing key (for PGP_SPLIT1_v1 → PGP_HOSTPAY1_v1) - STATIC"
        )

        success_url_signing_key = self.fetch_secret(
            "SUCCESS_URL_SIGNING_KEY",
            "Success URL signing key (for internal PGP HostPay communication) - STATIC"
        )

        # Validate critical configurations
        if not tps_hostpay_signing_key or not success_url_signing_key:
            print(f"⚠️ [CONFIG] Warning: Signing keys not available")
        if not ct_config['cloud_tasks_project_id'] or not ct_config['cloud_tasks_location']:
            print(f"⚠️ [CONFIG] Warning: Cloud Tasks configuration incomplete")

        # Combine all configurations
        # Note: Hot-reloadable secrets are NOT fetched here - they are fetched on-demand via getter methods
        config = {
            # STATIC Signing keys (loaded once at startup)
            'tps_hostpay_signing_key': tps_hostpay_signing_key,
            'success_url_signing_key': success_url_signing_key,

            # Cloud Tasks configuration (from base method)
            **ct_config,

            # Database configuration (from base method)
            **db_config
        }

        # Log configuration status
        print(f"📊 [CONFIG] Configuration status:")
        print(f"   TPS_HOSTPAY_SIGNING_KEY (static): {'✅' if config['tps_hostpay_signing_key'] else '❌'}")
        print(f"   SUCCESS_URL_SIGNING_KEY (static): {'✅' if config['success_url_signing_key'] else '❌'}")
        print(f"   Cloud Tasks Project: {'✅' if config['cloud_tasks_project_id'] else '❌'}")
        print(f"   Cloud Tasks Location: {'✅' if config['cloud_tasks_location'] else '❌'}")
        print(f"   CLOUD_SQL_CONNECTION_NAME: {'✅' if config['instance_connection_name'] else '❌'}")
        print(f"   DATABASE_NAME_SECRET: {'✅' if config['db_name'] else '❌'}")
        print(f"   DATABASE_USER_SECRET: {'✅' if config['db_user'] else '❌'}")
        print(f"   DATABASE_PASSWORD_SECRET: {'✅' if config['db_password'] else '❌'}")
        print(f"   Hot-reloadable secrets: CHANGENOW_API_KEY, PGP_HOSTPAY1/2/3_URLs, PGP_HOSTPAY1/2/3_QUEUEs, PGP_MICROBATCH_URL/QUEUE")

        return config
