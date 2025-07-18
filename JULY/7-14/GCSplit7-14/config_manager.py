#!/usr/bin/env python
"""
Configuration Manager for TPS7-14 Payment Splitting Service.
Handles fetching configuration values from Google Cloud Secret Manager.
"""
import os
from google.cloud import secretmanager
from typing import Optional

class ConfigManager:
    """
    Manages configuration and secrets for the TPS7-14 service.
    """
    
    def __init__(self):
        """Initialize the ConfigManager."""
        self.client = secretmanager.SecretManagerServiceClient()
        self.changenow_api_key = None
        self.webhook_signing_key = None
    
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
    
    def fetch_webhook_signing_key(self) -> Optional[str]:
        """
        Fetch the webhook signing key from Secret Manager.
        
        Returns:
            Webhook signing key or None if failed
        """
        return self.fetch_secret(
            "WEBHOOK_SIGNING_KEY",
            "webhook signing key"
        )
    
    def get_tps_webhook_url(self) -> Optional[str]:
        """
        Get the TPS webhook URL from environment variable.
        
        Returns:
            TPS webhook URL or None if not set
        """
        webhook_url = os.getenv("TPS_WEBHOOK_URL")
        if webhook_url:
            print(f"🔗 [CONFIG] TPS webhook URL: {webhook_url}")
            return webhook_url
        else:
            print(f"❌ [CONFIG] TPS_WEBHOOK_URL environment variable not set")
            return None
    
    def initialize_config(self) -> dict:
        """
        Initialize and return all configuration values.
        
        Returns:
            Dictionary containing all configuration values
        """
        print(f"⚙️ [CONFIG] Initializing TPS7-14 configuration")
        
        # Fetch all secrets
        self.changenow_api_key = self.fetch_changenow_api_key()
        self.webhook_signing_key = self.fetch_webhook_signing_key()
        
        # Get environment variables
        tps_webhook_url = self.get_tps_webhook_url()
        
        # Validate critical configurations
        if not self.changenow_api_key:
            print(f"⚠️ [CONFIG] Warning: ChangeNow API key not available")
        
        config = {
            'changenow_api_key': self.changenow_api_key,
            'webhook_signing_key': self.webhook_signing_key,
            'tps_webhook_url': tps_webhook_url
        }
        
        # Log configuration status
        print(f"📊 [CONFIG] Configuration status:")
        print(f"   ChangeNow API Key: {'✅' if config['changenow_api_key'] else '❌'}")
        print(f"   Webhook Signing Key: {'✅' if config['webhook_signing_key'] else '❌'}")
        print(f"   TPS Webhook URL: {'✅' if config['tps_webhook_url'] else '❌'}")
        
        return config
    
    def get_config(self) -> dict:
        """
        Get current configuration values.
        
        Returns:
            Dictionary containing current configuration
        """
        return {
            'changenow_api_key': self.changenow_api_key,
            'webhook_signing_key': self.webhook_signing_key
        }