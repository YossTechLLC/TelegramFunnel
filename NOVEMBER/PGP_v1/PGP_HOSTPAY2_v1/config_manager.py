#!/usr/bin/env python
"""
Configuration Manager for PGP_HOSTPAY2_v1 (ChangeNow Status Checker Service).
Handles fetching configuration values from Google Cloud Secret Manager.
"""
from PGP_COMMON.config import BaseConfigManager


class ConfigManager(BaseConfigManager):
    """
    Manages configuration and secrets for the PGP_HOSTPAY2_v1 service.
    Inherits common methods from BaseConfigManager.
    """

    def __init__(self):
        """Initialize the ConfigManager."""
        super().__init__(service_name="PGP_HOSTPAY2_v1")

    # ========== HOT-RELOADABLE SECRET GETTERS ==========

    def get_changenow_api_key(self) -> str:
        """Get ChangeNow API key (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("CHANGENOW_API_KEY")
        return self.fetch_secret_dynamic(
            secret_path,
            "ChangeNow API key",
            cache_key="changenow_api_key"
        )

    def get_hostpay1_response_queue(self) -> str:
        """Get PGP HostPay1 response queue name (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("PGP_HOSTPAY1_RESPONSE_QUEUE")
        return self.fetch_secret_dynamic(
            secret_path,
            "PGP HostPay1 response queue",
            cache_key="pgp_hostpay1_response_queue"
        )

    def get_hostpay1_url(self) -> str:
        """Get PGP HostPay1 service URL (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("PGP_HOSTPAY1_URL")
        return self.fetch_secret_dynamic(
            secret_path,
            "PGP HostPay1 URL",
            cache_key="pgp_hostpay1_url"
        )

    # ========== INITIALIZATION ==========

    def initialize_config(self) -> dict:
        """
        Initialize and return all configuration values for PGP_HOSTPAY2_v1.

        Returns:
            Dictionary containing all configuration values
        """
        print(f"⚙️ [CONFIG] Initializing PGP_HOSTPAY2_v1 configuration")

        # Use base methods to fetch common configurations
        ct_config = self.fetch_cloud_tasks_config()

        # Fetch STATIC signing key (security-critical)
        success_url_signing_key = self.fetch_secret(
            "SUCCESS_URL_SIGNING_KEY",
            "Success URL signing key (for internal PGP HostPay communication) - STATIC"
        )

        # Validate critical configurations
        if not success_url_signing_key:
            print(f"⚠️ [CONFIG] Warning: SUCCESS_URL_SIGNING_KEY not available")
        if not ct_config['cloud_tasks_project_id'] or not ct_config['cloud_tasks_location']:
            print(f"⚠️ [CONFIG] Warning: Cloud Tasks configuration incomplete")

        # Combine all configurations
        # Note: Hot-reloadable secrets are NOT fetched here - they are fetched on-demand via getter methods
        config = {
            # STATIC Signing key (loaded once at startup)
            'success_url_signing_key': success_url_signing_key,

            # Cloud Tasks configuration (from base method)
            **ct_config
        }

        # Log configuration status
        print(f"📊 [CONFIG] Configuration status:")
        print(f"   SUCCESS_URL_SIGNING_KEY (static): {'✅' if config['success_url_signing_key'] else '❌'}")
        print(f"   Cloud Tasks Project: {'✅' if config['cloud_tasks_project_id'] else '❌'}")
        print(f"   Cloud Tasks Location: {'✅' if config['cloud_tasks_location'] else '❌'}")
        print(f"   Hot-reloadable secrets: CHANGENOW_API_KEY, PGP_HOSTPAY1_RESPONSE_QUEUE, PGP_HOSTPAY1_URL")

        return config
