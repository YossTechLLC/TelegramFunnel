#!/usr/bin/env python
"""
Ethereum Wallet Manager for HPW10-9 Host Payment Wallet Service.
Handles all Ethereum blockchain interactions including balance checking,
transaction creation, signing, and broadcasting.
"""
from web3 import Web3
from eth_account import Account
from decimal import Decimal
from typing import Optional, Dict, Any, Tuple
import time


class EthWalletManager:
    """
    Manages Ethereum wallet operations for the host payment service.
    """

    def __init__(self, node_url: str, wallet_address: str, private_key: str):
        """
        Initialize the Ethereum wallet manager.

        Args:
            node_url: Ethereum node RPC URL (Infura/Alchemy)
            wallet_address: Host wallet Ethereum address
            private_key: Host wallet private key (KEEP SECURE!)
        """
        self.w3 = Web3(Web3.HTTPProvider(node_url))
        self.wallet_address = Web3.to_checksum_address(wallet_address)
        self.private_key = private_key

        # Validate connection
        if not self.w3.is_connected():
            raise ConnectionError(f"❌ [ETH_WALLET] Failed to connect to Ethereum node: {node_url}")

        print(f"✅ [ETH_WALLET] Connected to Ethereum node")
        print(f"🏦 [ETH_WALLET] Wallet address: {self.wallet_address}")

        # Verify private key matches address
        account = Account.from_key(private_key)
        if account.address.lower() != self.wallet_address.lower():
            raise ValueError(f"❌ [ETH_WALLET] Private key does not match wallet address!")

        print(f"🔐 [ETH_WALLET] Private key validated successfully")

    def get_balance(self) -> Decimal:
        """
        Get the ETH balance of the host wallet.

        Returns:
            Balance in ETH as Decimal
        """
        try:
            balance_wei = self.w3.eth.get_balance(self.wallet_address)
            balance_eth = Decimal(self.w3.from_wei(balance_wei, 'ether'))
            print(f"💰 [ETH_WALLET] Current balance: {balance_eth} ETH")
            return balance_eth

        except Exception as e:
            print(f"❌ [ETH_WALLET] Error getting balance: {e}")
            return Decimal('0')

    def estimate_gas_price(self) -> Tuple[int, int]:
        """
        Estimate current gas price using EIP-1559.

        Returns:
            Tuple of (max_fee_per_gas, max_priority_fee_per_gas) in Wei
        """
        try:
            # Get latest block to estimate base fee
            latest_block = self.w3.eth.get_block('latest')
            base_fee = latest_block.get('baseFeePerGas', 0)

            # Get suggested priority fee
            max_priority_fee = self.w3.eth.max_priority_fee

            # Calculate max fee (base fee + priority fee + buffer)
            # Add 20% buffer for base fee volatility
            max_fee_per_gas = int(base_fee * 1.2 + max_priority_fee)

            print(f"⛽ [ETH_WALLET] Gas estimate:")
            print(f"   Base fee: {self.w3.from_wei(base_fee, 'gwei'):.2f} Gwei")
            print(f"   Priority fee: {self.w3.from_wei(max_priority_fee, 'gwei'):.2f} Gwei")
            print(f"   Max fee: {self.w3.from_wei(max_fee_per_gas, 'gwei'):.2f} Gwei")

            return max_fee_per_gas, max_priority_fee

        except Exception as e:
            print(f"❌ [ETH_WALLET] Error estimating gas price: {e}")
            # Fallback to legacy gas price
            gas_price = self.w3.eth.gas_price
            return gas_price, 0

    def estimate_transaction_cost(self, to_address: str, amount_eth: Decimal) -> Tuple[Decimal, int, int]:
        """
        Estimate the total cost of a transaction including gas.

        Args:
            to_address: Recipient address
            amount_eth: Amount in ETH

        Returns:
            Tuple of (total_cost_eth, gas_limit, max_fee_per_gas)
        """
        try:
            to_address = Web3.to_checksum_address(to_address)
            amount_wei = self.w3.to_wei(amount_eth, 'ether')

            # Get gas estimates
            max_fee_per_gas, max_priority_fee = self.estimate_gas_price()

            # Estimate gas limit for ETH transfer (standard is 21000)
            gas_limit = 21000

            # Try to estimate actual gas usage
            try:
                gas_estimate = self.w3.eth.estimate_gas({
                    'from': self.wallet_address,
                    'to': to_address,
                    'value': amount_wei
                })
                gas_limit = int(gas_estimate * 1.1)  # Add 10% buffer
            except Exception:
                print(f"⚠️ [ETH_WALLET] Using default gas limit: {gas_limit}")

            # Calculate total gas cost
            gas_cost_wei = gas_limit * max_fee_per_gas
            gas_cost_eth = Decimal(self.w3.from_wei(gas_cost_wei, 'ether'))

            # Calculate total cost
            total_cost_eth = amount_eth + gas_cost_eth

            print(f"💸 [ETH_WALLET] Transaction cost estimate:")
            print(f"   Amount: {amount_eth} ETH")
            print(f"   Gas limit: {gas_limit}")
            print(f"   Gas cost: {gas_cost_eth} ETH ({self.w3.from_wei(max_fee_per_gas, 'gwei'):.2f} Gwei)")
            print(f"   Total cost: {total_cost_eth} ETH")

            return total_cost_eth, gas_limit, max_fee_per_gas

        except Exception as e:
            print(f"❌ [ETH_WALLET] Error estimating transaction cost: {e}")
            # Return conservative estimate
            return amount_eth + Decimal('0.001'), 21000, self.w3.eth.gas_price

    def validate_address(self, address: str) -> bool:
        """
        Validate an Ethereum address.

        Args:
            address: Ethereum address to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            checksum_address = Web3.to_checksum_address(address)
            is_valid = self.w3.is_address(checksum_address)

            if is_valid:
                print(f"✅ [ETH_WALLET] Valid address: {checksum_address}")
            else:
                print(f"❌ [ETH_WALLET] Invalid address: {address}")

            return is_valid

        except Exception as e:
            print(f"❌ [ETH_WALLET] Address validation error: {e}")
            return False

    def send_transaction(self, to_address: str, amount_eth: Decimal) -> Optional[Dict[str, Any]]:
        """
        Create, sign, and broadcast an Ethereum transaction.

        Args:
            to_address: Recipient address
            amount_eth: Amount to send in ETH

        Returns:
            Transaction details dict or None if failed
        """
        try:
            # Validate recipient address
            if not self.validate_address(to_address):
                print(f"❌ [ETH_WALLET] Invalid recipient address: {to_address}")
                return None

            to_address = Web3.to_checksum_address(to_address)
            amount_wei = self.w3.to_wei(amount_eth, 'ether')

            # Check sufficient balance
            balance = self.get_balance()
            total_cost, gas_limit, max_fee_per_gas = self.estimate_transaction_cost(to_address, amount_eth)

            if balance < total_cost:
                print(f"❌ [ETH_WALLET] Insufficient balance: {balance} ETH < {total_cost} ETH")
                return None

            # Get nonce
            nonce = self.w3.eth.get_transaction_count(self.wallet_address, 'pending')
            print(f"🔢 [ETH_WALLET] Using nonce: {nonce}")

            # Get gas prices
            max_fee_per_gas, max_priority_fee = self.estimate_gas_price()

            # Build transaction (EIP-1559)
            transaction = {
                'from': self.wallet_address,
                'to': to_address,
                'value': amount_wei,
                'gas': gas_limit,
                'maxFeePerGas': max_fee_per_gas,
                'maxPriorityFeePerGas': max_priority_fee,
                'nonce': nonce,
                'chainId': self.w3.eth.chain_id
            }

            print(f"📝 [ETH_WALLET] Transaction details:")
            print(f"   From: {transaction['from']}")
            print(f"   To: {transaction['to']}")
            print(f"   Value: {amount_eth} ETH")
            print(f"   Gas limit: {transaction['gas']}")
            print(f"   Max fee: {self.w3.from_wei(transaction['maxFeePerGas'], 'gwei'):.2f} Gwei")
            print(f"   Nonce: {transaction['nonce']}")
            print(f"   Chain ID: {transaction['chainId']}")

            # Sign transaction
            signed_txn = self.w3.eth.account.sign_transaction(transaction, self.private_key)
            print(f"🔐 [ETH_WALLET] Transaction signed successfully")

            # Broadcast transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            tx_hash_hex = tx_hash.hex()

            print(f"🚀 [ETH_WALLET] Transaction broadcasted!")
            print(f"📋 [ETH_WALLET] TX Hash: {tx_hash_hex}")

            # Return transaction details
            return {
                'tx_hash': tx_hash_hex,
                'from': self.wallet_address,
                'to': to_address,
                'value_eth': str(amount_eth),
                'gas_limit': gas_limit,
                'max_fee_per_gas': max_fee_per_gas,
                'max_priority_fee': max_priority_fee,
                'nonce': nonce,
                'gas_price_gwei': float(self.w3.from_wei(max_fee_per_gas, 'gwei'))
            }

        except Exception as e:
            print(f"❌ [ETH_WALLET] Error sending transaction: {e}")
            return None

    def get_transaction_receipt(self, tx_hash: str, timeout: int = 120) -> Optional[Dict[str, Any]]:
        """
        Get transaction receipt and wait for confirmation.

        Args:
            tx_hash: Transaction hash
            timeout: Timeout in seconds (default: 120)

        Returns:
            Transaction receipt dict or None if failed
        """
        try:
            print(f"⏳ [ETH_WALLET] Waiting for transaction confirmation: {tx_hash}")

            # Wait for transaction receipt
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)

            status = receipt.get('status', 0)
            gas_used = receipt.get('gasUsed', 0)
            block_number = receipt.get('blockNumber', 0)
            effective_gas_price = receipt.get('effectiveGasPrice', 0)

            if status == 1:
                print(f"✅ [ETH_WALLET] Transaction confirmed!")
                print(f"   Block: {block_number}")
                print(f"   Gas used: {gas_used}")
                print(f"   Effective gas price: {self.w3.from_wei(effective_gas_price, 'gwei'):.2f} Gwei")
            else:
                print(f"❌ [ETH_WALLET] Transaction failed!")

            return {
                'tx_hash': tx_hash,
                'status': status,
                'block_number': block_number,
                'gas_used': gas_used,
                'effective_gas_price': effective_gas_price,
                'gas_price_gwei': float(self.w3.from_wei(effective_gas_price, 'gwei'))
            }

        except Exception as e:
            print(f"❌ [ETH_WALLET] Error getting transaction receipt: {e}")
            return None

    def get_transaction_status(self, tx_hash: str) -> str:
        """
        Check the status of a transaction without waiting.

        Args:
            tx_hash: Transaction hash

        Returns:
            Status string: 'pending', 'confirmed', 'failed', or 'not_found'
        """
        try:
            # Try to get receipt
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)

            if receipt:
                status = receipt.get('status', 0)
                if status == 1:
                    return 'confirmed'
                else:
                    return 'failed'
            else:
                return 'not_found'

        except Exception:
            # Transaction exists but not mined yet
            try:
                tx = self.w3.eth.get_transaction(tx_hash)
                if tx:
                    return 'pending'
                else:
                    return 'not_found'
            except Exception:
                return 'not_found'

    def get_current_nonce(self) -> int:
        """
        Get the current nonce for the wallet.

        Returns:
            Current nonce
        """
        try:
            nonce = self.w3.eth.get_transaction_count(self.wallet_address, 'pending')
            print(f"🔢 [ETH_WALLET] Current nonce: {nonce}")
            return nonce

        except Exception as e:
            print(f"❌ [ETH_WALLET] Error getting nonce: {e}")
            return 0

    def get_network_info(self) -> Dict[str, Any]:
        """
        Get current Ethereum network information.

        Returns:
            Network info dictionary
        """
        try:
            chain_id = self.w3.eth.chain_id
            latest_block = self.w3.eth.block_number
            gas_price = self.w3.eth.gas_price

            network_map = {
                1: 'Mainnet',
                5: 'Goerli',
                11155111: 'Sepolia'
            }

            network_name = network_map.get(chain_id, f'Unknown (Chain ID: {chain_id})')

            print(f"🌐 [ETH_WALLET] Network info:")
            print(f"   Network: {network_name}")
            print(f"   Chain ID: {chain_id}")
            print(f"   Latest block: {latest_block}")
            print(f"   Gas price: {self.w3.from_wei(gas_price, 'gwei'):.2f} Gwei")

            return {
                'network_name': network_name,
                'chain_id': chain_id,
                'latest_block': latest_block,
                'gas_price_gwei': float(self.w3.from_wei(gas_price, 'gwei'))
            }

        except Exception as e:
            print(f"❌ [ETH_WALLET] Error getting network info: {e}")
            return {}
