#!/usr/bin/env python
"""
Wallet Manager for GCHostPay10-21 Host Wallet Payment Service.
Handles all Web3 wallet connections and ETH payment execution.
Uses Google Cloud Secret Manager for secure credential storage.
Enhanced with Alchemy SDK for gas optimization, retry logic, and webhook monitoring.
"""
import os
import time
from google.cloud import secretmanager
from typing import Optional, Dict, Any
from web3 import Web3
from web3.middleware import geth_poa_middleware


class WalletManager:
    """
    Manages Web3 wallet operations for the GCHostPay10-21 service.
    Handles ETH payment execution from host wallet to ChangeNow payin addresses.
    """

    def __init__(self):
        """Initialize the WalletManager with Web3 and Alchemy SDK."""
        self.host_wallet_address = None
        self.host_wallet_private_key = None
        self.web3_provider_url = None
        self.alchemy_api_key = None
        self.w3 = None
        self.alchemy = None

        # Retry configuration
        self.max_retries = 3
        self.retry_delay = 10  # seconds
        self.gas_price_buffer = 1.2  # 20% buffer for replacement transactions

        # Fetch wallet credentials
        self._initialize_credentials()

    def _fetch_secret(self, env_var_name: str, description: str = "") -> Optional[str]:
        """
        Fetch a secret from Google Cloud Secret Manager.

        Args:
            env_var_name: Environment variable containing the secret path
            description: Description for logging purposes

        Returns:
            Secret value or None if failed
        """
        try:
            client = secretmanager.SecretManagerServiceClient()
            secret_path = os.getenv(env_var_name)
            if not secret_path:
                print(f"❌ [WALLET_CONFIG] Environment variable {env_var_name} is not set")
                return None

            print(f"🔐 [WALLET_CONFIG] Fetching {description or env_var_name}")
            response = client.access_secret_version(request={"name": secret_path})
            secret_value = response.payload.data.decode("UTF-8")

            print(f"✅ [WALLET_CONFIG] Successfully fetched {description or env_var_name}")
            return secret_value

        except Exception as e:
            print(f"❌ [WALLET_CONFIG] Error fetching {description or env_var_name}: {e}")
            return None

    def _initialize_credentials(self):
        """Initialize wallet credentials from Secret Manager."""
        try:
            print(f"🔄 [WALLET] Initializing wallet credentials")

            # Fetch wallet credentials from Secret Manager
            self.host_wallet_address = self._fetch_secret("HOST_WALLET_ETH_ADDRESS", "host wallet ETH address")
            self.host_wallet_private_key = self._fetch_secret("HOST_WALLET_PRIVATE_KEY", "host wallet private key")
            self.web3_provider_url = self._fetch_secret("ETHEREUM_RPC_URL", "Ethereum RPC URL")
            self.alchemy_api_key = self._fetch_secret("ETHEREUM_RPC_URL_API", "Ethereum RPC URL API key")

            if not all([self.host_wallet_address, self.host_wallet_private_key, self.web3_provider_url]):
                print(f"❌ [WALLET] Missing required wallet credentials")
                print(f"   Wallet Address: {'✅' if self.host_wallet_address else '❌'}")
                print(f"   Private Key: {'✅' if self.host_wallet_private_key else '❌'}")
                print(f"   Provider URL: {'✅' if self.web3_provider_url else '❌'}")
                print(f"   Alchemy API Key: {'✅' if self.alchemy_api_key else '❌'}")
                return

            print(f"✅ [WALLET] Wallet credentials initialized")
            print(f"🏦 [WALLET] Host Wallet: {self.host_wallet_address}")
            print(f"🌐 [WALLET] Provider URL: {self.web3_provider_url[:50]}...")
            print(f"🔑 [WALLET] Alchemy API Key: {'✅ Configured' if self.alchemy_api_key else '⚠️ Missing'}")

        except Exception as e:
            print(f"❌ [WALLET] Error initializing credentials: {e}")


    def _connect_to_web3(self) -> bool:
        """
        Connect to Web3 provider.

        Returns:
            True if connected successfully, False otherwise
        """
        if not self.web3_provider_url:
            print(f"❌ [WALLET] Web3 provider URL not available")
            return False

        try:
            print(f"🔗 [WALLET] Connecting to Web3 provider")
            self.w3 = Web3(Web3.HTTPProvider(self.web3_provider_url))

            # Add POA middleware for better compatibility
            self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)

            if not self.w3.is_connected():
                print(f"❌ [WALLET] Failed to connect to Web3 provider")
                return False

            print(f"✅ [WALLET] Connected to Web3 provider")
            return True

        except Exception as e:
            print(f"❌ [WALLET] Error connecting to Web3: {e}")
            return False

    def _get_optimized_gas_price(self) -> Dict[str, int]:
        """
        Get optimized gas price using Alchemy's gas manager or Web3 fallback.
        Supports both EIP-1559 and legacy transactions.

        Returns:
            Dictionary with gas prices:
            {
                "maxFeePerGas": int (Wei),
                "maxPriorityFeePerGas": int (Wei),
                "gasPrice": int (Wei) - for legacy transactions
            }
        """
        try:
            # Try to get EIP-1559 gas fees using Web3
            if self.alchemy_api_key:
                try:
                    print(f"⛽ [GAS] Fetching optimized gas prices using EIP-1559")

                    # Use Alchemy's core API for gas prices
                    fee_data = self.w3.eth.fee_history(1, 'latest', [25, 50, 75])

                    if fee_data and 'baseFeePerGas' in fee_data and len(fee_data['baseFeePerGas']) > 1:
                        base_fee = fee_data['baseFeePerGas'][-1]

                        # Use median priority fee from fee history
                        priority_fee = int(fee_data['reward'][-1][1]) if fee_data.get('reward') else self.w3.to_wei(2, 'gwei')

                        # Calculate max fee per gas (base fee * 2 + priority fee)
                        max_fee = (base_fee * 2) + priority_fee

                        print(f"✅ [GAS] EIP-1559 gas prices calculated")
                        print(f"   Base Fee: {self.w3.from_wei(base_fee, 'gwei'):.2f} Gwei")
                        print(f"   Priority Fee: {self.w3.from_wei(priority_fee, 'gwei'):.2f} Gwei")
                        print(f"   Max Fee: {self.w3.from_wei(max_fee, 'gwei'):.2f} Gwei")

                        return {
                            "maxFeePerGas": max_fee,
                            "maxPriorityFeePerGas": priority_fee,
                            "gasPrice": base_fee + priority_fee  # Legacy fallback
                        }
                except Exception as alchemy_err:
                    print(f"⚠️ [GAS] Alchemy gas estimation failed: {alchemy_err}")

            # Fallback to standard Web3 gas price
            print(f"⛽ [GAS] Using standard Web3 gas price")
            gas_price = self.w3.eth.gas_price

            print(f"✅ [GAS] Gas price: {self.w3.from_wei(gas_price, 'gwei'):.2f} Gwei")

            # Return legacy format
            return {
                "maxFeePerGas": gas_price,
                "maxPriorityFeePerGas": self.w3.to_wei(2, 'gwei'),
                "gasPrice": gas_price
            }

        except Exception as e:
            print(f"❌ [GAS] Error getting gas price: {e}")
            # Return safe default
            default_gas = self.w3.to_wei(50, 'gwei')
            return {
                "maxFeePerGas": default_gas,
                "maxPriorityFeePerGas": self.w3.to_wei(2, 'gwei'),
                "gasPrice": default_gas
            }

    def _check_transaction_status(self, tx_hash: str) -> Optional[str]:
        """
        Check if a transaction is pending, mined, or failed.

        Args:
            tx_hash: Transaction hash to check

        Returns:
            "pending", "mined", "failed", or None if error
        """
        try:
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)

            if receipt:
                status = "mined" if receipt['status'] == 1 else "failed"
                print(f"📊 [TX_STATUS] Transaction {tx_hash[:10]}... is {status}")
                return status

        except Exception:
            # Transaction not found in chain yet - likely pending
            try:
                tx = self.w3.eth.get_transaction(tx_hash)
                if tx:
                    print(f"⏳ [TX_STATUS] Transaction {tx_hash[:10]}... is pending")
                    return "pending"
            except Exception:
                pass

        return None

    def _replace_stuck_transaction(self, original_tx_hash: str, to_address: str, amount_wei: int, nonce: int) -> Optional[str]:
        """
        Replace a stuck transaction with higher gas price.

        Args:
            original_tx_hash: Hash of stuck transaction
            to_address: Destination address
            amount_wei: Amount in Wei
            nonce: Same nonce as original transaction

        Returns:
            New transaction hash or None if failed
        """
        try:
            print(f"🔄 [TX_REPLACE] Replacing stuck transaction {original_tx_hash[:10]}...")

            # Get current gas prices and apply buffer
            gas_data = self._get_optimized_gas_price()

            # Increase gas price by buffer (20%)
            new_max_fee = int(gas_data['maxFeePerGas'] * self.gas_price_buffer)
            new_priority_fee = int(gas_data['maxPriorityFeePerGas'] * self.gas_price_buffer)

            print(f"⛽ [TX_REPLACE] New max fee: {self.w3.from_wei(new_max_fee, 'gwei'):.2f} Gwei (+20%)")

            # Build replacement transaction with EIP-1559
            transaction = {
                'nonce': nonce,
                'to': to_address,
                'value': amount_wei,
                'gas': 21000,
                'maxFeePerGas': new_max_fee,
                'maxPriorityFeePerGas': new_priority_fee,
                'chainId': 1
            }

            # Sign and broadcast
            signed_txn = self.w3.eth.account.sign_transaction(transaction, self.host_wallet_private_key)
            new_tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            new_tx_hash_hex = self.w3.to_hex(new_tx_hash)

            print(f"✅ [TX_REPLACE] Replacement transaction broadcasted")
            print(f"🆔 [TX_REPLACE] New TX Hash: {new_tx_hash_hex}")

            return new_tx_hash_hex

        except Exception as e:
            print(f"❌ [TX_REPLACE] Error replacing transaction: {e}")
            return None

    def _send_transaction_with_retry(self, to_address: str, amount_wei: int, unique_id: str) -> Optional[Dict[str, Any]]:
        """
        Send transaction with automatic retry logic for stuck/failed transactions.

        Args:
            to_address: Destination address
            amount_wei: Amount in Wei
            unique_id: Unique transaction ID for logging

        Returns:
            Transaction result dict or None if all retries failed
        """
        for attempt in range(self.max_retries):
            try:
                print(f"🔄 [TX_RETRY] Attempt {attempt + 1}/{self.max_retries}")

                # Get nonce
                nonce = self.w3.eth.get_transaction_count(self.host_wallet_address)
                print(f"🔢 [TX_RETRY] Nonce: {nonce}")

                # Get optimized gas prices
                gas_data = self._get_optimized_gas_price()

                # Build transaction with EIP-1559 support
                transaction = {
                    'nonce': nonce,
                    'to': to_address,
                    'value': amount_wei,
                    'gas': 21000,
                    'maxFeePerGas': gas_data['maxFeePerGas'],
                    'maxPriorityFeePerGas': gas_data['maxPriorityFeePerGas'],
                    'chainId': 1
                }

                print(f"📝 [TX_RETRY] Transaction built (EIP-1559)")

                # Sign transaction
                print(f"🔐 [TX_RETRY] Signing transaction")
                signed_txn = self.w3.eth.account.sign_transaction(transaction, self.host_wallet_private_key)

                # Broadcast transaction
                print(f"📤 [TX_RETRY] Broadcasting transaction")
                tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                tx_hash_hex = self.w3.to_hex(tx_hash)

                print(f"✅ [TX_RETRY] Transaction broadcasted")
                print(f"🆔 [TX_RETRY] TX Hash: {tx_hash_hex}")

                # Wait for confirmation with timeout
                print(f"⏳ [TX_RETRY] Waiting for confirmation (300s timeout)...")

                try:
                    tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

                    status = "success" if tx_receipt['status'] == 1 else "failed"

                    if status == "success":
                        print(f"🎉 [TX_RETRY] Transaction confirmed!")
                        return {
                            "tx_hash": tx_hash_hex,
                            "status": status,
                            "gas_used": tx_receipt['gasUsed'],
                            "block_number": tx_receipt['blockNumber']
                        }
                    else:
                        print(f"❌ [TX_RETRY] Transaction failed on-chain")
                        if attempt < self.max_retries - 1:
                            print(f"⏳ [TX_RETRY] Retrying in {self.retry_delay}s...")
                            time.sleep(self.retry_delay)
                            continue
                        return None

                except Exception as timeout_err:
                    print(f"⏰ [TX_RETRY] Transaction confirmation timeout: {timeout_err}")

                    # Check if transaction is still pending
                    status = self._check_transaction_status(tx_hash_hex)

                    if status == "pending" and attempt < self.max_retries - 1:
                        # Try to replace stuck transaction
                        print(f"🔄 [TX_RETRY] Attempting to replace stuck transaction...")
                        new_tx_hash = self._replace_stuck_transaction(tx_hash_hex, to_address, amount_wei, nonce)

                        if new_tx_hash:
                            tx_hash_hex = new_tx_hash
                            # Wait for new transaction
                            try:
                                tx_receipt = self.w3.eth.wait_for_transaction_receipt(new_tx_hash, timeout=300)
                                return {
                                    "tx_hash": tx_hash_hex,
                                    "status": "success" if tx_receipt['status'] == 1 else "failed",
                                    "gas_used": tx_receipt['gasUsed'],
                                    "block_number": tx_receipt['blockNumber']
                                }
                            except Exception:
                                pass

                    if attempt < self.max_retries - 1:
                        print(f"⏳ [TX_RETRY] Retrying in {self.retry_delay}s...")
                        time.sleep(self.retry_delay)
                        continue

            except ValueError as e:
                error_msg = str(e)
                print(f"❌ [TX_RETRY] Transaction error: {error_msg}")

                # Check for specific errors
                if "nonce too low" in error_msg.lower():
                    print(f"⚠️ [TX_RETRY] Nonce too low - transaction may already be mined")
                    # Don't retry for nonce errors
                    return None
                elif "insufficient funds" in error_msg.lower():
                    print(f"❌ [TX_RETRY] Insufficient funds - cannot retry")
                    return None
                elif "replacement transaction underpriced" in error_msg.lower():
                    print(f"⚠️ [TX_RETRY] Replacement underpriced - increasing gas buffer")
                    self.gas_price_buffer += 0.1  # Increase buffer by 10%

                if attempt < self.max_retries - 1:
                    print(f"⏳ [TX_RETRY] Retrying in {self.retry_delay}s...")
                    time.sleep(self.retry_delay)
                    continue

            except Exception as e:
                print(f"❌ [TX_RETRY] Unexpected error: {e}")
                if attempt < self.max_retries - 1:
                    print(f"⏳ [TX_RETRY] Retrying in {self.retry_delay}s...")
                    time.sleep(self.retry_delay)
                    continue

        print(f"❌ [TX_RETRY] All {self.max_retries} retry attempts failed")
        return None

    def send_eth_payment(self, to_address: str, amount: float, unique_id: str) -> Optional[Dict[str, Any]]:
        """
        Send ETH payment from host wallet to ChangeNow payin address.
        Enhanced with Alchemy gas optimization and automatic retry logic.

        Args:
            to_address: ChangeNow payin address (ETH address)
            amount: Amount of ETH to send (as float)
            unique_id: Unique transaction ID for logging

        Returns:
            Dictionary with transaction details:
            {
                "tx_hash": "0x...",
                "status": "success" | "failed",
                "gas_used": int,
                "block_number": int
            }
            Returns None if payment execution failed
        """
        try:
            # Verify credentials are available
            if not all([self.host_wallet_address, self.host_wallet_private_key, self.web3_provider_url]):
                print(f"❌ [ETH_PAYMENT] Missing required credentials")
                print(f"   Wallet Address: {'✅' if self.host_wallet_address else '❌'}")
                print(f"   Private Key: {'✅' if self.host_wallet_private_key else '❌'}")
                print(f"   Provider URL: {'✅' if self.web3_provider_url else '❌'}")
                return None

            # Connect to Web3 (if not already connected)
            if not self.w3 or not self.w3.is_connected():
                if not self._connect_to_web3():
                    return None

            print(f"💰 [ETH_PAYMENT] Initiating ETH payment for transaction: {unique_id}")
            print(f"🏦 [ETH_PAYMENT] From: {self.host_wallet_address}")
            print(f"🏦 [ETH_PAYMENT] To: {to_address}")
            print(f"💸 [ETH_PAYMENT] Amount: {amount} ETH")

            # Convert ETH amount to Wei
            amount_wei = self.w3.to_wei(amount, 'ether')
            print(f"💸 [ETH_PAYMENT] Amount in Wei: {amount_wei}")

            # Use retry logic for robust transaction execution
            result = self._send_transaction_with_retry(to_address, amount_wei, unique_id)

            if result:
                print(f"🎉 [ETH_PAYMENT] Payment completed successfully!")
                print(f"   TX Hash: {result['tx_hash']}")
                print(f"   Status: {result['status']}")
                print(f"   Gas Used: {result['gas_used']}")
                print(f"   Block Number: {result['block_number']}")

            return result

        except Exception as e:
            # General exception handling
            print(f"❌ [ETH_PAYMENT] Error sending ETH payment: {e}")
            import traceback
            print(f"📄 [ETH_PAYMENT] Traceback: {traceback.format_exc()}")
            return None

    def get_wallet_balance(self) -> Optional[float]:
        """
        Get the current ETH balance of the host wallet.

        Returns:
            ETH balance as float, or None if failed
        """
        try:
            if not self.host_wallet_address:
                print(f"❌ [WALLET] Host wallet address not available")
                return None

            # Connect to Web3 if not already connected
            if not self.w3 or not self.w3.is_connected():
                if not self._connect_to_web3():
                    return None

            # Get balance in Wei
            balance_wei = self.w3.eth.get_balance(self.host_wallet_address)

            # Convert to ETH
            balance_eth = self.w3.from_wei(balance_wei, 'ether')

            print(f"💰 [WALLET] Host wallet balance: {balance_eth} ETH")
            return float(balance_eth)

        except Exception as e:
            print(f"❌ [WALLET] Error getting wallet balance: {e}")
            return None

    def validate_eth_address(self, address: str) -> bool:
        """
        Validate if a string is a valid Ethereum address.

        Args:
            address: Address to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            # Connect to Web3 if not already connected
            if not self.w3 or not self.w3.is_connected():
                if not self._connect_to_web3():
                    # If we can't connect to Web3, fall back to basic validation
                    return address.startswith('0x') and len(address) == 42

            # Use Web3's built-in address validation
            is_valid = self.w3.is_address(address)

            if is_valid:
                print(f"✅ [WALLET] Address validation passed: {address}")
            else:
                print(f"❌ [WALLET] Invalid Ethereum address: {address}")

            return is_valid

        except Exception as e:
            print(f"❌ [WALLET] Error validating address: {e}")
            return False

    def estimate_gas_cost(self, to_address: str, amount: float) -> Optional[Dict[str, Any]]:
        """
        Estimate the gas cost for an ETH transfer using Alchemy-enhanced estimation.
        Provides both EIP-1559 and legacy gas estimates.

        Args:
            to_address: Destination address
            amount: Amount of ETH to send

        Returns:
            Dictionary with gas estimates:
            {
                "gas_limit": 21000,
                "gas_price_gwei": float (legacy),
                "gas_cost_eth": float (legacy),
                "total_cost_eth": float (legacy),
                "eip1559_max_fee_gwei": float,
                "eip1559_priority_fee_gwei": float,
                "eip1559_gas_cost_eth": float,
                "eip1559_total_cost_eth": float
            }
            Returns None if estimation failed
        """
        try:
            # Connect to Web3 if not already connected
            if not self.w3 or not self.w3.is_connected():
                if not self._connect_to_web3():
                    return None

            print(f"⛽ [WALLET] Estimating gas costs with Alchemy optimization")

            # Get optimized gas prices
            gas_data = self._get_optimized_gas_price()

            # Standard ETH transfer gas limit
            gas_limit = 21000

            # Legacy gas calculation
            legacy_gas_price = gas_data['gasPrice']
            legacy_gas_price_gwei = float(self.w3.from_wei(legacy_gas_price, 'gwei'))
            legacy_gas_cost_wei = legacy_gas_price * gas_limit
            legacy_gas_cost_eth = float(self.w3.from_wei(legacy_gas_cost_wei, 'ether'))
            legacy_total_cost_eth = amount + legacy_gas_cost_eth

            # EIP-1559 gas calculation
            eip1559_max_fee = gas_data['maxFeePerGas']
            eip1559_priority_fee = gas_data['maxPriorityFeePerGas']
            eip1559_max_fee_gwei = float(self.w3.from_wei(eip1559_max_fee, 'gwei'))
            eip1559_priority_fee_gwei = float(self.w3.from_wei(eip1559_priority_fee, 'gwei'))
            eip1559_gas_cost_wei = eip1559_max_fee * gas_limit
            eip1559_gas_cost_eth = float(self.w3.from_wei(eip1559_gas_cost_wei, 'ether'))
            eip1559_total_cost_eth = amount + eip1559_gas_cost_eth

            print(f"✅ [WALLET] Gas estimation complete:")
            print(f"   Gas Limit: {gas_limit}")
            print(f"   ")
            print(f"   Legacy (Pre-EIP-1559):")
            print(f"     Gas Price: {legacy_gas_price_gwei:.2f} Gwei")
            print(f"     Gas Cost: {legacy_gas_cost_eth:.6f} ETH")
            print(f"     Total Cost: {legacy_total_cost_eth:.6f} ETH")
            print(f"   ")
            print(f"   EIP-1559 (Recommended):")
            print(f"     Max Fee: {eip1559_max_fee_gwei:.2f} Gwei")
            print(f"     Priority Fee: {eip1559_priority_fee_gwei:.2f} Gwei")
            print(f"     Gas Cost: {eip1559_gas_cost_eth:.6f} ETH")
            print(f"     Total Cost: {eip1559_total_cost_eth:.6f} ETH")
            print(f"   ")
            print(f"   Transfer Amount: {amount} ETH")

            return {
                "gas_limit": gas_limit,
                # Legacy
                "gas_price_gwei": legacy_gas_price_gwei,
                "gas_cost_eth": legacy_gas_cost_eth,
                "total_cost_eth": legacy_total_cost_eth,
                # EIP-1559
                "eip1559_max_fee_gwei": eip1559_max_fee_gwei,
                "eip1559_priority_fee_gwei": eip1559_priority_fee_gwei,
                "eip1559_gas_cost_eth": eip1559_gas_cost_eth,
                "eip1559_total_cost_eth": eip1559_total_cost_eth
            }

        except Exception as e:
            print(f"❌ [WALLET] Error estimating gas cost: {e}")
            return None
