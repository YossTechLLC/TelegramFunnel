#!/usr/bin/env python
"""
Configuration Manager for GCSplit24 ETH Payment System.
Handles secure secret retrieval from Google Cloud Secret Manager.
"""
import os
from typing import Optional, Dict, Any
from google.cloud import secretmanager

class ConfigManager:
    """Manages configuration and secrets for the ETH payment splitting system."""
    
    def __init__(self):
        self.host_wallet_private_key = None
        self.host_wallet_eth_address = None
        self.ethereum_rpc_url = None
        self.oneinch_api_key = None
        self.config_loaded = False
    
    def fetch_secret(self, env_var_name: str, required: bool = True) -> Optional[str]:
        """
        Fetch a secret from Google Cloud Secret Manager.
        
        Args:
            env_var_name: Environment variable containing the secret path
            required: Whether this secret is required for operation
            
        Returns:
            The secret value if found, None if not required and missing
            
        Raises:
            ValueError: If required secret is missing
        """
        try:
            client = secretmanager.SecretManagerServiceClient()
            secret_path = os.getenv(env_var_name)
            
            if not secret_path:
                if required:
                    raise ValueError(f"Environment variable {env_var_name} is not set")
                print(f"⚠️ [WARNING] Optional secret {env_var_name} not configured")
                return None
            
            response = client.access_secret_version(request={"name": secret_path})
            secret_value = response.payload.data.decode("UTF-8")
            
            print(f"✅ [INFO] Successfully fetched secret: {env_var_name}")
            return secret_value
            
        except Exception as e:
            error_msg = f"❌ [ERROR] Failed to fetch secret {env_var_name}: {e}"
            print(error_msg)
            if required:
                raise ValueError(error_msg)
            return None
    
    def load_configuration(self) -> Dict[str, Any]:
        """
        Load all configuration values from Secret Manager.
        
        Returns:
            Dictionary containing all configuration values
            
        Raises:
            ValueError: If required configuration is missing
        """
        try:
            print("🔧 [INFO] Loading ETH payment system configuration...")
            
            # Load required secrets
            self.host_wallet_private_key = self.fetch_secret("HOST_WALLET_PRIVATE_KEY", required=True)
            self.host_wallet_eth_address = self.fetch_secret("HOST_WALLET_ETH_ADDRESS", required=True)
            self.ethereum_rpc_url = self.fetch_secret("ETHEREUM_RPC_URL", required=True)
            self.oneinch_api_key = self.fetch_secret("1INCH_API_KEY", required=True)
            
            # Validate private key format
            if not self.host_wallet_private_key.startswith('0x'):
                self.host_wallet_private_key = '0x' + self.host_wallet_private_key
                print("🔧 [INFO] Added 0x prefix to private key")
            
            # Validate Ethereum address format
            if not self.host_wallet_eth_address.startswith('0x'):
                raise ValueError("Host wallet ETH address must start with 0x")
            
            if len(self.host_wallet_eth_address) != 42:
                raise ValueError("Host wallet ETH address must be 42 characters long")
            
            self.config_loaded = True
            print("✅ [INFO] Configuration loaded successfully")
            
            return self.get_config()
            
        except Exception as e:
            print(f"❌ [ERROR] Configuration loading failed: {e}")
            raise
    
    def get_config(self) -> Dict[str, Any]:
        """
        Get current configuration values.
        
        Returns:
            Dictionary containing configuration (without sensitive data in logs)
        """
        return {
            'host_wallet_private_key': self.host_wallet_private_key,
            'host_wallet_eth_address': self.host_wallet_eth_address,
            'ethereum_rpc_url': self.ethereum_rpc_url,
            'oneinch_api_key': self.oneinch_api_key,
            'config_loaded': self.config_loaded
        }
    
    def get_safe_config_summary(self) -> Dict[str, str]:
        """
        Get a safe summary of configuration for logging (no sensitive data).
        
        Returns:
            Dictionary with masked sensitive values
        """
        if not self.config_loaded:
            return {'status': 'Configuration not loaded'}
        
        return {
            'host_wallet_address': self.host_wallet_eth_address,
            'ethereum_rpc_configured': bool(self.ethereum_rpc_url),
            'private_key_configured': bool(self.host_wallet_private_key),
            'oneinch_api_configured': bool(self.oneinch_api_key),
            'config_status': 'Loaded successfully'
        }
    
    def validate_configuration(self) -> bool:
        """
        Validate that all required configuration is present and properly formatted.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        try:
            if not self.config_loaded:
                print("❌ [ERROR] Configuration not loaded")
                return False
            
            # Check required fields
            required_fields = [
                ('host_wallet_private_key', 'Private key'),
                ('host_wallet_eth_address', 'ETH address'),
                ('ethereum_rpc_url', 'RPC URL'),
                ('oneinch_api_key', '1INCH API key')
            ]
            
            for field_name, description in required_fields:
                field_value = getattr(self, field_name)
                if not field_value:
                    print(f"❌ [ERROR] Missing required configuration: {description}")
                    return False
            
            # Validate formats
            if not self.host_wallet_private_key.startswith('0x') or len(self.host_wallet_private_key) != 66:
                print("❌ [ERROR] Invalid private key format")
                return False
            
            if not self.host_wallet_eth_address.startswith('0x') or len(self.host_wallet_eth_address) != 42:
                print("❌ [ERROR] Invalid ETH address format")
                return False
            
            if not self.ethereum_rpc_url.startswith(('http://', 'https://', 'wss://')):
                print("❌ [ERROR] Invalid RPC URL format")
                return False
            
            print("✅ [INFO] Configuration validation passed")
            return True
            
        except Exception as e:
            print(f"❌ [ERROR] Configuration validation failed: {e}")
            return False