#!/usr/bin/env python
"""
Ethereum Wallet Manager for TelegramFunnel
Handles ETH transactions and wallet operations
"""
import os
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple
from web3 import Web3
from eth_account import Account
from google.cloud import secretmanager


class ETHWalletManager:
    def __init__(self, private_key: str = None, rpc_url: str = None):
        """
        Initialize the Ethereum Wallet Manager.
        
        Args:
            private_key: Ethereum wallet private key. If None, will fetch from Secret Manager
            rpc_url: Ethereum RPC endpoint. Defaults to Infura mainnet
        """
        self.private_key = private_key or self.fetch_eth_private_key()
        self.rpc_url = rpc_url or "https://mainnet.infura.io/v3/YOUR_INFURA_PROJECT_ID"
        
        if not self.private_key:
            raise ValueError("Ethereum private key is required")
        
        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        if not self.w3.is_connected():
            raise ConnectionError("Failed to connect to Ethereum network")
        
        # Create account from private key
        self.account = Account.from_key(self.private_key)
        self.wallet_address = self.account.address
        
        print(f"🔗 [INFO] ETH Wallet Manager initialized")
        print(f"📍 [INFO] Wallet address: {self.wallet_address}")
        print(f"🌐 [INFO] Connected to Ethereum network: {self.w3.is_connected()}")
    
    def fetch_eth_private_key(self) -> Optional[str]:
        """Fetch Ethereum private key from Google Secret Manager."""
        try:
            client = secretmanager.SecretManagerServiceClient()
            secret_path = os.getenv("HOST_WALLET_PRIVATE_KEY")
            if not secret_path:
                raise ValueError("Environment variable HOST_WALLET_PRIVATE_KEY is not set")
            response = client.access_secret_version(request={"name": secret_path})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            print(f"❌ [ERROR] Failed to fetch ETH private key: {e}")
            return None
    
    def fetch_eth_address(self) -> Optional[str]:
        """Fetch Ethereum wallet address from Google Secret Manager (for verification)."""
        try:
            client = secretmanager.SecretManagerServiceClient()
            secret_path = os.getenv("HOST_WALLET_ETH_ADDRESS")
            if not secret_path:
                print("⚠️ [WARNING] HOST_WALLET_ETH_ADDRESS not set - using derived address")
                return None
            response = client.access_secret_version(request={"name": secret_path})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            print(f"❌ [ERROR] Failed to fetch ETH address: {e}")
            return None
    
    def get_balance(self) -> Tuple[float, str]:
        """
        Get ETH balance of the wallet.
        
        Returns:
            Tuple of (balance_eth, balance_wei_str)
        """
        try:
            balance_wei = self.w3.eth.get_balance(self.wallet_address)
            balance_eth = self.w3.from_wei(balance_wei, 'ether')
            balance_eth_float = float(balance_eth)
            
            print(f"💰 [DEBUG] Wallet balance: {balance_eth_float:.6f} ETH ({balance_wei} wei)")
            return balance_eth_float, str(balance_wei)
            
        except Exception as e:
            print(f"❌ [ERROR] Failed to get wallet balance: {e}")
            return 0.0, "0"
    
    def estimate_gas(self, to_address: str, value_wei: int) -> Dict[str, Any]:
        """
        Estimate gas for an ETH transaction.
        
        Args:
            to_address: Recipient address
            value_wei: Amount in wei
            
        Returns:
            Dictionary with gas estimation data
        """
        try:
            # Get current gas price
            gas_price = self.w3.eth.gas_price
            
            # Estimate gas limit
            gas_estimate = self.w3.eth.estimate_gas({
                'from': self.wallet_address,
                'to': to_address,
                'value': value_wei
            })
            
            # Add 20% buffer for gas limit
            gas_limit = int(gas_estimate * 1.2)
            
            # Calculate total gas cost
            gas_cost_wei = gas_price * gas_limit
            gas_cost_eth = float(self.w3.from_wei(gas_cost_wei, 'ether'))
            
            print(f"⛽ [DEBUG] Gas estimation: limit={gas_limit}, price={gas_price} wei, cost={gas_cost_eth:.6f} ETH")
            
            return {
                "success": True,
                "gas_limit": gas_limit,
                "gas_price": gas_price,
                "gas_cost_wei": gas_cost_wei,
                "gas_cost_eth": gas_cost_eth
            }
            
        except Exception as e:
            error_msg = f"Gas estimation failed: {str(e)}"
            print(f"❌ [ERROR] {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    def validate_eth_address(self, address: str) -> bool:
        """
        Validate Ethereum address format.
        
        Args:
            address: Address to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            is_valid = self.w3.is_address(address)
            if is_valid:
                # Convert to checksum address for additional validation
                checksum_address = self.w3.to_checksum_address(address)
                print(f"✅ [DEBUG] Valid ETH address: {checksum_address}")
            else:
                print(f"❌ [DEBUG] Invalid ETH address: {address}")
            return is_valid
        except Exception as e:
            print(f"❌ [ERROR] Address validation failed: {e}")
            return False
    
    async def send_eth(self, to_address: str, amount_eth: float, 
                      gas_price_gwei: Optional[float] = None) -> Dict[str, Any]:
        """
        Send ETH to a specified address.
        
        Args:
            to_address: Recipient address
            amount_eth: Amount in ETH to send
            gas_price_gwei: Optional custom gas price in Gwei
            
        Returns:
            Dictionary with transaction result
        """
        try:
            # Validate recipient address
            if not self.validate_eth_address(to_address):
                return {
                    "success": False,
                    "error": f"Invalid recipient address: {to_address}"
                }
            
            # Convert amount to wei
            amount_wei = self.w3.to_wei(Decimal(str(amount_eth)), 'ether')
            
            # Check wallet balance
            balance_eth, _ = self.get_balance()
            if balance_eth < amount_eth:
                return {
                    "success": False,
                    "error": f"Insufficient balance: {balance_eth:.6f} ETH < {amount_eth:.6f} ETH"
                }
            
            # Estimate gas
            gas_estimation = self.estimate_gas(to_address, amount_wei)
            if not gas_estimation["success"]:
                return {
                    "success": False,
                    "error": f"Gas estimation failed: {gas_estimation['error']}"
                }
            
            # Check if we have enough ETH for amount + gas
            total_needed_eth = amount_eth + gas_estimation["gas_cost_eth"]
            if balance_eth < total_needed_eth:
                return {
                    "success": False,
                    "error": f"Insufficient balance for amount + gas: {balance_eth:.6f} ETH < {total_needed_eth:.6f} ETH"
                }
            
            # Set gas price
            if gas_price_gwei:
                gas_price = self.w3.to_wei(gas_price_gwei, 'gwei')
            else:
                gas_price = gas_estimation["gas_price"]
            
            # Get nonce
            nonce = self.w3.eth.get_transaction_count(self.wallet_address)
            
            # Build transaction
            transaction = {
                'nonce': nonce,
                'to': self.w3.to_checksum_address(to_address),
                'value': amount_wei,
                'gas': gas_estimation["gas_limit"],
                'gasPrice': gas_price,
                'chainId': 1  # Ethereum mainnet
            }
            
            print(f"🔄 [DEBUG] Preparing ETH transaction:")
            print(f"💰 [DEBUG] Amount: {amount_eth} ETH ({amount_wei} wei)")
            print(f"📍 [DEBUG] To: {to_address}")
            print(f"⛽ [DEBUG] Gas: {gas_estimation['gas_limit']} @ {gas_price} wei")
            print(f"🔢 [DEBUG] Nonce: {nonce}")
            
            # Sign transaction
            signed_txn = self.w3.eth.account.sign_transaction(transaction, self.private_key)
            
            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            tx_hash_hex = tx_hash.hex()
            
            print(f"🚀 [SUCCESS] ETH transaction sent successfully")
            print(f"🔗 [INFO] Transaction hash: {tx_hash_hex}")
            print(f"📊 [INFO] Amount sent: {amount_eth} ETH to {to_address}")
            
            return {
                "success": True,
                "tx_hash": tx_hash_hex,
                "amount_eth": amount_eth,
                "amount_wei": str(amount_wei),
                "to_address": to_address,
                "gas_used": gas_estimation["gas_limit"],
                "gas_price": gas_price,
                "nonce": nonce
            }
            
        except Exception as e:
            error_msg = f"ETH transaction failed: {str(e)}"
            print(f"❌ [ERROR] {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    def get_transaction_status(self, tx_hash: str) -> Dict[str, Any]:
        """
        Get the status of a transaction.
        
        Args:
            tx_hash: Transaction hash
            
        Returns:
            Dictionary with transaction status
        """
        try:
            # Get transaction receipt
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)
            
            status = "success" if receipt.status == 1 else "failed"
            block_number = receipt.blockNumber
            gas_used = receipt.gasUsed
            
            print(f"📈 [DEBUG] Transaction {tx_hash} status: {status}")
            print(f"📊 [DEBUG] Block: {block_number}, Gas used: {gas_used}")
            
            return {
                "success": True,
                "status": status,
                "block_number": block_number,
                "gas_used": gas_used,
                "receipt": receipt
            }
            
        except Exception as e:
            # Transaction might be pending
            error_msg = f"Transaction status check failed: {str(e)}"
            print(f"⏳ [DEBUG] {error_msg} (might be pending)")
            return {
                "success": False,
                "error": error_msg,
                "status": "pending"
            }
    
    def wei_to_eth(self, wei_amount: int) -> float:
        """Convert wei to ETH."""
        return float(self.w3.from_wei(wei_amount, 'ether'))
    
    def eth_to_wei(self, eth_amount: float) -> int:
        """Convert ETH to wei."""
        return self.w3.to_wei(Decimal(str(eth_amount)), 'ether')
    
    def get_latest_block(self) -> Dict[str, Any]:
        """Get latest block information."""
        try:
            latest_block = self.w3.eth.get_block('latest')
            return {
                "success": True,
                "block_number": latest_block.number,
                "block_hash": latest_block.hash.hex(),
                "timestamp": latest_block.timestamp
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }