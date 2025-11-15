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

    def initialize_config(self) -> dict:
        """
        Initialize and return all configuration values for PGP_HOSTPAY2_v1.

        Returns:
            Dictionary containing all configuration values
        """
        print(f"⚙️ [CONFIG] Initializing PGP_HOSTPAY2_v1 configuration")

        # Use base methods to fetch common configurations
        ct_config = self.fetch_cloud_tasks_config()

        # Fetch signing key for internal communication
        success_url_signing_key = self.fetch_secret(
            "SUCCESS_URL_SIGNING_KEY",
            "Success URL signing key (for internal PGP HostPay communication)"
        )

        # Fetch ChangeNow API key
        changenow_api_key = self.fetch_secret(
            "CHANGENOW_API_KEY",
            "ChangeNow API key"
        )

        # Get PGP HostPay1 response queue configuration
        pgp_hostpay1_response_queue = self.fetch_secret(
            "PGP_HOSTPAY1_RESPONSE_QUEUE",
            "PGP HostPay1 response queue name"
        )

        pgp_hostpay1_url = self.fetch_secret(
            "PGP_HOSTPAY1_URL",
            "PGP HostPay1 service URL"
        )

        # Validate critical configurations
        if not success_url_signing_key:
            print(f"⚠️ [CONFIG] Warning: SUCCESS_URL_SIGNING_KEY not available")
        if not changenow_api_key:
            print(f"⚠️ [CONFIG] Warning: CHANGENOW_API_KEY not available")
        if not ct_config['cloud_tasks_project_id'] or not ct_config['cloud_tasks_location']:
            print(f"⚠️ [CONFIG] Warning: Cloud Tasks configuration incomplete")

        # Combine all configurations
        config = {
            # Signing key
            'success_url_signing_key': success_url_signing_key,

            # ChangeNow API
            'changenow_api_key': changenow_api_key,

            # Cloud Tasks configuration (from base method)
            **ct_config,

            # Service-specific queues and URLs
            'pgp_hostpay1_response_queue': pgp_hostpay1_response_queue,
            'pgp_hostpay1_url': pgp_hostpay1_url
        }

        # Log configuration status
        print(f"📊 [CONFIG] Configuration status:")
        print(f"   SUCCESS_URL_SIGNING_KEY: {'✅' if config['success_url_signing_key'] else '❌'}")
        print(f"   CHANGENOW_API_KEY: {'✅' if config['changenow_api_key'] else '❌'}")
        print(f"   Cloud Tasks Project: {'✅' if config['cloud_tasks_project_id'] else '❌'}")
        print(f"   Cloud Tasks Location: {'✅' if config['cloud_tasks_location'] else '❌'}")
        print(f"   PGP HostPay1 Response Queue: {'✅' if config['pgp_hostpay1_response_queue'] else '❌'}")
        print(f"   PGP HostPay1 URL: {'✅' if config['pgp_hostpay1_url'] else '❌'}")

        return config
