#!/usr/bin/env python
"""
Configuration Manager for HPW10-9 Host Payment Wallet Service.
Handles fetching configuration values from Google Cloud Secret Manager.
"""
import os
from google.cloud import secretmanager
from typing import Optional

# LIST OF ENVIRONMENT VARIABLES
# HOST_WALLET_ETH_ADDRESS: Path to custodial wallet address in Secret Manager
# HOST_WALLET_PRIVATE_KEY: Path to custodial wallet private key in Secret Manager
# NOWPAYMENT_WEBHOOK_KEY: Path to NowPayments webhook key in Secret Manager
# ETHEREUM_RPC_URL: Path to Ethereum RPC endpoint URL in Secret Manager
# ETHEREUM_RPC_URL_API: Path to Alchemy API key in Secret Manager (for future use)
# DATABASE_HOST_SECRET: Path to database host in Secret Manager
# DATABASE_NAME_SECRET: Path to database name in Secret Manager
# DATABASE_USER_SECRET: Path to database user in Secret Manager
# DATABASE_PASSWORD_SECRET: Path to database password in Secret Manager
# ETH_NETWORK: Ethereum network (mainnet/goerli/sepolia)
# PAYMENT_TIMEOUT_MINUTES: Payment expiration timeout
# MAX_RETRY_ATTEMPTS: Maximum retry attempts for failed payments
# POLLING_INTERVAL_SECONDS: Interval for polling wallet balance

class ConfigManager:
    """
    Manages configuration and secrets for the HPW10-9 service.
    """

    def __init__(self):
        """Initialize the ConfigManager."""
        self.client = secretmanager.SecretManagerServiceClient()
        self.host_wallet_address = None
        self.host_wallet_private_key = None
        self.nowpayments_ipn_secret = None
        self.eth_node_url = None

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

    def fetch_host_wallet_address(self) -> Optional[str]:
        """
        Fetch the host custodial wallet address from Secret Manager.

        Returns:
            Ethereum address or None if failed
        """
        return self.fetch_secret(
            "HOST_WALLET_ETH_ADDRESS",
            "host custodial wallet address"
        )

    def fetch_host_wallet_private_key(self) -> Optional[str]:
        """
        Fetch the host wallet private key from Secret Manager.

        SECURITY WARNING: This key must NEVER be logged or exposed.

        Returns:
            Private key or None if failed
        """
        key = self.fetch_secret(
            "HOST_WALLET_PRIVATE_KEY",
            "host wallet private key"
        )
        if key:
            print(f"🔒 [CONFIG] Private key loaded (length: {len(key)} chars)")
        return key

    def fetch_nowpayments_ipn_secret(self) -> Optional[str]:
        """
        Fetch the NowPayments webhook key from Secret Manager.

        Returns:
            NowPayments webhook key or None if failed
        """
        return self.fetch_secret(
            "NOWPAYMENT_WEBHOOK_KEY",
            "NowPayments webhook key"
        )

    def fetch_eth_node_url(self) -> Optional[str]:
        """
        Fetch the Ethereum node RPC URL from Secret Manager.

        Returns:
            Node URL or None if failed
        """
        return self.fetch_secret(
            "ETHEREUM_RPC_URL",
            "Ethereum node RPC URL"
        )

    def fetch_ethereum_rpc_api_key(self) -> Optional[str]:
        """
        Fetch the Alchemy API key from Secret Manager.
        This is stored separately for future use cases.

        Returns:
            Alchemy API key or None if failed
        """
        return self.fetch_secret(
            "ETHEREUM_RPC_URL_API",
            "Alchemy API key"
        )

    def get_eth_network(self) -> str:
        """
        Get the Ethereum network from environment variable.

        Returns:
            Network name (mainnet/goerli/sepolia)
        """
        network = os.getenv("ETH_NETWORK", "mainnet")
        print(f"🌐 [CONFIG] Ethereum network: {network}")
        return network

    def get_payment_timeout_minutes(self) -> int:
        """
        Get payment timeout in minutes from environment variable.

        Returns:
            Timeout in minutes (default: 120)
        """
        timeout = int(os.getenv("PAYMENT_TIMEOUT_MINUTES", "120"))
        print(f"⏱️ [CONFIG] Payment timeout: {timeout} minutes")
        return timeout

    def get_max_retry_attempts(self) -> int:
        """
        Get maximum retry attempts from environment variable.

        Returns:
            Maximum retry attempts (default: 5)
        """
        max_retries = int(os.getenv("MAX_RETRY_ATTEMPTS", "5"))
        print(f"🔄 [CONFIG] Max retry attempts: {max_retries}")
        return max_retries

    def get_polling_interval_seconds(self) -> int:
        """
        Get polling interval in seconds from environment variable.

        Returns:
            Polling interval in seconds (default: 30)
        """
        interval = int(os.getenv("POLLING_INTERVAL_SECONDS", "30"))
        print(f"⏲️ [CONFIG] Polling interval: {interval} seconds")
        return interval

    def initialize_config(self) -> dict:
        """
        Initialize and return all configuration values.

        Returns:
            Dictionary containing all configuration values
        """
        print(f"⚙️ [CONFIG] Initializing HPW10-9 configuration")

        # Fetch all secrets
        self.host_wallet_address = self.fetch_host_wallet_address()
        self.host_wallet_private_key = self.fetch_host_wallet_private_key()
        self.nowpayments_ipn_secret = self.fetch_nowpayments_ipn_secret()
        self.eth_node_url = self.fetch_eth_node_url()

        # Fetch Alchemy API key (for future use)
        ethereum_rpc_api_key = self.fetch_ethereum_rpc_api_key()

        # Get environment variables
        eth_network = self.get_eth_network()
        payment_timeout = self.get_payment_timeout_minutes()
        max_retries = self.get_max_retry_attempts()
        polling_interval = self.get_polling_interval_seconds()

        # Validate critical configurations
        if not self.host_wallet_address:
            print(f"⚠️ [CONFIG] Warning: Host wallet address not available")
        if not self.host_wallet_private_key:
            print(f"⚠️ [CONFIG] Warning: Host wallet private key not available")
        if not self.eth_node_url:
            print(f"⚠️ [CONFIG] Warning: Ethereum node URL not available")

        config = {
            'host_wallet_address': self.host_wallet_address,
            'host_wallet_private_key': self.host_wallet_private_key,
            'nowpayments_ipn_secret': self.nowpayments_ipn_secret,
            'eth_node_url': self.eth_node_url,
            'ethereum_rpc_api_key': ethereum_rpc_api_key,
            'eth_network': eth_network,
            'payment_timeout_minutes': payment_timeout,
            'max_retry_attempts': max_retries,
            'polling_interval_seconds': polling_interval
        }

        # Log configuration status (NEVER log private key or API keys)
        print(f"📊 [CONFIG] Configuration status:")
        print(f"   Host Wallet Address: {'✅' if config['host_wallet_address'] else '❌'}")
        print(f"   Host Wallet Private Key: {'✅' if config['host_wallet_private_key'] else '❌'}")
        print(f"   NowPayments Webhook Key: {'✅' if config['nowpayments_ipn_secret'] else '❌'}")
        print(f"   Ethereum Node URL: {'✅' if config['eth_node_url'] else '❌'}")
        print(f"   Ethereum RPC API Key: {'✅' if config['ethereum_rpc_api_key'] else '❌'} (for future use)")
        print(f"   Network: {config['eth_network']}")
        print(f"   Payment Timeout: {config['payment_timeout_minutes']} min")
        print(f"   Max Retries: {config['max_retry_attempts']}")
        print(f"   Polling Interval: {config['polling_interval_seconds']}s")

        return config

    def get_config(self) -> dict:
        """
        Get current configuration values.

        Returns:
            Dictionary containing current configuration
        """
        return {
            'host_wallet_address': self.host_wallet_address,
            'host_wallet_private_key': self.host_wallet_private_key,
            'nowpayments_ipn_secret': self.nowpayments_ipn_secret,
            'eth_node_url': self.eth_node_url
        }
