#!/usr/bin/env python
"""
Configuration Manager for PGP_INVITE_v1 (Telegram Invite Sender Service).
Handles fetching configuration values from Google Cloud Secret Manager and environment variables.
"""
import os
from PGP_COMMON.config import BaseConfigManager


class ConfigManager(BaseConfigManager):
    """
    Manages configuration and secrets for the PGP_INVITE_v1 service.
    Inherits common methods from BaseConfigManager.
    """

    def __init__(self):
        """Initialize the ConfigManager."""
        super().__init__(service_name="PGP_INVITE_v1")

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
        Initialize and return all configuration values for PGP_INVITE_v1.

        Returns:
            Dictionary containing all configuration values
        """
        print(f"⚙️ [CONFIG] Initializing PGP_INVITE_v1 configuration")

        # Fetch secrets from Secret Manager (using inherited fetch_secret method)
        success_url_signing_key = self.fetch_secret(
            "SUCCESS_URL_SIGNING_KEY",
            "Success URL signing key (for token decryption)"
        )

        telegram_bot_token = self.fetch_secret(
            "TELEGRAM_BOT_SECRET_NAME",
            "Telegram bot token"
        )

        # Use base method to fetch database configuration
        db_config = self.fetch_database_config()

        # Validate critical configurations
        if not success_url_signing_key:
            print(f"⚠️ [CONFIG] Warning: SUCCESS_URL_SIGNING_KEY not available")
        if not telegram_bot_token:
            print(f"⚠️ [CONFIG] Warning: TELEGRAM_BOT_SECRET_NAME not available")
        if not db_config['instance_connection_name']:
            print(f"⚠️ [CONFIG] Warning: CLOUD_SQL_CONNECTION_NAME not available")
        if not db_config['db_name']:
            print(f"⚠️ [CONFIG] Warning: DATABASE_NAME_SECRET not available")
        if not db_config['db_user']:
            print(f"⚠️ [CONFIG] Warning: DATABASE_USER_SECRET not available")
        if not db_config['db_password']:
            print(f"⚠️ [CONFIG] Warning: DATABASE_PASSWORD_SECRET not available")

        # Fetch payment validation tolerances (service-specific)
        payment_tolerances = self.get_payment_tolerances()

        # Combine all configurations
        config = {
            # Secrets
            'success_url_signing_key': success_url_signing_key,
            'telegram_bot_token': telegram_bot_token,

            # Database configuration (from base method)
            **db_config,

            # Payment validation tolerances
            'payment_min_tolerance': payment_tolerances['min_tolerance'],
            'payment_fallback_tolerance': payment_tolerances['fallback_tolerance']
        }

        # Log configuration status
        print(f"📊 [CONFIG] Configuration status:")
        print(f"   SUCCESS_URL_SIGNING_KEY: {'✅' if config['success_url_signing_key'] else '❌'}")
        print(f"   TELEGRAM_BOT_TOKEN: {'✅' if config['telegram_bot_token'] else '❌'}")
        print(f"   DATABASE_CREDENTIALS: {'✅' if all([db_config['db_name'], db_config['db_user'], db_config['db_password'], db_config['instance_connection_name']]) else '❌'}")
        print(f"   PAYMENT_MIN_TOLERANCE: {config['payment_min_tolerance']} ({config['payment_min_tolerance']*100}%)")
        print(f"   PAYMENT_FALLBACK_TOLERANCE: {config['payment_fallback_tolerance']} ({config['payment_fallback_tolerance']*100}%)")

        return config
