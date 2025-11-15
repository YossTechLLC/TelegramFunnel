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

        # Fetch signing keys
        tps_hostpay_signing_key = self.fetch_secret(
            "TPS_HOSTPAY_SIGNING_KEY",
            "TPS HostPay signing key (for PGP_SPLIT1_v1 → PGP_HOSTPAY1_v1)"
        )

        success_url_signing_key = self.fetch_secret(
            "SUCCESS_URL_SIGNING_KEY",
            "Success URL signing key (for internal PGP HostPay communication)"
        )

        # Get PGP HostPay2 (Status Checker) configuration
        pgp_hostpay2_queue = self.fetch_secret(
            "PGP_HOSTPAY2_STATUS_QUEUE",
            "PGP HostPay2 status queue name"
        )

        pgp_hostpay2_url = self.fetch_secret(
            "PGP_HOSTPAY2_URL",
            "PGP HostPay2 service URL"
        )

        # Get PGP HostPay3 (Payment Executor) configuration
        pgp_hostpay3_queue = self.fetch_secret(
            "PGP_HOSTPAY3_PAYMENT_QUEUE",
            "PGP HostPay3 payment queue name"
        )

        pgp_hostpay3_url = self.fetch_secret(
            "PGP_HOSTPAY3_URL",
            "PGP HostPay3 service URL"
        )

        # Get PGP HostPay1 (Self) configuration for retry callbacks
        pgp_hostpay1_url = self.fetch_secret(
            "PGP_HOSTPAY1_URL",
            "PGP HostPay1 service URL (for self-callbacks)"
        )

        pgp_hostpay1_response_queue = self.fetch_secret(
            "PGP_HOSTPAY1_RESPONSE_QUEUE",
            "PGP HostPay1 response queue name (for retry callbacks)"
        )

        # Get ChangeNow API key for transaction status queries
        changenow_api_key = self.fetch_secret(
            "CHANGENOW_API_KEY",
            "ChangeNow API key"
        )

        # Get PGP MicroBatch configuration (for batch conversion callbacks)
        pgp_microbatch_response_queue = self.fetch_secret(
            "PGP_MICROBATCH_RESPONSE_QUEUE",
            "PGP MicroBatch response queue name"
        )

        pgp_microbatch_url = self.fetch_secret(
            "PGP_MICROBATCH_URL",
            "PGP MicroBatch service URL"
        )

        # Validate critical configurations
        if not tps_hostpay_signing_key or not success_url_signing_key:
            print(f"⚠️ [CONFIG] Warning: Signing keys not available")
        if not ct_config['cloud_tasks_project_id'] or not ct_config['cloud_tasks_location']:
            print(f"⚠️ [CONFIG] Warning: Cloud Tasks configuration incomplete")

        # Combine all configurations
        config = {
            # Signing keys
            'tps_hostpay_signing_key': tps_hostpay_signing_key,
            'success_url_signing_key': success_url_signing_key,

            # ChangeNow API
            'changenow_api_key': changenow_api_key,

            # Cloud Tasks configuration (from base method)
            **ct_config,

            # Service-specific queues and URLs
            'pgp_hostpay1_url': pgp_hostpay1_url,
            'pgp_hostpay1_response_queue': pgp_hostpay1_response_queue,
            'pgp_hostpay2_queue': pgp_hostpay2_queue,
            'pgp_hostpay2_url': pgp_hostpay2_url,
            'pgp_hostpay3_queue': pgp_hostpay3_queue,
            'pgp_hostpay3_url': pgp_hostpay3_url,
            'pgp_microbatch_response_queue': pgp_microbatch_response_queue,
            'pgp_microbatch_url': pgp_microbatch_url,

            # Database configuration (from base method)
            **db_config
        }

        # Log configuration status
        print(f"📊 [CONFIG] Configuration status:")
        print(f"   TPS_HOSTPAY_SIGNING_KEY: {'✅' if config['tps_hostpay_signing_key'] else '❌'}")
        print(f"   SUCCESS_URL_SIGNING_KEY: {'✅' if config['success_url_signing_key'] else '❌'}")
        print(f"   CHANGENOW_API_KEY: {'✅' if config['changenow_api_key'] else '❌'}")
        print(f"   Cloud Tasks Project: {'✅' if config['cloud_tasks_project_id'] else '❌'}")
        print(f"   Cloud Tasks Location: {'✅' if config['cloud_tasks_location'] else '❌'}")
        print(f"   PGP HostPay1 URL: {'✅' if config['pgp_hostpay1_url'] else '❌'}")
        print(f"   PGP HostPay1 Response Queue: {'✅' if config['pgp_hostpay1_response_queue'] else '❌'}")
        print(f"   PGP HostPay2 Queue: {'✅' if config['pgp_hostpay2_queue'] else '❌'}")
        print(f"   PGP HostPay2 URL: {'✅' if config['pgp_hostpay2_url'] else '❌'}")
        print(f"   PGP HostPay3 Queue: {'✅' if config['pgp_hostpay3_queue'] else '❌'}")
        print(f"   PGP HostPay3 URL: {'✅' if config['pgp_hostpay3_url'] else '❌'}")
        print(f"   PGP MicroBatch Response Queue: {'✅' if config['pgp_microbatch_response_queue'] else '❌'}")
        print(f"   PGP MicroBatch URL: {'✅' if config['pgp_microbatch_url'] else '❌'}")
        print(f"   CLOUD_SQL_CONNECTION_NAME: {'✅' if config['instance_connection_name'] else '❌'}")
        print(f"   DATABASE_NAME_SECRET: {'✅' if config['db_name'] else '❌'}")
        print(f"   DATABASE_USER_SECRET: {'✅' if config['db_user'] else '❌'}")
        print(f"   DATABASE_PASSWORD_SECRET: {'✅' if config['db_password'] else '❌'}")

        return config
