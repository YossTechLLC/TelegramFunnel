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

    # ========== HOT-RELOADABLE SECRET GETTERS ==========

    def get_telegram_token(self) -> str:
        """Get Telegram bot token (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("TELEGRAM_BOT_API_TOKEN")
        return self.fetch_secret_dynamic(
            secret_path,
            "Telegram bot token",
            cache_key="telegram_bot_token"
        )

    def get_payment_min_tolerance(self) -> float:
        """Get payment minimum tolerance (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("PAYMENT_MIN_TOLERANCE")
        tolerance_str = self.fetch_secret_dynamic(
            secret_path,
            "Payment min tolerance",
            cache_key="payment_min_tolerance"
        ) or "0.50"
        try:
            return float(tolerance_str)
        except (ValueError, TypeError):
            print(f"⚠️ [CONFIG] Invalid min tolerance value, using default: 0.50")
            return 0.50

    def get_payment_fallback_tolerance(self) -> float:
        """Get payment fallback tolerance (HOT-RELOADABLE)."""
        secret_path = self.build_secret_path("PAYMENT_FALLBACK_TOLERANCE")
        tolerance_str = self.fetch_secret_dynamic(
            secret_path,
            "Payment fallback tolerance",
            cache_key="payment_fallback_tolerance"
        ) or "0.75"
        try:
            return float(tolerance_str)
        except (ValueError, TypeError):
            print(f"⚠️ [CONFIG] Invalid fallback tolerance value, using default: 0.75")
            return 0.75

    # ========== DEPRECATED METHOD (kept for backward compatibility) ==========

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

        # Fetch STATIC secrets (security-critical)
        success_url_signing_key = self.fetch_secret(
            "SUCCESS_URL_SIGNING_KEY",
            "Success URL signing key (for token decryption) - STATIC"
        )

        # Use base method to fetch database configuration (STATIC)
        db_config = self.fetch_database_config()

        # Validate critical configurations
        if not success_url_signing_key:
            print(f"⚠️ [CONFIG] Warning: SUCCESS_URL_SIGNING_KEY not available")
        if not db_config['instance_connection_name']:
            print(f"⚠️ [CONFIG] Warning: CLOUD_SQL_CONNECTION_NAME not available")
        if not db_config['db_name']:
            print(f"⚠️ [CONFIG] Warning: DATABASE_NAME_SECRET not available")
        if not db_config['db_user']:
            print(f"⚠️ [CONFIG] Warning: DATABASE_USER_SECRET not available")
        if not db_config['db_password']:
            print(f"⚠️ [CONFIG] Warning: DATABASE_PASSWORD_SECRET not available")

        # Combine all configurations
        # Note: Hot-reloadable secrets are NOT fetched here - they are fetched on-demand via getter methods
        config = {
            # STATIC Secrets (loaded once at startup)
            'success_url_signing_key': success_url_signing_key,

            # Database configuration (from base method - STATIC)
            **db_config
        }

        # Log configuration status
        print(f"📊 [CONFIG] Configuration status:")
        print(f"   SUCCESS_URL_SIGNING_KEY (static): {'✅' if config['success_url_signing_key'] else '❌'}")
        print(f"   DATABASE_CREDENTIALS: {'✅' if all([db_config['db_name'], db_config['db_user'], db_config['db_password'], db_config['instance_connection_name']]) else '❌'}")
        print(f"   Hot-reloadable secrets: TELEGRAM_BOT_API_TOKEN, PAYMENT_MIN_TOLERANCE, PAYMENT_FALLBACK_TOLERANCE")

        return config
