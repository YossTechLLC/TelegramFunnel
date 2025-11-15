#!/usr/bin/env python
"""
Configuration Manager for PGP_HOSTPAY1_v1 (Validator & Orchestrator Service).
Handles fetching configuration values from Google Cloud Secret Manager.
"""
import os
from google.cloud import secretmanager
from typing import Optional


class ConfigManager:
    """
    Manages configuration and secrets for the PGP_HOSTPAY1_v1 service.
    """

    def __init__(self):
        """Initialize the ConfigManager."""
        self.client = secretmanager.SecretManagerServiceClient()
        print(f"⚙️ [CONFIG] ConfigManager initialized")

    def fetch_secret(self, secret_name_env: str, description: str = "") -> Optional[str]:
        """
        Fetch a secret value from environment variable.
        Cloud Run automatically injects secret values when using --set-secrets.

        Args:
            secret_name_env: Environment variable name containing the secret value
            description: Description for logging purposes

        Returns:
            Secret value or None if failed
        """
        try:
            # Defensive pattern: handle None, strip whitespace, return None if empty
            secret_value = (os.getenv(secret_name_env) or '').strip() or None
            if not secret_value:
                print(f"❌ [CONFIG] Environment variable {secret_name_env} is not set or empty")
                return None

            print(f"✅ [CONFIG] Successfully loaded {description or secret_name_env}")
            return secret_value

        except Exception as e:
            print(f"❌ [CONFIG] Error loading {description or secret_name_env}: {e}")
            return None

    def initialize_config(self) -> dict:
        """
        Initialize and return all configuration values for GCHostPay1.

        Returns:
            Dictionary containing all configuration values
        """
        print(f"⚙️ [CONFIG] Initializing PGP_HOSTPAY1_v1 configuration")

        # Fetch signing keys
        tps_hostpay_signing_key = self.fetch_secret(
            "TPS_HOSTPAY_SIGNING_KEY",
            "TPS HostPay signing key (for GCSplit1 → GCHostPay1)"
        )

        success_url_signing_key = self.fetch_secret(
            "SUCCESS_URL_SIGNING_KEY",
            "Success URL signing key (for internal PGP HostPay communication)"
        )

        # Get Cloud Tasks configuration from Secret Manager
        cloud_tasks_project_id = self.fetch_secret(
            "CLOUD_TASKS_PROJECT_ID",
            "Cloud Tasks project ID"
        )

        cloud_tasks_location = self.fetch_secret(
            "CLOUD_TASKS_LOCATION",
            "Cloud Tasks location/region"
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

        # Fetch database configuration from Secret Manager
        cloud_sql_connection_name = self.fetch_secret(
            "CLOUD_SQL_CONNECTION_NAME",
            "Cloud SQL instance connection name"
        )

        database_name = self.fetch_secret(
            "DATABASE_NAME_SECRET",
            "Database name"
        )

        database_user = self.fetch_secret(
            "DATABASE_USER_SECRET",
            "Database user"
        )

        database_password = self.fetch_secret(
            "DATABASE_PASSWORD_SECRET",
            "Database password"
        )

        # Validate critical configurations
        if not tps_hostpay_signing_key or not success_url_signing_key:
            print(f"⚠️ [CONFIG] Warning: Signing keys not available")
        if not cloud_tasks_project_id or not cloud_tasks_location:
            print(f"⚠️ [CONFIG] Warning: Cloud Tasks configuration incomplete")

        config = {
            # Signing keys
            'tps_hostpay_signing_key': tps_hostpay_signing_key,
            'success_url_signing_key': success_url_signing_key,

            # ChangeNow API
            'changenow_api_key': changenow_api_key,

            # Cloud Tasks configuration
            'cloud_tasks_project_id': cloud_tasks_project_id,
            'cloud_tasks_location': cloud_tasks_location,
            'pgp_hostpay1_url': pgp_hostpay1_url,
            'pgp_hostpay1_response_queue': pgp_hostpay1_response_queue,
            'pgp_hostpay2_queue': pgp_hostpay2_queue,
            'pgp_hostpay2_url': pgp_hostpay2_url,
            'pgp_hostpay3_queue': pgp_hostpay3_queue,
            'pgp_hostpay3_url': pgp_hostpay3_url,
            'pgp_microbatch_response_queue': pgp_microbatch_response_queue,
            'pgp_microbatch_url': pgp_microbatch_url,

            # Database configuration (all from Secret Manager)
            'instance_connection_name': cloud_sql_connection_name,
            'db_name': database_name,
            'db_user': database_user,
            'db_password': database_password
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
