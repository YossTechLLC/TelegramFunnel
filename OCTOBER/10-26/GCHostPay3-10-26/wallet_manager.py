#!/usr/bin/env python
"""
Wallet Manager for GCHostPay3-10-26 (ETH Payment Executor Service).
Handles Web3 wallet operations with INFINITE RETRY logic.

Implements resilience against:
- RPC timeouts
- Connection errors
- Gas estimation failures
- Nonce issues
- Network congestion

Retry Strategy:
- Fixed 60-second backoff between retries
- Infinite retries (-1 max_attempts)
- 24-hour max retry duration (handled by Cloud Tasks)
"""
import time
from typing import Optional, Dict, Any
from web3 import Web3
from web3.middleware import geth_poa_middleware


class WalletManager:
    """
    Manages Web3 wallet operations with infinite retry logic.
    """

    def __init__(self, wallet_address: str, private_key: str, rpc_url: str, alchemy_api_key: Optional[str] = None):
        """
        Initialize WalletManager.

        Args:
            wallet_address: Host wallet ETH address (checksum format)
            private_key: Host wallet private key
            rpc_url: Ethereum RPC provider URL
            alchemy_api_key: Optional Alchemy API key for gas optimization
        """
        self.wallet_address = Web3.to_checksum_address(wallet_address)
        self.private_key = private_key
        self.rpc_url = rpc_url
        self.alchemy_api_key = alchemy_api_key
        self.w3 = None
        self.gas_price_buffer = 1.2  # 20% buffer for replacement transactions

        print(f"✅ [WALLET] WalletManager initialized")
        print(f"🏦 [WALLET] Wallet: {self.wallet_address}")

        # Connect to Web3
        self._connect_to_web3()

    def _connect_to_web3(self) -> bool:
        """Connect to Web3 provider."""
        try:
            print(f"🔗 [WALLET] Connecting to Web3 provider")
            self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))

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
        Get optimized gas price using EIP-1559 or fallback to legacy.

        Returns:
            Dictionary with gas prices (maxFeePerGas, maxPriorityFeePerGas, gasPrice)
        """
        try:
            # Try EIP-1559 gas fees
            if self.alchemy_api_key:
                try:
                    print(f"⛽ [GAS] Fetching EIP-1559 gas prices")

                    fee_data = self.w3.eth.fee_history(1, 'latest', [25, 50, 75])

                    if fee_data and 'baseFeePerGas' in fee_data and len(fee_data['baseFeePerGas']) > 1:
                        base_fee = fee_data['baseFeePerGas'][-1]
                        priority_fee = int(fee_data['reward'][-1][1]) if fee_data.get('reward') else self.w3.to_wei(2, 'gwei')
                        max_fee = (base_fee * 2) + priority_fee

                        print(f"✅ [GAS] EIP-1559 gas prices calculated")
                        print(f"   Base Fee: {self.w3.from_wei(base_fee, 'gwei'):.2f} Gwei")
                        print(f"   Priority Fee: {self.w3.from_wei(priority_fee, 'gwei'):.2f} Gwei")
                        print(f"   Max Fee: {self.w3.from_wei(max_fee, 'gwei'):.2f} Gwei")

                        return {
                            "maxFeePerGas": max_fee,
                            "maxPriorityFeePerGas": priority_fee,
                            "gasPrice": base_fee + priority_fee
                        }
                except Exception:
                    pass

            # Fallback to standard gas price
            print(f"⛽ [GAS] Using standard Web3 gas price")
            gas_price = self.w3.eth.gas_price

            print(f"✅ [GAS] Gas price: {self.w3.from_wei(gas_price, 'gwei'):.2f} Gwei")

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

    def send_eth_payment_with_infinite_retry(
        self,
        to_address: str,
        amount: float,
        unique_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Send ETH payment with SINGLE ATTEMPT (NEW: No infinite retry).

        UPDATED: Removed infinite retry loop. Now raises exceptions on failure.
        Retry logic handled by GCHostPay3 main service (3-attempt limit).

        Args:
            to_address: Destination address (ChangeNow payin address)
            amount: Amount of ETH to send (as float)
            unique_id: Unique transaction ID for logging

        Returns:
            Dictionary with transaction details:
            {
                "tx_hash": "0x...",
                "status": "success",
                "gas_used": int,
                "block_number": int
            }

        Raises:
            ValueError: If address is invalid or amount is invalid
            Exception: For all other payment failures (network, gas, confirmation, etc.)
        """
        print(f"💰 [ETH_PAYMENT] Starting ETH payment (single attempt)")
        print(f"🆔 [ETH_PAYMENT] Unique ID: {unique_id}")
        print(f"🏦 [ETH_PAYMENT] From: {self.wallet_address}")
        print(f"🏦 [ETH_PAYMENT] To: {to_address}")
        print(f"💸 [ETH_PAYMENT] Amount: {amount} ETH")

        # Convert to checksum address
        try:
            to_address_checksum = self.w3.to_checksum_address(to_address)
        except Exception as e:
            print(f"❌ [ETH_PAYMENT] Invalid destination address: {e}")
            raise ValueError(f"Invalid destination address: {e}")

        # Convert ETH to Wei
        amount_wei = self.w3.to_wei(amount, 'ether')
        print(f"💸 [ETH_PAYMENT] Amount in Wei: {amount_wei}")

        # Validate amount
        if amount_wei <= 0:
            raise ValueError(f"Invalid amount: {amount} ETH (must be positive)")

        # Single attempt (NO RETRY)
        try:
            # Check connection
            if not self.w3 or not self.w3.is_connected():
                print(f"🔗 [ETH_PAYMENT] Reconnecting to Web3")
                if not self._connect_to_web3():
                    raise Exception("Failed to connect to Ethereum RPC endpoint")

            # Get nonce
            nonce = self.w3.eth.get_transaction_count(self.wallet_address)
            print(f"🔢 [ETH_PAYMENT] Nonce: {nonce}")

            # Get optimized gas prices
            gas_data = self._get_optimized_gas_price()

            # Build transaction with EIP-1559
            transaction = {
                'nonce': nonce,
                'to': to_address_checksum,
                'value': amount_wei,
                'gas': 21000,
                'maxFeePerGas': gas_data['maxFeePerGas'],
                'maxPriorityFeePerGas': gas_data['maxPriorityFeePerGas'],
                'chainId': 1
            }

            print(f"📝 [ETH_PAYMENT] Transaction built (EIP-1559)")

            # Sign transaction
            print(f"🔐 [ETH_PAYMENT] Signing transaction")
            signed_txn = self.w3.eth.account.sign_transaction(transaction, self.private_key)

            # Broadcast transaction
            print(f"📤 [ETH_PAYMENT] Broadcasting transaction")
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            tx_hash_hex = self.w3.to_hex(tx_hash)

            print(f"✅ [ETH_PAYMENT] Transaction broadcasted")
            print(f"🆔 [ETH_PAYMENT] TX Hash: {tx_hash_hex}")

            # Wait for confirmation with timeout
            print(f"⏳ [ETH_PAYMENT] Waiting for confirmation (300s timeout)...")

            try:
                tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

                status = "success" if tx_receipt['status'] == 1 else "failed"

                if status == "success":
                    print(f"🎉 [ETH_PAYMENT] Transaction confirmed!")

                    return {
                        "tx_hash": tx_hash_hex,
                        "status": status,
                        "gas_used": tx_receipt['gasUsed'],
                        "block_number": tx_receipt['blockNumber']
                    }
                else:
                    # Transaction reverted on-chain
                    print(f"❌ [ETH_PAYMENT] Transaction failed on-chain (reverted)")
                    raise Exception(f"Transaction reverted on-chain: {tx_hash_hex}")

            except Exception as timeout_err:
                # Confirmation timeout (transaction may still be pending)
                print(f"⏰ [ETH_PAYMENT] Transaction confirmation timeout: {timeout_err}")
                raise Exception(f"Transaction confirmation timeout after 300s: {tx_hash_hex}")

        except ValueError as e:
            # Value errors (nonce, insufficient funds, etc.)
            error_msg = str(e)
            print(f"❌ [ETH_PAYMENT] Transaction error: {error_msg}")
            raise  # Re-raise ValueError for classification

        except Exception as e:
            # All other errors (network, gas, etc.)
            print(f"❌ [ETH_PAYMENT] Payment execution error: {e}")
            raise  # Re-raise for classification
