#!/usr/bin/env python
"""
Configuration Manager for GCWebhook1-10-26 (Payment Processor Service).
Handles fetching configuration values from Google Cloud Secret Manager and environment variables.
"""
import os
from google.cloud import secretmanager
from typing import Optional


class ConfigManager:
    """
    Manages configuration and secrets for the GCWebhook1-10-26 service.
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
        Initialize and return all configuration values for GCWebhook1.

        Returns:
            Dictionary containing all configuration values
        """
        print(f"⚙️ [CONFIG] Initializing GCWebhook1-10-26 configuration")

        # Fetch secrets from Secret Manager
        success_url_signing_key = self.fetch_secret(
            "SUCCESS_URL_SIGNING_KEY",
            "Success URL signing key (for token verification and encryption)"
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

        gcwebhook2_queue = self.fetch_secret(
            "GCWEBHOOK2_QUEUE",
            "GCWebhook2 queue name"
        )

        gcwebhook2_url = self.fetch_secret(
            "GCWEBHOOK2_URL",
            "GCWebhook2 service URL"
        )

        gcsplit1_queue = self.fetch_secret(
            "GCSPLIT1_QUEUE",
            "GCSplit1 queue name"
        )

        gcsplit1_url = self.fetch_secret(
            "GCSPLIT1_URL",
            "GCSplit1 service URL"
        )

        # GCAccumulator configuration (for threshold payout)
        gcaccumulator_queue = self.fetch_secret(
            "GCACCUMULATOR_QUEUE",
            "GCAccumulator queue name"
        )

        gcaccumulator_url = self.fetch_secret(
            "GCACCUMULATOR_URL",
            "GCAccumulator service URL"
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
        if not cloud_tasks_project_id or not cloud_tasks_location:
            print(f"⚠️ [CONFIG] Warning: Cloud Tasks configuration incomplete")

        config = {
            # Secrets
            'success_url_signing_key': success_url_signing_key,

            # Cloud Tasks configuration
            'cloud_tasks_project_id': cloud_tasks_project_id,
            'cloud_tasks_location': cloud_tasks_location,
            'gcwebhook2_queue': gcwebhook2_queue,
            'gcwebhook2_url': gcwebhook2_url,
            'gcsplit1_queue': gcsplit1_queue,
            'gcsplit1_url': gcsplit1_url,
            'gcaccumulator_queue': gcaccumulator_queue,
            'gcaccumulator_url': gcaccumulator_url,

            # Database configuration (all from Secret Manager)
            'instance_connection_name': cloud_sql_connection_name,
            'db_name': database_name,
            'db_user': database_user,
            'db_password': database_password
        }

        # Log configuration status
        print(f"📊 [CONFIG] Configuration status:")
        print(f"   SUCCESS_URL_SIGNING_KEY: {'✅' if config['success_url_signing_key'] else '❌'}")
        print(f"   Cloud Tasks Project: {'✅' if config['cloud_tasks_project_id'] else '❌'}")
        print(f"   Cloud Tasks Location: {'✅' if config['cloud_tasks_location'] else '❌'}")
        print(f"   GCWebhook2 Queue: {'✅' if config['gcwebhook2_queue'] else '❌'}")
        print(f"   GCWebhook2 URL: {'✅' if config['gcwebhook2_url'] else '❌'}")
        print(f"   GCSplit1 Queue: {'✅' if config['gcsplit1_queue'] else '❌'}")
        print(f"   GCSplit1 URL: {'✅' if config['gcsplit1_url'] else '❌'}")
        print(f"   GCAccumulator Queue: {'✅' if config['gcaccumulator_queue'] else '❌'}")
        print(f"   GCAccumulator URL: {'✅' if config['gcaccumulator_url'] else '❌'}")
        print(f"   CLOUD_SQL_CONNECTION_NAME: {'✅' if config['instance_connection_name'] else '❌'}")
        print(f"   DATABASE_NAME_SECRET: {'✅' if config['db_name'] else '❌'}")
        print(f"   DATABASE_USER_SECRET: {'✅' if config['db_user'] else '❌'}")
        print(f"   DATABASE_PASSWORD_SECRET: {'✅' if config['db_password'] else '❌'}")

        return config
