#!/usr/bin/env python
"""
Configuration Manager for TPS10-16 Payment Splitting Service.
Handles fetching configuration values from Google Cloud Secret Manager.
"""
import os
from google.cloud import secretmanager
from typing import Optional

#LIST OF ENVIORNMENT VARIABLES
# CHANGENOW_API_KEY: Path to ChangeNow API key in Secret Manager
# SUCCESS_URL_SIGNING_KEY: Path to success URL signing key in Secret Manager (shared with tph10-16)
# TPS_WEBHOOK_URL: Path to TPS webhook URL in Secret Manager
# TELEGRAM_BOT_USERNAME: Path to Telegram bot token in Secret Manager (shared with main app)
# TP_FLAT_FEE: Path to TelePay flat fee percentage in Secret Manager

class ConfigManager:
    """
    Manages configuration and secrets for the TPS10-16 service.
    """
    
    def __init__(self):
        """Initialize the ConfigManager."""
        self.client = secretmanager.SecretManagerServiceClient()
        self.changenow_api_key = None
        self.success_url_signing_key = None
        self.telegram_bot_token = None
        self.tp_flat_fee = None
    
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
    
    def fetch_changenow_api_key(self) -> Optional[str]:
        """
        Fetch the ChangeNow API key from Secret Manager.
        
        Returns:
            ChangeNow API key or None if failed
        """
        return self.fetch_secret(
            "CHANGENOW_API_KEY",
            "ChangeNow API key"
        )
    
    def fetch_success_url_signing_key(self) -> Optional[str]:
        """
        Fetch the success URL signing key from Secret Manager.
        This key is shared with tph10-16 for webhook signature verification.

        Returns:
            Success URL signing key or None if failed
        """
        return self.fetch_secret(
            "SUCCESS_URL_SIGNING_KEY",
            "success URL signing key"
        )

    def fetch_telegram_bot_token(self) -> Optional[str]:
        """
        Fetch the Telegram bot token from Secret Manager.

        Returns:
            Telegram bot token or None if failed
        """
        return self.fetch_secret(
            "TELEGRAM_BOT_USERNAME",
            "Telegram bot token"
        )

    def fetch_tp_flat_fee(self) -> Optional[str]:
        """
        Fetch the TelePay flat fee percentage from Secret Manager.

        Returns:
            TelePay flat fee as string (e.g., "3" for 3%) or None if failed
        """
        return self.fetch_secret(
            "TP_FLAT_FEE",
            "TelePay flat fee percentage"
        )
    
    def get_tps_webhook_url(self) -> Optional[str]:
        """
        Get the TPS webhook URL from Secret Manager.

        Returns:
            TPS webhook URL or None if failed
        """
        return self.fetch_secret(
            "TPS_WEBHOOK_URL",
            "TPS webhook URL"
        )
    
    def initialize_config(self) -> dict:
        """
        Initialize and return all configuration values.

        Returns:
            Dictionary containing all configuration values
        """
        print(f"⚙️ [CONFIG] Initializing TPS10-16 configuration")

        # Fetch all secrets
        self.changenow_api_key = self.fetch_changenow_api_key()
        self.success_url_signing_key = self.fetch_success_url_signing_key()
        self.telegram_bot_token = self.fetch_telegram_bot_token()
        self.tp_flat_fee = self.fetch_tp_flat_fee()

        # Get environment variables
        tps_webhook_url = self.get_tps_webhook_url()

        # Validate critical configurations
        if not self.changenow_api_key:
            print(f"⚠️ [CONFIG] Warning: ChangeNow API key not available")
        if not self.tp_flat_fee:
            print(f"⚠️ [CONFIG] Warning: TP flat fee not available, will default to 3%")

        config = {
            'changenow_api_key': self.changenow_api_key,
            'success_url_signing_key': self.success_url_signing_key,
            'tps_webhook_url': tps_webhook_url,
            'telegram_bot_token': self.telegram_bot_token,
            'tp_flat_fee': self.tp_flat_fee
        }

        # Log configuration status
        print(f"📊 [CONFIG] Configuration status:")
        print(f"   ChangeNow API Key: {'✅' if config['changenow_api_key'] else '❌'}")
        print(f"   Success URL Signing Key: {'✅' if config['success_url_signing_key'] else '❌'}")
        print(f"   TPS Webhook URL: {'✅' if config['tps_webhook_url'] else '❌'}")
        print(f"   Telegram Bot Token: {'✅' if config['telegram_bot_token'] else '❌'}")
        print(f"   TP Flat Fee: {'✅' if config['tp_flat_fee'] else '❌'}")

        return config
    
    def get_config(self) -> dict:
        """
        Get current configuration values.

        Returns:
            Dictionary containing current configuration
        """
        return {
            'changenow_api_key': self.changenow_api_key,
            'success_url_signing_key': self.success_url_signing_key,
            'tp_flat_fee': self.tp_flat_fee
        }