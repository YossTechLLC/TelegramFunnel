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

        # Fetch signing key for internal communication
        success_url_signing_key = self.fetch_secret(
            "SUCCESS_URL_SIGNING_KEY",
            "Success URL signing key (for token verification and encryption)"
        )

        # PGP Split2 configuration (for USDT conversion estimates)
        pgp_split2_queue = self.fetch_secret(
            "PGP_SPLIT2_ESTIMATE_QUEUE",
            "PGP Split2 estimate queue name"
        )

        pgp_split2_url = self.fetch_secret(
            "PGP_SPLIT2_URL",
            "PGP Split2 service URL"
        )

        # PGP Split3 configuration (for ETH→USDT swap creation)
        pgp_split3_queue = self.fetch_secret(
            "PGP_SPLIT3_SWAP_QUEUE",
            "PGP Split3 swap queue name"
        )

        pgp_split3_url = self.fetch_secret(
            "PGP_SPLIT3_URL",
            "PGP Split3 service URL"
        )

        # PGP HostPay1 configuration (for swap execution)
        pgp_hostpay1_queue = self.fetch_secret(
            "PGP_HOSTPAY_TRIGGER_QUEUE",
            "PGP HostPay trigger queue name"
        )

        pgp_hostpay1_url = self.fetch_secret(
            "PGP_HOSTPAY1_URL",
            "PGP HostPay1 service URL"
        )

        # Host wallet configuration
        host_wallet_usdt_address = self.fetch_secret(
            "HOST_WALLET_USDT_ADDRESS",
            "Host USDT wallet address"
        )

        # TP fee configuration (for fee calculation)
        tp_flat_fee = self.fetch_secret(
            "TP_FLAT_FEE",
            "TP flat fee percentage"
        ) or "3"  # Default 3%

        # Validate critical configurations
        if not success_url_signing_key:
            print(f"⚠️ [CONFIG] Warning: SUCCESS_URL_SIGNING_KEY not available")
        if not ct_config['cloud_tasks_project_id'] or not ct_config['cloud_tasks_location']:
            print(f"⚠️ [CONFIG] Warning: Cloud Tasks configuration incomplete")

        # Combine all configurations
        config = {
            # Signing key
            'success_url_signing_key': success_url_signing_key,

            # Cloud Tasks configuration (from base method)
            **ct_config,

            # Service-specific queues and URLs
            'pgp_split2_queue': pgp_split2_queue,
            'pgp_split2_url': pgp_split2_url,
            'pgp_split3_queue': pgp_split3_queue,
            'pgp_split3_url': pgp_split3_url,
            'pgp_hostpay1_queue': pgp_hostpay1_queue,
            'pgp_hostpay1_url': pgp_hostpay1_url,

            # Wallet configuration
            'host_wallet_usdt_address': host_wallet_usdt_address,

            # Fee configuration
            'tp_flat_fee': tp_flat_fee,

            # Database configuration (from base method)
            **db_config
        }

        # Log configuration status
        print(f"📊 [CONFIG] Configuration status:")
        print(f"   SUCCESS_URL_SIGNING_KEY: {'✅' if config['success_url_signing_key'] else '❌'}")
        print(f"   Cloud Tasks Project: {'✅' if config['cloud_tasks_project_id'] else '❌'}")
        print(f"   Cloud Tasks Location: {'✅' if config['cloud_tasks_location'] else '❌'}")
        print(f"   PGP Split2 Queue: {'✅' if config['pgp_split2_queue'] else '❌'}")
        print(f"   PGP Split2 URL: {'✅' if config['pgp_split2_url'] else '❌'}")
        print(f"   PGP Split3 Queue: {'✅' if config['pgp_split3_queue'] else '❌'}")
        print(f"   PGP Split3 URL: {'✅' if config['pgp_split3_url'] else '❌'}")
        print(f"   PGP HostPay1 Queue: {'✅' if config['pgp_hostpay1_queue'] else '❌'}")
        print(f"   PGP HostPay1 URL: {'✅' if config['pgp_hostpay1_url'] else '❌'}")
        print(f"   Host USDT Wallet: {'✅' if config['host_wallet_usdt_address'] else '❌'}")
        print(f"   CLOUD_SQL_CONNECTION_NAME: {'✅' if config['instance_connection_name'] else '❌'}")
        print(f"   DATABASE_NAME_SECRET: {'✅' if config['db_name'] else '❌'}")
        print(f"   DATABASE_USER_SECRET: {'✅' if config['db_user'] else '❌'}")
        print(f"   DATABASE_PASSWORD_SECRET: {'✅' if config['db_password'] else '❌'}")
        print(f"   TP_FLAT_FEE: {config['tp_flat_fee']}%")

        return config
