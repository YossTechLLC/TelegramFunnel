#!/usr/bin/env python
"""
Configuration Manager for GCWebhook2-10-26 (Telegram Invite Sender Service).
Handles fetching configuration values from Google Cloud Secret Manager and environment variables.
"""
import os
from google.cloud import secretmanager
from typing import Optional


class ConfigManager:
    """
    Manages configuration and secrets for the GCWebhook2-10-26 service.
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

    def initialize_config(self) -> dict:
        """
        Initialize and return all configuration values for GCWebhook2.

        Returns:
            Dictionary containing all configuration values
        """
        print(f"⚙️ [CONFIG] Initializing GCWebhook2-10-26 configuration")

        # Fetch secrets from Secret Manager
        success_url_signing_key = self.fetch_secret(
            "SUCCESS_URL_SIGNING_KEY",
            "Success URL signing key (for token decryption)"
        )

        telegram_bot_token = self.fetch_secret(
            "TELEGRAM_BOT_SECRET_NAME",
            "Telegram bot token"
        )

        # Validate critical configurations
        if not success_url_signing_key:
            print(f"⚠️ [CONFIG] Warning: SUCCESS_URL_SIGNING_KEY not available")
        if not telegram_bot_token:
            print(f"⚠️ [CONFIG] Warning: TELEGRAM_BOT_SECRET_NAME not available")

        config = {
            # Secrets
            'success_url_signing_key': success_url_signing_key,
            'telegram_bot_token': telegram_bot_token
        }

        # Log configuration status
        print(f"📊 [CONFIG] Configuration status:")
        print(f"   SUCCESS_URL_SIGNING_KEY: {'✅' if config['success_url_signing_key'] else '❌'}")
        print(f"   TELEGRAM_BOT_TOKEN: {'✅' if config['telegram_bot_token'] else '❌'}")

        return config
