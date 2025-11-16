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

    def get_payment_tolerances(self) -> dict:
        """
        Fetch payment validation tolerance thresholds.

        Returns:
            Dict with 'min_tolerance' and 'fallback_tolerance' as floats
        """
        try:
            # Fetch from environment variables (Cloud Run injects from Secret Manager)
            min_tolerance_str = os.getenv('PAYMENT_MIN_TOLERANCE', '0.50')
            fallback_tolerance_str = os.getenv('PAYMENT_FALLBACK_TOLERANCE', '0.75')

            min_tolerance = float(min_tolerance_str)
            fallback_tolerance = float(fallback_tolerance_str)

            print(f"✅ [CONFIG] Payment min tolerance: {min_tolerance} ({min_tolerance*100}%)")
            print(f"✅ [CONFIG] Payment fallback tolerance: {fallback_tolerance} ({fallback_tolerance*100}%)")

            return {
                'min_tolerance': min_tolerance,
                'fallback_tolerance': fallback_tolerance
            }

        except Exception as e:
            print(f"❌ [CONFIG] Error loading payment tolerances: {e}")
            print(f"⚠️ [CONFIG] Using defaults: min=0.50, fallback=0.75")
            return {
                'min_tolerance': 0.50,
                'fallback_tolerance': 0.75
            }

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

        # Fetch database credentials for payment validation
        instance_connection_name = self.fetch_secret(
            "CLOUD_SQL_CONNECTION_NAME",
            "Cloud SQL connection name"
        )

        db_name = self.fetch_secret(
            "DATABASE_NAME_SECRET",
            "Database name"
        )

        db_user = self.fetch_secret(
            "DATABASE_USER_SECRET",
            "Database user"
        )

        db_password = self.fetch_secret(
            "DATABASE_PASSWORD_SECRET",
            "Database password"
        )

        # Validate critical configurations
        if not success_url_signing_key:
            print(f"⚠️ [CONFIG] Warning: SUCCESS_URL_SIGNING_KEY not available")
        if not telegram_bot_token:
            print(f"⚠️ [CONFIG] Warning: TELEGRAM_BOT_SECRET_NAME not available")
        if not instance_connection_name:
            print(f"⚠️ [CONFIG] Warning: CLOUD_SQL_CONNECTION_NAME not available")
        if not db_name:
            print(f"⚠️ [CONFIG] Warning: DATABASE_NAME_SECRET not available")
        if not db_user:
            print(f"⚠️ [CONFIG] Warning: DATABASE_USER_SECRET not available")
        if not db_password:
            print(f"⚠️ [CONFIG] Warning: DATABASE_PASSWORD_SECRET not available")

        # Fetch payment validation tolerances
        payment_tolerances = self.get_payment_tolerances()

        config = {
            # Secrets
            'success_url_signing_key': success_url_signing_key,
            'telegram_bot_token': telegram_bot_token,
            # Database credentials
            'instance_connection_name': instance_connection_name,
            'db_name': db_name,
            'db_user': db_user,
            'db_password': db_password,
            # Payment validation tolerances
            'payment_min_tolerance': payment_tolerances['min_tolerance'],
            'payment_fallback_tolerance': payment_tolerances['fallback_tolerance']
        }

        # Log configuration status
        print(f"📊 [CONFIG] Configuration status:")
        print(f"   SUCCESS_URL_SIGNING_KEY: {'✅' if config['success_url_signing_key'] else '❌'}")
        print(f"   TELEGRAM_BOT_TOKEN: {'✅' if config['telegram_bot_token'] else '❌'}")
        print(f"   DATABASE_CREDENTIALS: {'✅' if all([db_name, db_user, db_password, instance_connection_name]) else '❌'}")
        print(f"   PAYMENT_MIN_TOLERANCE: {config['payment_min_tolerance']} ({config['payment_min_tolerance']*100}%)")
        print(f"   PAYMENT_FALLBACK_TOLERANCE: {config['payment_fallback_tolerance']} ({config['payment_fallback_tolerance']*100}%)")

        return config
