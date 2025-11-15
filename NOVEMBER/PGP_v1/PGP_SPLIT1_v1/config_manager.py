#!/usr/bin/env python
"""
Configuration Manager for PGP_SPLIT1_v1 (Orchestrator Service).
Handles fetching configuration values from Google Cloud Secret Manager and environment variables.
"""
import os
from google.cloud import secretmanager
from typing import Optional


class ConfigManager:
    """
    Manages configuration and secrets for the PGP_SPLIT1_v1 service.
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

    def get_env_var(self, var_name: str, description: str = "", required: bool = True) -> Optional[str]:
        """
        Get environment variable value.

        Args:
            var_name: Environment variable name
            description: Description for logging
            required: Whether the variable is required

        Returns:
            Environment variable value or None if not found
        """
        value = os.getenv(var_name)
        if not value:
            if required:
                print(f"❌ [CONFIG] Required environment variable {var_name} is not set or empty")
            else:
                print(f"⚠️ [CONFIG] Optional environment variable {var_name} is not set or empty")
            return None

        print(f"✅ [CONFIG] {description or var_name}: {value[:50]}..." if len(value) > 50 else f"✅ [CONFIG] {description or var_name}: {value}")
        return value

    def initialize_config(self) -> dict:
        """
        Initialize and return all configuration values for GCSplit1.

        Returns:
            Dictionary containing all configuration values
        """
        print(f"⚙️ [CONFIG] Initializing PGP_SPLIT1_v1 configuration")

        # Fetch secrets from Secret Manager
        success_url_signing_key = self.fetch_secret(
            "SUCCESS_URL_SIGNING_KEY",
            "Success URL signing key (for webhook verification and token encryption)"
        )

        tps_hostpay_signing_key = self.fetch_secret(
            "TPS_HOSTPAY_SIGNING_KEY",
            "TPS HostPay signing key (for GCHostPay tokens)"
        )

        tp_flat_fee = self.fetch_secret(
            "TP_FLAT_FEE",
            "TelePay flat fee percentage"
        )

        pgp_hostpay1_url = self.fetch_secret(
            "PGP_HOSTPAY1_URL",
            "PGP HostPay1 webhook URL"
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

        pgp_split2_queue = self.fetch_secret(
            "PGP_SPLIT2_ESTIMATE_QUEUE",
            "PGP Split2 estimate queue name"
        )

        pgp_split2_url = self.fetch_secret(
            "PGP_SPLIT2_URL",
            "PGP Split2 service URL"
        )

        pgp_split3_queue = self.fetch_secret(
            "PGP_SPLIT3_SWAP_QUEUE",
            "PGP Split3 swap queue name"
        )

        pgp_split3_url = self.fetch_secret(
            "PGP_SPLIT3_URL",
            "PGP Split3 service URL"
        )

        pgp_hostpay_trigger_queue = self.fetch_secret(
            "PGP_HOSTPAY_TRIGGER_QUEUE",
            "PGP HostPay trigger queue name"
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
        if not success_url_signing_key:
            print(f"⚠️ [CONFIG] Warning: SUCCESS_URL_SIGNING_KEY not available")
        if not tp_flat_fee:
            print(f"⚠️ [CONFIG] Warning: TP_FLAT_FEE not available, will default to 3%")
        if not cloud_tasks_project_id or not cloud_tasks_location:
            print(f"⚠️ [CONFIG] Warning: Cloud Tasks configuration incomplete")

        config = {
            # Secrets
            'success_url_signing_key': success_url_signing_key,
            'tps_hostpay_signing_key': tps_hostpay_signing_key,
            'tp_flat_fee': tp_flat_fee,
            'pgp_hostpay1_url': pgp_hostpay1_url,

            # Cloud Tasks configuration
            'cloud_tasks_project_id': cloud_tasks_project_id,
            'cloud_tasks_location': cloud_tasks_location,
            'pgp_split2_queue': pgp_split2_queue,
            'pgp_split2_url': pgp_split2_url,
            'pgp_split3_queue': pgp_split3_queue,
            'pgp_split3_url': pgp_split3_url,
            'pgp_hostpay_trigger_queue': pgp_hostpay_trigger_queue,

            # Database configuration (all from Secret Manager)
            'instance_connection_name': cloud_sql_connection_name,
            'db_name': database_name,
            'db_user': database_user,
            'db_password': database_password
        }

        # Log configuration status
        print(f"📊 [CONFIG] Configuration status:")
        print(f"   SUCCESS_URL_SIGNING_KEY: {'✅' if config['success_url_signing_key'] else '❌'}")
        print(f"   TPS_HOSTPAY_SIGNING_KEY: {'✅' if config['tps_hostpay_signing_key'] else '❌'}")
        print(f"   TP_FLAT_FEE: {'✅' if config['tp_flat_fee'] else '❌'}")
        print(f"   PGP HostPay1 URL: {'✅' if config['pgp_hostpay1_url'] else '❌'}")
        print(f"   Cloud Tasks Project: {'✅' if config['cloud_tasks_project_id'] else '❌'}")
        print(f"   Cloud Tasks Location: {'✅' if config['cloud_tasks_location'] else '❌'}")
        print(f"   PGP Split2 Queue: {'✅' if config['pgp_split2_queue'] else '❌'}")
        print(f"   PGP Split2 URL: {'✅' if config['pgp_split2_url'] else '❌'}")
        print(f"   PGP Split3 Queue: {'✅' if config['pgp_split3_queue'] else '❌'}")
        print(f"   PGP Split3 URL: {'✅' if config['pgp_split3_url'] else '❌'}")
        print(f"   PGP HostPay Trigger Queue: {'✅' if config['pgp_hostpay_trigger_queue'] else '❌'}")
        print(f"   CLOUD_SQL_CONNECTION_NAME: {'✅' if config['instance_connection_name'] else '❌'}")
        print(f"   DATABASE_NAME_SECRET: {'✅' if config['db_name'] else '❌'}")
        print(f"   DATABASE_USER_SECRET: {'✅' if config['db_user'] else '❌'}")
        print(f"   DATABASE_PASSWORD_SECRET: {'✅' if config['db_password'] else '❌'}")

        return config
