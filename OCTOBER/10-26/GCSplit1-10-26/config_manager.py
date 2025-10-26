#!/usr/bin/env python
"""
Configuration Manager for GCSplit1-10-26 (Orchestrator Service).
Handles fetching configuration values from Google Cloud Secret Manager and environment variables.
"""
import os
from google.cloud import secretmanager
from typing import Optional


class ConfigManager:
    """
    Manages configuration and secrets for the GCSplit1-10-26 service.
    """

    def __init__(self):
        """Initialize the ConfigManager."""
        self.client = secretmanager.SecretManagerServiceClient()
        print(f"⚙️ [CONFIG] ConfigManager initialized")

    def fetch_secret(self, secret_name_env: str, description: str = "") -> Optional[str]:
        """
        Fetch a secret from Google Cloud Secret Manager.

        Args:
            secret_name_env: Environment variable containing the secret path
            description: Description for logging purposes

        Returns:
            Secret value or None if failed
        """
        try:
            secret_path = os.getenv(secret_name_env)
            if not secret_path:
                print(f"❌ [CONFIG] Environment variable {secret_name_env} is not set")
                return None

            print(f"🔐 [CONFIG] Fetching {description or secret_name_env}")
            response = self.client.access_secret_version(request={"name": secret_path})
            secret_value = response.payload.data.decode("UTF-8")

            print(f"✅ [CONFIG] Successfully fetched {description or secret_name_env}")
            return secret_value

        except Exception as e:
            print(f"❌ [CONFIG] Error fetching {description or secret_name_env}: {e}")
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
                print(f"❌ [CONFIG] Required environment variable {var_name} is not set")
            else:
                print(f"⚠️ [CONFIG] Optional environment variable {var_name} is not set")
            return None

        print(f"✅ [CONFIG] {description or var_name}: {value[:50]}..." if len(value) > 50 else f"✅ [CONFIG] {description or var_name}: {value}")
        return value

    def initialize_config(self) -> dict:
        """
        Initialize and return all configuration values for GCSplit1.

        Returns:
            Dictionary containing all configuration values
        """
        print(f"⚙️ [CONFIG] Initializing GCSplit1-10-26 configuration")

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

        hostpay_webhook_url = self.fetch_secret(
            "HOSTPAY_WEBHOOK_URL",
            "GCHostPay webhook URL"
        )

        db_password = self.fetch_secret(
            "DB_PASSWORD",
            "Database password"
        )

        # Get environment variables for Cloud Tasks
        cloud_tasks_project_id = self.get_env_var(
            "CLOUD_TASKS_PROJECT_ID",
            "Cloud Tasks project ID"
        )

        cloud_tasks_location = self.get_env_var(
            "CLOUD_TASKS_LOCATION",
            "Cloud Tasks location/region"
        )

        gcsplit2_queue = self.fetch_secret(
            "GCSPLIT2_QUEUE",
            "GCSplit2 queue name"
        )

        gcsplit2_url = self.fetch_secret(
            "GCSPLIT2_URL",
            "GCSplit2 service URL"
        )

        gcsplit3_queue = self.fetch_secret(
            "GCSPLIT3_QUEUE",
            "GCSplit3 queue name"
        )

        gcsplit3_url = self.fetch_secret(
            "GCSPLIT3_URL",
            "GCSplit3 service URL"
        )

        hostpay_queue = self.fetch_secret(
            "HOSTPAY_QUEUE",
            "HostPay trigger queue name"
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
            'hostpay_webhook_url': hostpay_webhook_url,

            # Cloud Tasks configuration
            'cloud_tasks_project_id': cloud_tasks_project_id,
            'cloud_tasks_location': cloud_tasks_location,
            'gcsplit2_queue': gcsplit2_queue,
            'gcsplit2_url': gcsplit2_url,
            'gcsplit3_queue': gcsplit3_queue,
            'gcsplit3_url': gcsplit3_url,
            'hostpay_queue': hostpay_queue,

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
        print(f"   HOSTPAY_WEBHOOK_URL: {'✅' if config['hostpay_webhook_url'] else '❌'}")
        print(f"   Cloud Tasks Project: {'✅' if config['cloud_tasks_project_id'] else '❌'}")
        print(f"   Cloud Tasks Location: {'✅' if config['cloud_tasks_location'] else '❌'}")
        print(f"   GCSplit2 Queue: {'✅' if config['gcsplit2_queue'] else '❌'}")
        print(f"   GCSplit2 URL: {'✅' if config['gcsplit2_url'] else '❌'}")
        print(f"   GCSplit3 Queue: {'✅' if config['gcsplit3_queue'] else '❌'}")
        print(f"   GCSplit3 URL: {'✅' if config['gcsplit3_url'] else '❌'}")
        print(f"   HostPay Queue: {'✅' if config['hostpay_queue'] else '❌'}")
        print(f"   CLOUD_SQL_CONNECTION_NAME: {'✅' if config['instance_connection_name'] else '❌'}")
        print(f"   DATABASE_NAME_SECRET: {'✅' if config['db_name'] else '❌'}")
        print(f"   DATABASE_USER_SECRET: {'✅' if config['db_user'] else '❌'}")
        print(f"   DATABASE_PASSWORD_SECRET: {'✅' if config['db_password'] else '❌'}")

        return config
