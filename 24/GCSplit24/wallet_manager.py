#!/usr/bin/env python
"""
Wallet Manager - Ethereum transaction handling using web3.py.
Manages ETH transfers, balance checking, and transaction monitoring.
"""
import time
from typing import Dict, Any, Optional, Union
from decimal import Decimal
from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_account import Account
from eth_account.signers.local import LocalAccount

class WalletManager:
    """Manages Ethereum wallet operations and transactions."""
    
    def __init__(self, private_key: str, host_address: str, rpc_url: str):
        """
        Initialize the wallet manager.
        
        Args:
            private_key: Private key for the host wallet (with 0x prefix)
            host_address: ETH address of the host wallet
            rpc_url: Ethereum RPC endpoint URL
        """
        self.private_key = private_key
        self.rpc_url = rpc_url
        
        # Ensure host address is properly checksummed
        if not Web3.is_address(host_address):
            raise ValueError(f"Invalid Ethereum address: {host_address}")
        self.host_address = Web3.to_checksum_address(host_address)
        
        # Initialize Web3 connection
        self.w3 = None
        self.account = None
        
        self._initialize_web3()
        print(f"🏦 [INFO] Wallet Manager initialized for address: {self.host_address}")
    
    def _initialize_web3(self) -> None:
        """Initialize Web3 connection and account."""
        try:
            # Log RPC connection attempt (mask sensitive parts)
            masked_rpc = self.rpc_url.replace(self.rpc_url.split('/')[-1], '***') if '/' in self.rpc_url else '***'
            print(f"🔗 [INFO] Attempting connection to RPC endpoint: {masked_rpc}")
            
            # Create Web3 instance with enhanced provider settings
            from web3.providers import HTTPProvider
            
            # Prepare request headers for better provider compatibility
            headers = {
                'User-Agent': 'TPS1-ETH-Payment-Service/1.0',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Add provider-specific optimizations
            if any(provider in self.rpc_url.lower() for provider in ['infura', 'alchemy', 'quicknode']):
                headers['Accept-Encoding'] = 'gzip, deflate'
                print(f"🔧 [INFO] Using optimized headers for managed RPC provider")
            
            provider = HTTPProvider(
                self.rpc_url,
                request_kwargs={
                    'timeout': 30,  # 30 second timeout
                    'headers': headers
                }
            )
            self.w3 = Web3(provider)
            
            # Add middleware for POA networks (if needed)
            if 'polygon' in self.rpc_url.lower() or 'bsc' in self.rpc_url.lower():
                self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
                print(f"🔧 [INFO] Added POA middleware for network")
            
            # Test basic connectivity with retries
            print(f"🔄 [INFO] Testing Web3 connection...")
            connection_success = False
            max_retries = 3
            
            for attempt in range(max_retries):
                try:
                    print(f"🔄 [INFO] Connection attempt {attempt + 1}/{max_retries}")
                    
                    # Test basic connection
                    if not self.w3.is_connected():
                        raise ConnectionError("Web3.is_connected() returned False")
                    
                    # Try to get a basic response from the node
                    print(f"🔄 [INFO] Testing RPC response...")
                    client_version = self.w3.client_version
                    print(f"🔗 [INFO] RPC client version: {client_version}")
                    
                    # Test getting latest block number
                    block_number = self.w3.eth.block_number
                    print(f"🔗 [INFO] Latest block number: {block_number}")
                    
                    connection_success = True
                    break
                    
                except Exception as e:
                    print(f"⚠️ [WARNING] Connection attempt {attempt + 1} failed: {e}")
                    if attempt < max_retries - 1:
                        import time
                        wait_time = (attempt + 1) * 2  # 2, 4, 6 seconds
                        print(f"⏳ [INFO] Waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                    else:
                        print(f"❌ [ERROR] All connection attempts failed")
                        raise ConnectionError(f"Failed to establish stable connection after {max_retries} attempts: {e}")
            
            if not connection_success:
                raise ConnectionError("Connection validation failed")
            
            print(f"✅ [INFO] Web3 connection established successfully")
            
            # Create account from private key
            self.account: LocalAccount = Account.from_key(self.private_key)
            
            # Verify account address matches provided address
            if self.account.address.lower() != self.host_address.lower():
                raise ValueError(f"Private key does not match host address. Expected: {self.host_address}, Got: {self.account.address}")
            
            # Get detailed network info
            chain_id = self.w3.eth.chain_id
            network_names = {
                1: 'Ethereum Mainnet',
                5: 'Goerli Testnet', 
                11155111: 'Sepolia Testnet',
                137: 'Polygon Mainnet',
                80001: 'Polygon Mumbai',
                56: 'BSC Mainnet',
                97: 'BSC Testnet'
            }
            network_name = network_names.get(chain_id, f'Unknown Network (ID: {chain_id})')
            
            print(f"🌐 [INFO] Connected to {network_name} (Chain ID: {chain_id})")
            print(f"✅ [INFO] Account verified: {self.account.address}")
            print(f"🏦 [INFO] Web3 initialization completed successfully")
            
        except Exception as e:
            print(f"❌ [ERROR] Web3 initialization failed: {e}")
            print(f"🔍 [DEBUG] RPC URL (masked): {masked_rpc if 'masked_rpc' in locals() else 'Unknown'}")
            print(f"🔍 [DEBUG] Error type: {type(e).__name__}")
            raise
    
    def get_wallet_balance(self) -> Dict[str, Any]:
        """
        Get current wallet balance in ETH and USD equivalent.
        
        Returns:
            Dictionary with balance information
        """
        try:
            # Get balance in Wei using checksummed address
            balance_wei = self.w3.eth.get_balance(self.host_address)
            
            # Convert to ETH
            balance_eth = self.w3.from_wei(balance_wei, 'ether')
            balance_eth_float = float(balance_eth)
            
            print(f"💰 [INFO] Wallet balance: {balance_eth_float:.8f} ETH")
            
            return {
                'success': True,
                'balance_wei': balance_wei,
                'balance_eth': balance_eth_float,
                'address': self.host_address,
                'timestamp': time.time()
            }
            
        except Exception as e:
            error_msg = f"Failed to get wallet balance: {str(e)}"
            print(f"❌ [ERROR] {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
    
    def estimate_gas_price(self) -> Dict[str, Any]:
        """
        Estimate current gas prices for transactions.
        
        Returns:
            Dictionary with gas price information
        """
        try:
            # Get current gas price
            gas_price = self.w3.eth.gas_price
            
            # For EIP-1559 networks, get fee data
            fee_data = {}
            try:
                latest_block = self.w3.eth.get_block('latest')
                if hasattr(latest_block, 'baseFeePerGas') and latest_block.baseFeePerGas:
                    # EIP-1559 network
                    base_fee = latest_block.baseFeePerGas
                    max_priority_fee = self.w3.to_wei(2, 'gwei')  # 2 gwei priority fee
                    max_fee = base_fee + max_priority_fee
                    
                    fee_data = {
                        'base_fee_per_gas': base_fee,
                        'max_priority_fee_per_gas': max_priority_fee,
                        'max_fee_per_gas': max_fee,
                        'is_eip1559': True
                    }
                else:
                    # Legacy network
                    fee_data = {
                        'gas_price': gas_price,
                        'is_eip1559': False
                    }
            except Exception:
                # Fallback to legacy gas price
                fee_data = {
                    'gas_price': gas_price,
                    'is_eip1559': False
                }
            
            return {
                'success': True,
                'gas_price': gas_price,
                'gas_price_gwei': self.w3.from_wei(gas_price, 'gwei'),
                'fee_data': fee_data,
                'timestamp': time.time()
            }
            
        except Exception as e:
            error_msg = f"Failed to estimate gas price: {str(e)}"
            print(f"❌ [ERROR] {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
    
    def estimate_transaction_cost(self, recipient_address: str, amount_eth: float) -> Dict[str, Any]:
        """
        Estimate total cost of a transaction including gas.
        
        Args:
            recipient_address: Address to send ETH to
            amount_eth: Amount of ETH to send
            
        Returns:
            Dictionary with cost estimation
        """
        try:
            # Get gas price estimation
            gas_result = self.estimate_gas_price()
            if not gas_result['success']:
                return gas_result
            
            # Estimate gas limit for ETH transfer (usually 21000)
            amount_wei = self.w3.to_wei(amount_eth, 'ether')
            
            try:
                # Ensure recipient address is checksummed for gas estimation
                recipient_checksum = Web3.to_checksum_address(recipient_address)
                gas_estimate = self.w3.eth.estimate_gas({
                    'from': self.host_address,
                    'to': recipient_checksum,
                    'value': amount_wei
                })
            except Exception:
                # Use standard gas limit for ETH transfer
                gas_estimate = 21000
            
            # Calculate gas costs
            gas_price = gas_result['gas_price']
            gas_cost_wei = gas_estimate * gas_price
            gas_cost_eth = self.w3.from_wei(gas_cost_wei, 'ether')
            
            total_cost_eth = amount_eth + float(gas_cost_eth)
            
            return {
                'success': True,
                'amount_eth': amount_eth,
                'gas_estimate': gas_estimate,
                'gas_price': gas_price,
                'gas_price_gwei': float(self.w3.from_wei(gas_price, 'gwei')),
                'gas_cost_wei': gas_cost_wei,
                'gas_cost_eth': float(gas_cost_eth),
                'total_cost_eth': total_cost_eth,
                'fee_data': gas_result['fee_data']
            }
            
        except Exception as e:
            error_msg = f"Failed to estimate transaction cost: {str(e)}"
            print(f"❌ [ERROR] {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
    
    def send_eth_to_address(self, recipient_address: str, amount_eth: float, request_id: str = None) -> Dict[str, Any]:
        """
        Send ETH to a specified address.
        
        Args:
            recipient_address: Address to send ETH to
            amount_eth: Amount of ETH to send
            request_id: Optional request ID for tracking
            
        Returns:
            Dictionary with transaction result
        """
        try:
            request_id = request_id or f"TX_{int(time.time())}"
            print(f"📤 [INFO] {request_id}: Preparing ETH transfer...")
            
            # Validate recipient address
            if not Web3.is_address(recipient_address):
                return {
                    'success': False,
                    'error': f"Invalid recipient address: {recipient_address}"
                }
            
            recipient_address = Web3.to_checksum_address(recipient_address)
            
            # Validate amount
            if amount_eth <= 0:
                return {
                    'success': False,
                    'error': f"Invalid amount: {amount_eth} ETH"
                }
            
            # Check balance
            balance_result = self.get_wallet_balance()
            if not balance_result['success']:
                return {
                    'success': False,
                    'error': f"Failed to check balance: {balance_result.get('error', 'Unknown error')}"
                }
            
            # Estimate transaction costs
            cost_result = self.estimate_transaction_cost(recipient_address, amount_eth)
            if not cost_result['success']:
                return {
                    'success': False,
                    'error': f"Failed to estimate costs: {cost_result.get('error', 'Unknown error')}"
                }
            
            # Check if we have enough balance
            wallet_balance = balance_result['balance_eth']
            total_cost = cost_result['total_cost_eth']
            
            if wallet_balance < total_cost:
                return {
                    'success': False,
                    'error': f"Insufficient balance. Need: {total_cost:.8f} ETH, Have: {wallet_balance:.8f} ETH"
                }
            
            print(f"💰 [INFO] {request_id}: Sending {amount_eth:.8f} ETH to {recipient_address}")
            print(f"⛽ [INFO] {request_id}: Gas cost: {cost_result['gas_cost_eth']:.8f} ETH ({cost_result['gas_estimate']} gas @ {cost_result['gas_price_gwei']:.2f} gwei)")
            
            # Get current nonce
            nonce = self.w3.eth.get_transaction_count(self.host_address)
            
            # Convert amount to Wei
            amount_wei = self.w3.to_wei(amount_eth, 'ether')
            
            # Build transaction
            fee_data = cost_result['fee_data']
            
            if fee_data.get('is_eip1559', False):
                # EIP-1559 transaction
                transaction = {
                    'from': self.host_address,
                    'to': recipient_address,
                    'value': amount_wei,
                    'nonce': nonce,
                    'gas': cost_result['gas_estimate'],
                    'maxFeePerGas': fee_data['max_fee_per_gas'],
                    'maxPriorityFeePerGas': fee_data['max_priority_fee_per_gas'],
                    'type': 2  # EIP-1559 transaction type
                }
            else:
                # Legacy transaction
                transaction = {
                    'from': self.host_address,
                    'to': recipient_address,
                    'value': amount_wei,
                    'nonce': nonce,
                    'gas': cost_result['gas_estimate'],
                    'gasPrice': cost_result['gas_price']
                }
            
            print(f"🔐 [INFO] {request_id}: Signing transaction...")
            
            # Sign transaction
            signed_txn = self.w3.eth.account.sign_transaction(transaction, self.private_key)
            
            print(f"📡 [INFO] {request_id}: Broadcasting transaction...")
            
            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.raw_transaction)
            tx_hash_hex = tx_hash.hex()
            
            print(f"⏳ [INFO] {request_id}: Transaction broadcast - Hash: {tx_hash_hex}")
            print(f"🔍 [INFO] {request_id}: Waiting for confirmation...")
            
            # Wait for transaction receipt (with timeout)
            try:
                tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
                
                if tx_receipt.status == 1:
                    # Transaction successful
                    actual_gas_used = tx_receipt.gasUsed
                    actual_gas_price = transaction.get('gasPrice', fee_data.get('max_fee_per_gas', 0))
                    actual_gas_cost_wei = actual_gas_used * actual_gas_price
                    actual_gas_cost_eth = self.w3.from_wei(actual_gas_cost_wei, 'ether')
                    
                    print(f"✅ [SUCCESS] {request_id}: Transaction confirmed!")
                    print(f"⛽ [INFO] {request_id}: Actual gas used: {actual_gas_used} (cost: {float(actual_gas_cost_eth):.8f} ETH)")
                    
                    return {
                        'success': True,
                        'transaction_hash': tx_hash_hex,
                        'recipient': recipient_address,
                        'amount_eth': amount_eth,
                        'gas_used': actual_gas_used,
                        'gas_price': actual_gas_price,
                        'gas_cost_eth': float(actual_gas_cost_eth),
                        'block_number': tx_receipt.blockNumber,
                        'block_hash': tx_receipt.blockHash.hex(),
                        'transaction_index': tx_receipt.transactionIndex,
                        'request_id': request_id
                    }
                else:
                    # Transaction failed
                    return {
                        'success': False,
                        'error': 'Transaction failed (status: 0)',
                        'transaction_hash': tx_hash_hex,
                        'receipt': dict(tx_receipt)
                    }
                    
            except Exception as e:
                # Transaction timeout or error getting receipt
                print(f"⚠️ [WARNING] {request_id}: Could not get transaction receipt: {e}")
                return {
                    'success': False,
                    'error': f'Transaction receipt timeout: {str(e)}',
                    'transaction_hash': tx_hash_hex,
                    'note': 'Transaction may still be pending - check manually'
                }
            
        except Exception as e:
            error_msg = f"ETH transfer failed: {str(e)}"
            print(f"❌ [ERROR] {request_id or 'Unknown'}: {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'request_id': request_id
            }
    
    def get_transaction_status(self, tx_hash: str) -> Dict[str, Any]:
        """
        Get status of a transaction by hash.
        
        Args:
            tx_hash: Transaction hash to check
            
        Returns:
            Dictionary with transaction status
        """
        try:
            # Get transaction receipt
            tx_receipt = self.w3.eth.get_transaction_receipt(tx_hash)
            
            # Get transaction details
            tx_details = self.w3.eth.get_transaction(tx_hash)
            
            return {
                'success': True,
                'transaction_hash': tx_hash,
                'status': 'confirmed' if tx_receipt.status == 1 else 'failed',
                'block_number': tx_receipt.blockNumber,
                'gas_used': tx_receipt.gasUsed,
                'from_address': tx_details['from'],
                'to_address': tx_details['to'],
                'value_wei': tx_details['value'],
                'value_eth': float(self.w3.from_wei(tx_details['value'], 'ether')),
                'gas_price': tx_details.get('gasPrice', 0),
                'nonce': tx_details['nonce']
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to get transaction status: {str(e)}",
                'transaction_hash': tx_hash
            }
    
    def get_network_info(self) -> Dict[str, Any]:
        """
        Get current network information.
        
        Returns:
            Dictionary with network details
        """
        try:
            chain_id = self.w3.eth.chain_id
            block_number = self.w3.eth.block_number
            gas_price = self.w3.eth.gas_price
            
            # Get network name based on chain ID
            network_names = {
                1: 'Ethereum Mainnet',
                3: 'Ropsten Testnet',
                4: 'Rinkeby Testnet',
                5: 'Goerli Testnet',
                11155111: 'Sepolia Testnet',
                137: 'Polygon Mainnet',
                80001: 'Polygon Mumbai',
                56: 'BSC Mainnet',
                97: 'BSC Testnet'
            }
            
            network_name = network_names.get(chain_id, f'Unknown Network (ID: {chain_id})')
            
            return {
                'success': True,
                'chain_id': chain_id,
                'network_name': network_name,
                'block_number': block_number,
                'gas_price': gas_price,
                'gas_price_gwei': float(self.w3.from_wei(gas_price, 'gwei')),
                'rpc_url': self.rpc_url,
                'is_connected': self.w3.is_connected()
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to get network info: {str(e)}"
            }