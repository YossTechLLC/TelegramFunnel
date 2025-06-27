#!/usr/bin/env python
"""
BTC Wallet Manager - WBTC (Wrapped Bitcoin) transaction handling using web3.py.
Manages WBTC transfers, balance checking, and Bitcoin address validation.
"""
import re
import time
from typing import Dict, Any, Optional
from decimal import Decimal
from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_account import Account
from eth_account.signers.local import LocalAccount

# Import from parent directory
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'GCSplit26'))
from token_registry import TokenRegistry, ERC20_ABI

# Bitcoin address validation
try:
    from bitcoinlib.keys import Address as BitcoinAddress
    BITCOINLIB_AVAILABLE = True
except ImportError:
    BITCOINLIB_AVAILABLE = False
    print("⚠️ [WARNING] bitcoinlib not available - using regex validation only")


class BTCWalletManager:
    """Manages WBTC (Wrapped Bitcoin) wallet operations and transactions."""
    
    def __init__(self, private_key: str, host_address: str, rpc_url: str, chain_id: int = 1):
        """
        Initialize the BTC wallet manager.
        
        Args:
            private_key: Private key for the host wallet (with 0x prefix)
            host_address: ETH address of the host wallet
            rpc_url: Ethereum RPC endpoint URL
            chain_id: Chain ID (1 for Ethereum, 137 for Polygon)
        """
        self.private_key = private_key
        self.rpc_url = rpc_url
        self.chain_id = chain_id
        
        # Ensure host address is properly checksummed
        if not Web3.is_address(host_address):
            raise ValueError(f"Invalid Ethereum address: {host_address}")
        self.host_address = Web3.to_checksum_address(host_address)
        
        # Initialize Web3 connection
        self.w3 = None
        self.account = None
        self.token_registry = None
        self.wbtc_contract = None
        
        self._initialize_web3()
        self._initialize_wbtc_contract()
        print(f"₿ [INFO] BTC Wallet Manager initialized for address: {self.host_address}")
    
    def _initialize_web3(self) -> None:
        """Initialize Web3 connection and account."""
        try:
            print(f"🔗 [INFO] Connecting to blockchain (Chain ID: {self.chain_id})...")
            
            # Create Web3 instance
            from web3.providers import HTTPProvider
            
            headers = {
                'User-Agent': 'TPBTCS1-BTC-Service/1.0',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            provider = HTTPProvider(
                self.rpc_url,
                request_kwargs={
                    'timeout': 30,
                    'headers': headers
                }
            )
            self.w3 = Web3(provider)
            
            # Add middleware for POA networks
            if self.chain_id in [137, 80001]:  # Polygon networks
                self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
                print(f"🔧 [INFO] Added POA middleware for Polygon")
            
            # Test connection
            if not self.w3.is_connected():
                raise ConnectionError("Web3 connection failed")
            
            block_number = self.w3.eth.block_number
            print(f"✅ [INFO] Connected to chain {self.chain_id}, block: {block_number}")
            
            # Create account from private key
            self.account: LocalAccount = Account.from_key(self.private_key)
            
            if self.account.address.lower() != self.host_address.lower():
                raise ValueError(f"Private key does not match host address")
            
            # Initialize token registry
            self.token_registry = TokenRegistry()
            print(f"✅ [INFO] Web3 and account initialized successfully")
            
        except Exception as e:
            print(f"❌ [ERROR] Web3 initialization failed: {e}")
            raise
    
    def _initialize_wbtc_contract(self) -> None:
        """Initialize WBTC token contract."""
        try:
            wbtc_info = self.token_registry.get_token_info(self.chain_id, "WBTC")
            if not wbtc_info:
                raise ValueError(f"WBTC not supported on chain {self.chain_id}")
            
            self.wbtc_contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(wbtc_info.address),
                abi=ERC20_ABI
            )
            
            # Test contract connection
            symbol = self.wbtc_contract.functions.symbol().call()
            decimals = self.wbtc_contract.functions.decimals().call()
            
            print(f"₿ [INFO] WBTC contract initialized: {symbol} ({decimals} decimals)")
            print(f"₿ [INFO] Contract address: {wbtc_info.address}")
            
        except Exception as e:
            print(f"❌ [ERROR] WBTC contract initialization failed: {e}")
            raise
    
    def validate_bitcoin_address(self, address: str) -> Dict[str, Any]:
        """
        Validate Bitcoin address format.
        
        Args:
            address: Bitcoin address to validate
            
        Returns:
            Dictionary with validation results
        """
        try:
            if not address or not isinstance(address, str):
                return {
                    'valid': False,
                    'error': 'Address is empty or not a string'
                }
            
            # Basic regex validation for Bitcoin addresses
            btc_regex = r'^(bc1|[13])[a-km-zA-HJ-NP-Z1-9]{25,62}$'
            
            if not re.match(btc_regex, address):
                return {
                    'valid': False,
                    'error': 'Invalid Bitcoin address format'
                }
            
            # Advanced validation using bitcoinlib if available
            if BITCOINLIB_AVAILABLE:
                try:
                    btc_addr = BitcoinAddress(address)
                    if btc_addr.address != address:
                        return {
                            'valid': False,
                            'error': 'Bitcoin address checksum validation failed'
                        }
                except Exception as e:
                    return {
                        'valid': False,
                        'error': f'Bitcoin address validation failed: {str(e)}'
                    }
            
            # Determine address type
            address_type = 'unknown'
            if address.startswith('1'):
                address_type = 'P2PKH (Legacy)'
            elif address.startswith('3'):
                address_type = 'P2SH (Script)'
            elif address.startswith('bc1'):
                address_type = 'Bech32 (SegWit)'
            
            print(f"✅ [INFO] Valid Bitcoin address: {address[:10]}... ({address_type})")
            
            return {
                'valid': True,
                'address_type': address_type,
                'format': 'bitcoin'
            }
            
        except Exception as e:
            print(f"❌ [ERROR] Bitcoin address validation error: {e}")
            return {
                'valid': False,
                'error': f'Validation error: {str(e)}'
            }
    
    def get_wbtc_balance(self) -> Dict[str, Any]:
        """
        Get WBTC balance of the host wallet.
        
        Returns:
            Dictionary with balance information
        """
        try:
            print(f"💰 [INFO] Checking WBTC balance for {self.host_address}")
            
            balance_wei = self.wbtc_contract.functions.balanceOf(self.host_address).call()
            balance_wbtc = balance_wei / (10 ** 8)  # WBTC has 8 decimals
            
            # Get USD value using current BTC price (approximate)
            balance_usd = 0.0
            try:
                from btc_converter import BTCConverter
                converter = BTCConverter()
                rate_result = converter.get_usd_to_wbtc_rate()
                if rate_result['success']:
                    balance_usd = balance_wbtc * rate_result['usd_per_btc']
            except Exception:
                pass  # USD value is optional
            
            print(f"💰 [INFO] WBTC Balance: {balance_wbtc:.8f} WBTC (~${balance_usd:.2f})")
            
            return {
                'success': True,
                'balance_wbtc': balance_wbtc,
                'balance_wei': balance_wei,
                'balance_usd': balance_usd
            }
            
        except Exception as e:
            print(f"❌ [ERROR] WBTC balance check failed: {e}")
            return {
                'success': False,
                'error': f'Balance check failed: {str(e)}'
            }
    
    def estimate_wbtc_transfer_cost(self, recipient_address: str, amount_wbtc: float) -> Dict[str, Any]:
        """
        Estimate gas cost for WBTC transfer.
        
        Args:
            recipient_address: Recipient address (can be BTC or ETH format)
            amount_wbtc: Amount of WBTC to transfer
            
        Returns:
            Dictionary with gas estimation
        """
        try:
            # For BTC addresses, we can't directly send WBTC
            # This is a limitation of the current implementation
            if not recipient_address.startswith('0x'):
                return {
                    'success': False,
                    'error': 'Cannot send WBTC to Bitcoin address - recipient must have Ethereum address for WBTC'
                }
            
            recipient_eth = Web3.to_checksum_address(recipient_address)
            amount_wei = int(amount_wbtc * (10 ** 8))  # Convert to wei
            
            # Estimate gas for ERC20 transfer
            gas_estimate = self.wbtc_contract.functions.transfer(
                recipient_eth, amount_wei
            ).estimate_gas({'from': self.host_address})
            
            gas_price = self.w3.eth.gas_price
            gas_cost_wei = gas_estimate * gas_price
            gas_cost_eth = gas_cost_wei / (10 ** 18)
            
            print(f"⛽ [INFO] WBTC transfer gas estimate: {gas_estimate} gas")
            print(f"⛽ [INFO] Gas cost: {gas_cost_eth:.6f} ETH")
            
            return {
                'success': True,
                'gas_estimate': gas_estimate,
                'gas_price': gas_price,
                'gas_cost_wei': gas_cost_wei,
                'gas_cost_eth': gas_cost_eth
            }
            
        except Exception as e:
            print(f"❌ [ERROR] Gas estimation failed: {e}")
            return {
                'success': False,
                'error': f'Gas estimation failed: {str(e)}'
            }
    
    def send_wbtc_to_address(self, recipient_address: str, amount_wbtc: float, request_id: str = None) -> Dict[str, Any]:
        """
        Send WBTC to a recipient address.
        
        Args:
            recipient_address: Recipient Ethereum address (WBTC requires ETH address)
            amount_wbtc: Amount of WBTC to send
            request_id: Optional request ID for logging
            
        Returns:
            Dictionary with transaction results
        """
        try:
            if not request_id:
                request_id = f"WBTC_{int(time.time())}"
            
            print(f"₿ [INFO] {request_id}: Initiating WBTC transfer")
            print(f"📤 [INFO] {request_id}: Amount: {amount_wbtc:.8f} WBTC")
            print(f"🎯 [INFO] {request_id}: Recipient: {recipient_address}")
            
            # Validate recipient is Ethereum address
            if not recipient_address.startswith('0x'):
                return {
                    'success': False,
                    'error': 'WBTC transfers require Ethereum address - Bitcoin addresses not supported'
                }
            
            recipient_eth = Web3.to_checksum_address(recipient_address)
            amount_wei = int(amount_wbtc * (10 ** 8))  # Convert to wei (8 decimals)
            
            # Check balance
            balance_result = self.get_wbtc_balance()
            if not balance_result['success']:
                return balance_result
            
            if balance_result['balance_wbtc'] < amount_wbtc:
                return {
                    'success': False,
                    'error': f"Insufficient WBTC balance. Need: {amount_wbtc:.8f}, Have: {balance_result['balance_wbtc']:.8f}"
                }
            
            # Get gas estimate
            gas_result = self.estimate_wbtc_transfer_cost(recipient_address, amount_wbtc)
            if not gas_result['success']:
                return gas_result
            
            # Build transaction
            nonce = self.w3.eth.get_transaction_count(self.host_address, 'pending')
            
            transaction = self.wbtc_contract.functions.transfer(
                recipient_eth, amount_wei
            ).build_transaction({
                'from': self.host_address,
                'gas': int(gas_result['gas_estimate'] * 1.1),  # 10% buffer
                'gasPrice': gas_result['gas_price'],
                'nonce': nonce,
                'chainId': self.chain_id
            })
            
            print(f"🔐 [INFO] {request_id}: Signing WBTC transaction...")
            
            # Sign transaction
            signed_txn = self.account.sign_transaction(transaction)
            
            print(f"📡 [INFO] {request_id}: Broadcasting WBTC transaction...")
            
            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            tx_hash_hex = tx_hash.hex()
            
            print(f"✅ [SUCCESS] {request_id}: WBTC transaction broadcasted!")
            print(f"🔗 [INFO] {request_id}: TX Hash: {tx_hash_hex}")
            
            # Wait for confirmation (optional - can be made configurable)
            try:
                print(f"⏳ [INFO] {request_id}: Waiting for transaction confirmation...")
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
                
                if receipt.status == 1:
                    print(f"✅ [SUCCESS] {request_id}: WBTC transaction confirmed in block {receipt.blockNumber}")
                else:
                    print(f"❌ [ERROR] {request_id}: Transaction failed (status: {receipt.status})")
                    return {
                        'success': False,
                        'error': 'Transaction failed during execution',
                        'transaction_hash': tx_hash_hex
                    }
                
            except Exception as e:
                print(f"⚠️ [WARNING] {request_id}: Confirmation timeout: {e}")
                # Still return success as transaction was broadcasted
            
            return {
                'success': True,
                'transaction_hash': tx_hash_hex,
                'amount_wbtc': amount_wbtc,
                'recipient': recipient_eth,
                'gas_used': gas_result['gas_estimate'],
                'gas_price': gas_result['gas_price'],
                'chain_id': self.chain_id
            }
            
        except Exception as e:
            print(f"❌ [ERROR] {request_id}: WBTC transfer failed: {e}")
            return {
                'success': False,
                'error': f'Transfer failed: {str(e)}'
            }
    
    def get_wallet_balance(self) -> Dict[str, Any]:
        """
        Get ETH balance for gas fees.
        
        Returns:
            Dictionary with ETH balance
        """
        try:
            balance_wei = self.w3.eth.get_balance(self.host_address)
            balance_eth = balance_wei / (10 ** 18)
            
            return {
                'success': True,
                'balance_eth': balance_eth,
                'balance_wei': balance_wei
            }
            
        except Exception as e:
            print(f"❌ [ERROR] ETH balance check failed: {e}")
            return {
                'success': False,
                'error': f'ETH balance check failed: {str(e)}'
            }