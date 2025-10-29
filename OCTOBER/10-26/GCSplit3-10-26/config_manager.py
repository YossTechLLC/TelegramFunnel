#!/usr/bin/env python
"""
Configuration Manager for GCSplit3-10-26 (ETH→ClientCurrency Swapper Service).
Handles fetching configuration values from Google Cloud Secret Manager and environment variables.
"""
import os
from google.cloud import secretmanager
from typing import Optional


class ConfigManager:
    """
    Manages configuration and secrets for the GCSplit3-10-26 service.
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
            secret_value = os.getenv(secret_name_env)
            if not secret_value:
                print(f"❌ [CONFIG] Environment variable {secret_name_env} is not set")
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
                print(f"❌ [CONFIG] Required environment variable {var_name} is not set")
            else:
                print(f"⚠️ [CONFIG] Optional environment variable {var_name} is not set")
            return None

        print(f"✅ [CONFIG] {description or var_name}: {value[:50]}..." if len(value) > 50 else f"✅ [CONFIG] {description or var_name}: {value}")
        return value

    def initialize_config(self) -> dict:
        """
        Initialize and return all configuration values for GCSplit3.

        Returns:
            Dictionary containing all configuration values
        """
        print(f"⚙️ [CONFIG] Initializing GCSplit3-10-26 configuration")

        # Fetch secrets from Secret Manager
        success_url_signing_key = self.fetch_secret(
            "SUCCESS_URL_SIGNING_KEY",
            "Success URL signing key (for token encryption/decryption)"
        )

        changenow_api_key = self.fetch_secret(
            "CHANGENOW_API_KEY",
            "ChangeNow API key"
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

        gcsplit1_response_queue = self.fetch_secret(
            "GCSPLIT3_RESPONSE_QUEUE",
            "GCSplit1 response queue name (GCSplit3 → GCSplit1)"
        )

        gcsplit1_url = self.fetch_secret(
            "GCSPLIT1_SWAP_RESPONSE_URL",
            "GCSplit1 /eth-client-swap endpoint URL"
        )

        # Validate critical configurations
        if not success_url_signing_key:
            print(f"⚠️ [CONFIG] Warning: SUCCESS_URL_SIGNING_KEY not available")
        if not changenow_api_key:
            print(f"⚠️ [CONFIG] Warning: CHANGENOW_API_KEY not available")
        if not cloud_tasks_project_id or not cloud_tasks_location:
            print(f"⚠️ [CONFIG] Warning: Cloud Tasks configuration incomplete")

        config = {
            # Secrets
            'success_url_signing_key': success_url_signing_key,
            'changenow_api_key': changenow_api_key,

            # Cloud Tasks configuration
            'cloud_tasks_project_id': cloud_tasks_project_id,
            'cloud_tasks_location': cloud_tasks_location,
            'gcsplit1_response_queue': gcsplit1_response_queue,
            'gcsplit1_url': gcsplit1_url
        }

        # Log configuration status
        print(f"📊 [CONFIG] Configuration status:")
        print(f"   SUCCESS_URL_SIGNING_KEY: {'✅' if config['success_url_signing_key'] else '❌'}")
        print(f"   CHANGENOW_API_KEY: {'✅' if config['changenow_api_key'] else '❌'}")
        print(f"   Cloud Tasks Project: {'✅' if config['cloud_tasks_project_id'] else '❌'}")
        print(f"   Cloud Tasks Location: {'✅' if config['cloud_tasks_location'] else '❌'}")
        print(f"   GCSplit1 Response Queue: {'✅' if config['gcsplit1_response_queue'] else '❌'}")
        print(f"   GCSplit1 URL: {'✅' if config['gcsplit1_url'] else '❌'}")

        return config
