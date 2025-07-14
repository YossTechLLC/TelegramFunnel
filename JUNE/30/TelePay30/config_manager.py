#!/usr/bin/env python
import os
from google.cloud import secretmanager
from typing import Optional

class ConfigManager:
    def __init__(self):
        self.bot_token = None
        self.webhook_key = None
        # Get bot username from environment variable
        self.bot_username = self.fetch_bot_username()
        # ChangeNOW and ETH wallet configuration
        self.changenow_api_key = None
        self.host_wallet_eth_address = None
        self.host_wallet_private_key = None
    
    def fetch_telegram_token(self) -> Optional[str]:
        """Fetch the Telegram bot token from Secret Manager."""
        try:
            client = secretmanager.SecretManagerServiceClient()
            secret_path = os.getenv("TELEGRAM_BOT_SECRET_NAME")
            if not secret_path:
                raise ValueError("Environment variable TELEGRAM_BOT_SECRET_NAME is not set.")
            response = client.access_secret_version(request={"name": secret_path})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            print(f"❌ Error fetching the Telegram bot TOKEN: {e}")
            return None

    def fetch_now_webhook_key(self) -> Optional[str]:
        """Fetch the NowPayments webhook key from Secret Manager."""
        try:
            client = secretmanager.SecretManagerServiceClient()
            secret_path = os.getenv("NOWPAYMENT_WEBHOOK_KEY")
            if not secret_path:
                raise ValueError("Environment variable NOWPAYMENT_WEBHOOK_KEY is not set.")
            response = client.access_secret_version(request={"name": secret_path})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            print(f"❌ Error fetching the NOWPAYMENT_WEBHOOK_KEY: {e}")
            return None
    
    def fetch_changenow_api_key(self) -> Optional[str]:
        """Fetch the ChangeNOW API key from Secret Manager."""
        try:
            client = secretmanager.SecretManagerServiceClient()
            secret_path = os.getenv("CHANGENOW_API_KEY")
            if not secret_path:
                raise ValueError("Environment variable CHANGENOW_API_KEY is not set.")
            response = client.access_secret_version(request={"name": secret_path})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            print(f"❌ Error fetching the CHANGENOW_API_KEY: {e}")
            return None
    
    def fetch_host_wallet_eth_address(self) -> Optional[str]:
        """Fetch the host wallet ETH address from Secret Manager."""
        try:
            client = secretmanager.SecretManagerServiceClient()
            secret_path = os.getenv("HOST_WALLET_ETH_ADDRESS_SECRET")
            if not secret_path:
                raise ValueError("Environment variable HOST_WALLET_ETH_ADDRESS_SECRET is not set.")
            response = client.access_secret_version(request={"name": secret_path})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            print(f"❌ Error fetching the HOST_WALLET_ETH_ADDRESS: {e}")
            return None
    
    def fetch_host_wallet_private_key(self) -> Optional[str]:
        """Fetch the host wallet private key from Secret Manager."""
        try:
            client = secretmanager.SecretManagerServiceClient()
            secret_path = os.getenv("HOST_WALLET_PRIVATE_KEY_SECRET")
            if not secret_path:
                raise ValueError("Environment variable HOST_WALLET_PRIVATE_KEY_SECRET is not set.")
            response = client.access_secret_version(request={"name": secret_path})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            print(f"❌ Error fetching the HOST_WALLET_PRIVATE_KEY: {e}")
            return None
    
    def initialize_config(self) -> dict:
        """Initialize and return all configuration values."""
        print("🔧 [INFO] Initializing configuration from Secret Manager...")
        
        # Fetch core configuration
        self.bot_token = self.fetch_telegram_token()
        self.webhook_key = self.fetch_now_webhook_key()
        
        # Fetch ChangeNOW configuration
        self.changenow_api_key = self.fetch_changenow_api_key()
        self.host_wallet_eth_address = self.fetch_host_wallet_eth_address()
        self.host_wallet_private_key = self.fetch_host_wallet_private_key()
        
        # Validate critical configuration
        missing_critical = []
        if not self.bot_token:
            missing_critical.append("TELEGRAM_BOT_TOKEN")
        if not self.bot_username:
            missing_critical.append("TELEGRAM_BOT_USERNAME")
            
        if missing_critical:
            raise RuntimeError(f"❌ Critical configuration missing: {', '.join(missing_critical)}")
        
        # Warn about optional configuration
        missing_optional = []
        if not self.webhook_key:
            missing_optional.append("NOWPAYMENT_WEBHOOK_KEY")
        if not self.changenow_api_key:
            missing_optional.append("CHANGENOW_API_KEY")
        if not self.host_wallet_eth_address:
            missing_optional.append("HOST_WALLET_ETH_ADDRESS_SECRET")
        if not self.host_wallet_private_key:
            missing_optional.append("HOST_WALLET_PRIVATE_KEY_SECRET")
            
        if missing_optional:
            print(f"⚠️ [WARNING] Optional configuration missing: {', '.join(missing_optional)}")
            print("⚠️ [WARNING] Some features may not work properly")
        
        print("✅ [INFO] Configuration initialization completed")
        
        return {
            'bot_token': self.bot_token,
            'webhook_key': self.webhook_key,
            'bot_username': self.bot_username,
            'changenow_api_key': self.changenow_api_key,
            'host_wallet_eth_address': self.host_wallet_eth_address,
            'host_wallet_private_key': self.host_wallet_private_key
        }
    
    def fetch_bot_username(self) -> Optional[str]:
        """Fetch the bot username from Secret Manager."""
        try:
            client = secretmanager.SecretManagerServiceClient()
            secret_path = os.getenv("TELEGRAM_BOT_USERNAME")
            if not secret_path:
                raise ValueError("Environment variable TELEGRAM_BOT_USERNAME is not set.")
            response = client.access_secret_version(request={"name": secret_path})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            print(f"❌ Error fetching the TELEGRAM_BOT_USERNAME: {e}")
            return None
    
    def get_config(self) -> dict:
        """Get current configuration values."""
        return {
            'bot_token': self.bot_token,
            'webhook_key': self.webhook_key,
            'bot_username': self.bot_username,
            'changenow_api_key': self.changenow_api_key,
            'host_wallet_eth_address': self.host_wallet_eth_address,
            'host_wallet_private_key': self.host_wallet_private_key
        }