#!/usr/bin/env python
"""
Wallet Manager - Ethereum transaction handling using web3.py.
Manages ETH transfers, balance checking, transaction monitoring, and automatic token swapping.
"""
import time
from typing import Dict, Any, Optional, Union
from decimal import Decimal
from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_account import Account
from eth_account.signers.local import LocalAccount
from token_registry import TokenRegistry, ERC20_ABI
from dex_swapper import DEXSwapper, SwapConfig

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
        self.token_registry = None
        self.dex_swapper = None
        
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
                'User-Agent': 'TPS2-ETH-Payment-Service/1.0',
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
            
            # Initialize token registry for this chain
            self.token_registry = TokenRegistry()
            supported_tokens = self.token_registry.get_supported_tokens(chain_id)
            print(f"🪙 [INFO] Token registry initialized with {len(supported_tokens)} supported tokens")
            
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
    
    def _validate_contract_address(self, contract_address: str, token_symbol: str) -> Dict[str, Any]:
        """
        Validate that a contract address exists and has code deployed.
        
        Args:
            contract_address: Contract address to validate
            token_symbol: Token symbol for logging
            
        Returns:
            Dictionary with validation result
        """
        try:
            # Check if address is valid format
            if not Web3.is_address(contract_address):
                return {
                    'valid': False,
                    'error': f'Invalid address format for {token_symbol}: {contract_address}'
                }
            
            # Check if contract has code deployed
            code = self.w3.eth.get_code(Web3.to_checksum_address(contract_address))
            
            if code == b'' or code == '0x':
                return {
                    'valid': False,
                    'error': f'No contract code found at {token_symbol} address {contract_address} - contract may not be deployed'
                }
            
            print(f"✅ [VALIDATION] {token_symbol} contract validated at {contract_address}")
            return {
                'valid': True,
                'code_size': len(code),
                'address': contract_address
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': f'Contract validation failed for {token_symbol}: {str(e)}'
            }

    def get_erc20_balance(self, token_symbol: str) -> Dict[str, Any]:
        """
        Get ERC20 token balance for the host wallet with contract validation.
        
        Args:
            token_symbol: Token symbol (e.g., "USDT", "USDC")
            
        Returns:
            Dictionary with balance information
        """
        try:
            chain_id = self.w3.eth.chain_id
            token_info = self.token_registry.get_token_info(chain_id, token_symbol)
            
            if not token_info:
                return {
                    'success': False,
                    'error': f'Token {token_symbol} not supported on chain {chain_id}'
                }
            
            # Validate contract address before attempting to interact
            validation_result = self._validate_contract_address(token_info.address, token_symbol)
            if not validation_result['valid']:
                print(f"❌ [ERROR] Contract validation failed: {validation_result['error']}")
                return {
                    'success': False,
                    'error': validation_result['error'],
                    'validation_details': validation_result
                }
            
            # Create contract instance
            token_contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(token_info.address),
                abi=ERC20_ABI
            )
            
            # Get balance in token's smallest unit
            balance_raw = token_contract.functions.balanceOf(self.host_address).call()
            
            # Convert to human-readable format
            balance_tokens = balance_raw / (10 ** token_info.decimals)
            
            print(f"🪙 [INFO] {token_symbol} balance: {balance_tokens:.8f} {token_symbol}")
            
            return {
                'success': True,
                'balance_raw': balance_raw,
                'balance_tokens': balance_tokens,
                'token_symbol': token_symbol,
                'token_decimals': token_info.decimals,
                'token_address': token_info.address,
                'address': self.host_address,
                'timestamp': time.time(),
                'contract_validation': validation_result
            }
            
        except Exception as e:
            error_msg = f"Failed to get {token_symbol} balance: {str(e)}"
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
    
    def estimate_erc20_transfer_cost(self, recipient_address: str, amount_tokens: float, token_symbol: str) -> Dict[str, Any]:
        """
        Estimate total gas cost for an ERC20 token transfer.
        
        Args:
            recipient_address: Address to send tokens to
            amount_tokens: Amount of tokens to send
            token_symbol: Token symbol (e.g., "USDT", "USDC")
            
        Returns:
            Dictionary with cost estimation
        """
        try:
            chain_id = self.w3.eth.chain_id
            token_info = self.token_registry.get_token_info(chain_id, token_symbol)
            
            if not token_info:
                return {
                    'success': False,
                    'error': f'Token {token_symbol} not supported on chain {chain_id}'
                }
            
            # Validate contract address before attempting to interact
            validation_result = self._validate_contract_address(token_info.address, token_symbol)
            if not validation_result['valid']:
                print(f"❌ [ERROR] Contract validation failed: {validation_result['error']}")
                return {
                    'success': False,
                    'error': validation_result['error'],
                    'validation_details': validation_result
                }
            
            # Get gas price estimation
            gas_result = self.estimate_gas_price()
            if not gas_result['success']:
                return gas_result
            
            # Create contract instance
            token_contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(token_info.address),
                abi=ERC20_ABI
            )
            
            # Convert amount to token's smallest unit
            amount_raw = int(amount_tokens * (10 ** token_info.decimals))
            
            try:
                # Ensure recipient address is checksummed for gas estimation
                recipient_checksum = Web3.to_checksum_address(recipient_address)
                
                # Estimate gas for ERC20 transfer
                gas_estimate = token_contract.functions.transfer(
                    recipient_checksum, 
                    amount_raw
                ).estimate_gas({'from': self.host_address})
                
            except Exception as e:
                # Use standard gas limit for ERC20 transfers (typically 60,000-100,000)
                print(f"⚠️ [WARNING] Gas estimation failed, using default: {e}")
                gas_estimate = 80000  # Conservative estimate
            
            # Calculate gas costs in ETH
            gas_price = gas_result['gas_price']
            gas_cost_wei = gas_estimate * gas_price
            gas_cost_eth = self.w3.from_wei(gas_cost_wei, 'ether')
            
            return {
                'success': True,
                'token_symbol': token_symbol,
                'amount_tokens': amount_tokens,
                'amount_raw': amount_raw,
                'gas_estimate': gas_estimate,
                'gas_price': gas_price,
                'gas_price_gwei': float(self.w3.from_wei(gas_price, 'gwei')),
                'gas_cost_wei': gas_cost_wei,
                'gas_cost_eth': float(gas_cost_eth),
                'token_decimals': token_info.decimals,
                'token_address': token_info.address,
                'fee_data': gas_result['fee_data']
            }
            
        except Exception as e:
            error_msg = f"Failed to estimate {token_symbol} transfer cost: {str(e)}"
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
            
            # Temporary: Force legacy transactions for stability testing
            # Can be removed once EIP-1559 is confirmed working
            force_legacy = True  # Set to False to re-enable EIP-1559
            
            if fee_data.get('is_eip1559', False) and not force_legacy:
                # EIP-1559 transaction (from field auto-derived during signing)
                chain_id = self.w3.eth.chain_id
                transaction = {
                    'to': recipient_address,
                    'value': amount_wei,
                    'nonce': nonce,
                    'gas': cost_result['gas_estimate'],  # Web3.py 6.x still uses 'gas' for gas limit
                    'maxFeePerGas': fee_data['max_fee_per_gas'],
                    'maxPriorityFeePerGas': fee_data['max_priority_fee_per_gas'],
                    'chainId': chain_id,  # Required for EIP-1559 replay protection
                    'type': 2  # EIP-1559 transaction type
                }
                print(f"🔧 [INFO] {request_id}: Built EIP-1559 transaction with chainId: {chain_id}")
            else:
                # Legacy transaction (from field auto-derived during signing)
                chain_id = self.w3.eth.chain_id
                transaction = {
                    'to': recipient_address,
                    'value': amount_wei,
                    'nonce': nonce,
                    'gas': cost_result['gas_estimate'],
                    'gasPrice': cost_result['gas_price'],
                    'chainId': chain_id  # Required for replay protection
                }
                legacy_reason = "(forced for stability)" if force_legacy and fee_data.get('is_eip1559', False) else ""
                print(f"🔧 [INFO] {request_id}: Built legacy transaction with chainId: {chain_id} {legacy_reason}")
            
            # Log transaction details (without sensitive data)
            tx_type = "EIP-1559" if transaction.get('type') == 2 else "Legacy"
            print(f"🔍 [DEBUG] {request_id}: {tx_type} transaction - To: {transaction['to']}, Value: {self.w3.from_wei(transaction['value'], 'ether')} ETH, Nonce: {transaction['nonce']}, ChainId: {transaction['chainId']}")
            
            print(f"🔐 [INFO] {request_id}: Signing transaction...")
            
            # Sign transaction
            try:
                signed_txn = self.w3.eth.account.sign_transaction(transaction, self.private_key)
                print(f"✅ [DEBUG] {request_id}: Transaction signed successfully")
                
                # Log raw transaction for debugging (first 20 chars only for security)
                raw_tx_preview = signed_txn.rawTransaction.hex()[:20] + "..."
                print(f"🔍 [DEBUG] {request_id}: Raw transaction preview: 0x{raw_tx_preview}")
                
            except Exception as e:
                print(f"❌ [ERROR] {request_id}: Transaction signing failed: {e}")
                raise
            
            print(f"📡 [INFO] {request_id}: Broadcasting transaction...")
            
            # Send transaction (handle Web3.py version compatibility)
            try:
                # Web3.py 6.x uses 'rawTransaction'
                raw_tx = signed_txn.rawTransaction
            except AttributeError:
                # Fallback for older versions that use 'raw_transaction'
                raw_tx = signed_txn.raw_transaction
            
            tx_hash = self.w3.eth.send_raw_transaction(raw_tx)
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
    
    def send_erc20_token(self, recipient_address: str, amount_tokens: float, token_symbol: str, request_id: str = None) -> Dict[str, Any]:
        """
        Send ERC20 tokens to a specified address.
        
        Args:
            recipient_address: Address to send tokens to
            amount_tokens: Amount of tokens to send
            token_symbol: Token symbol (e.g., "USDT", "USDC")
            request_id: Optional request ID for tracking
            
        Returns:
            Dictionary with transaction result
        """
        try:
            request_id = request_id or f"TX_{int(time.time())}"
            print(f"🪙 [INFO] {request_id}: Preparing {token_symbol} transfer...")
            
            chain_id = self.w3.eth.chain_id
            token_info = self.token_registry.get_token_info(chain_id, token_symbol)
            
            if not token_info:
                return {
                    'success': False,
                    'error': f'Token {token_symbol} not supported on chain {chain_id}'
                }
            
            # Validate recipient address
            if not Web3.is_address(recipient_address):
                return {
                    'success': False,
                    'error': f"Invalid recipient address: {recipient_address}"
                }
            
            recipient_address = Web3.to_checksum_address(recipient_address)
            
            # Validate amount
            if amount_tokens <= 0:
                return {
                    'success': False,
                    'error': f"Invalid amount: {amount_tokens} {token_symbol}"
                }
            
            # Check token balance
            balance_result = self.get_erc20_balance(token_symbol)
            if not balance_result['success']:
                return {
                    'success': False,
                    'error': f"Failed to check {token_symbol} balance: {balance_result.get('error', 'Unknown error')}"
                }
            
            token_balance = balance_result['balance_tokens']
            if token_balance < amount_tokens:
                return {
                    'success': False,
                    'error': f"Insufficient {token_symbol} balance. Need: {amount_tokens:.8f}, Have: {token_balance:.8f}"
                }
            
            # Estimate transaction costs
            cost_result = self.estimate_erc20_transfer_cost(recipient_address, amount_tokens, token_symbol)
            if not cost_result['success']:
                return {
                    'success': False,
                    'error': f"Failed to estimate costs: {cost_result.get('error', 'Unknown error')}"
                }
            
            # Check ETH balance for gas
            eth_balance_result = self.get_wallet_balance()
            if not eth_balance_result['success']:
                return {
                    'success': False,
                    'error': f"Failed to check ETH balance for gas: {eth_balance_result.get('error', 'Unknown error')}"
                }
            
            eth_balance = eth_balance_result['balance_eth']
            gas_cost_eth = cost_result['gas_cost_eth']
            
            if eth_balance < gas_cost_eth:
                return {
                    'success': False,
                    'error': f"Insufficient ETH for gas. Need: {gas_cost_eth:.8f} ETH, Have: {eth_balance:.8f} ETH"
                }
            
            print(f"🪙 [INFO] {request_id}: Sending {amount_tokens:.8f} {token_symbol} to {recipient_address}")
            print(f"⛽ [INFO] {request_id}: Gas cost: {gas_cost_eth:.8f} ETH ({cost_result['gas_estimate']} gas @ {cost_result['gas_price_gwei']:.2f} gwei)")
            
            # Create contract instance
            token_contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(token_info.address),
                abi=ERC20_ABI
            )
            
            # Get current nonce
            nonce = self.w3.eth.get_transaction_count(self.host_address)
            
            # Convert amount to token's smallest unit
            amount_raw = int(amount_tokens * (10 ** token_info.decimals))
            
            # Build transaction with proper validation
            fee_data = cost_result['fee_data']
            
            # Ensure contract address is properly checksummed
            contract_address = Web3.to_checksum_address(token_info.address)
            
            # Encode the transfer function call with proper validation
            try:
                transfer_data = token_contract.encodeABI(fn_name='transfer', args=[recipient_address, amount_raw])
                print(f"🔍 [DEBUG] {request_id}: Transfer ABI encoded successfully - data length: {len(transfer_data)} bytes")
            except Exception as e:
                print(f"❌ [ERROR] {request_id}: Failed to encode transfer ABI: {e}")
                raise ValueError(f"Failed to encode ERC20 transfer: {e}")
            
            # Use legacy transactions for ERC20 (more reliable) with comprehensive validation
            transaction = {
                'from': Web3.to_checksum_address(self.host_address),  # Explicitly include from address
                'to': contract_address,  # Properly checksummed contract address
                'value': 0,  # No ETH transfer, just gas
                'nonce': nonce,
                'gas': cost_result['gas_estimate'],
                'gasPrice': cost_result['gas_price'],
                'chainId': chain_id,
                'data': transfer_data
            }
            
            # Validate transaction structure before signing
            required_fields = ['from', 'to', 'value', 'nonce', 'gas', 'gasPrice', 'chainId', 'data']
            for field in required_fields:
                if field not in transaction:
                    raise ValueError(f"Missing required transaction field: {field}")
                if transaction[field] is None:
                    raise ValueError(f"Transaction field {field} cannot be None")
            
            # Validate address fields
            if not Web3.is_address(transaction['from']):
                raise ValueError(f"Invalid from address: {transaction['from']}")
            if not Web3.is_address(transaction['to']):
                raise ValueError(f"Invalid to address: {transaction['to']}")
            
            # Validate numeric fields
            if transaction['gas'] <= 0:
                raise ValueError(f"Invalid gas limit: {transaction['gas']}")
            if transaction['gasPrice'] <= 0:
                raise ValueError(f"Invalid gas price: {transaction['gasPrice']}")
            if transaction['chainId'] <= 0:
                raise ValueError(f"Invalid chain ID: {transaction['chainId']}")
            
            # Validate data field format
            if not isinstance(transaction['data'], (str, bytes)):
                raise ValueError(f"Invalid data field type: {type(transaction['data'])}")
            if isinstance(transaction['data'], str) and not transaction['data'].startswith('0x'):
                raise ValueError(f"Data field must be hex string starting with 0x: {transaction['data'][:20]}...")
            
            print(f"✅ [VALIDATION] {request_id}: Transaction structure validated successfully")
            
            print(f"🔍 [DEBUG] {request_id}: ERC20 transfer transaction - From: {transaction['from']}, To: {transaction['to']}, Amount: {amount_tokens:.8f} {token_symbol}, Nonce: {transaction['nonce']}, ChainId: {transaction['chainId']}")
            
            print(f"🔐 [INFO] {request_id}: Signing transaction...")
            
            # Sign transaction with enhanced error handling for ERC20 transfers
            try:
                signed_txn = self.w3.eth.account.sign_transaction(transaction, self.private_key)
                print(f"✅ [DEBUG] {request_id}: Transaction signed successfully")
                
                # Validate signed transaction
                if not hasattr(signed_txn, 'rawTransaction'):
                    raise ValueError("Signed transaction missing rawTransaction field")
                
                # Ensure raw transaction is in proper hex format
                if isinstance(signed_txn.rawTransaction, bytes):
                    raw_tx_hex = signed_txn.rawTransaction.hex()
                else:
                    raw_tx_hex = signed_txn.rawTransaction
                
                if not raw_tx_hex.startswith('0x'):
                    raw_tx_hex = '0x' + raw_tx_hex
                
                # Log raw transaction for debugging (first 20 chars only for security)
                raw_tx_preview = raw_tx_hex[:22] + "..." if len(raw_tx_hex) > 22 else raw_tx_hex
                print(f"🔍 [DEBUG] {request_id}: Raw transaction preview: {raw_tx_preview}")
                print(f"🔍 [DEBUG] {request_id}: Raw transaction length: {len(raw_tx_hex)} characters")
                
            except Exception as e:
                error_str = str(e).lower()
                if "invalid fields" in error_str:
                    print(f"❌ [ERROR] {request_id}: ERC20 transaction has invalid fields")
                    print(f"🔍 [DEBUG] {request_id}: Transaction details for debugging:")
                    for field, value in transaction.items():
                        if field == 'data':
                            # Truncate data field for readability
                            data_preview = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
                            print(f"    {field}: {data_preview}")
                        else:
                            print(f"    {field}: {value}")
                    print(f"💡 [SUGGESTION] {request_id}: Check that all ERC20 transaction fields are properly formatted")
                    print(f"💡 [SUGGESTION] {request_id}: Verify USDC contract address and recipient address are valid")
                    print(f"💡 [SUGGESTION] {request_id}: Ensure ABI encoding is correct for transfer function")
                else:
                    print(f"❌ [ERROR] {request_id}: ERC20 transaction signing failed: {e}")
                
                raise ValueError(f"ERC20 transaction signing failed: {e}")
            
            print(f"📡 [INFO] {request_id}: Broadcasting transaction...")
            
            # Send transaction with enhanced error handling
            try:
                # Get raw transaction with proper validation
                try:
                    raw_tx = signed_txn.rawTransaction
                except AttributeError:
                    raw_tx = signed_txn.raw_transaction
                
                # Ensure raw transaction is in proper format
                if isinstance(raw_tx, str) and not raw_tx.startswith('0x'):
                    raw_tx = '0x' + raw_tx
                elif isinstance(raw_tx, bytes):
                    raw_tx = raw_tx.hex()
                    if not raw_tx.startswith('0x'):
                        raw_tx = '0x' + raw_tx
                
                print(f"🔍 [DEBUG] {request_id}: Broadcasting raw transaction of length {len(raw_tx)} characters")
                
                # Send the transaction
                tx_hash = self.w3.eth.send_raw_transaction(raw_tx)
                tx_hash_hex = tx_hash.hex()
                
            except Exception as broadcast_error:
                error_str = str(broadcast_error).lower()
                if "invalid fields" in error_str or "transaction had invalid fields" in error_str:
                    print(f"❌ [ERROR] {request_id}: Blockchain rejected ERC20 transaction due to invalid fields")
                    print(f"🔍 [DEBUG] {request_id}: Broadcast error: {broadcast_error}")
                    print(f"🔍 [DEBUG] {request_id}: This indicates the transaction structure doesn't meet blockchain requirements")
                    print(f"💡 [SUGGESTION] {request_id}: Check that contract address {contract_address} is valid")
                    print(f"💡 [SUGGESTION] {request_id}: Verify recipient address {recipient_address} is correct")
                    print(f"💡 [SUGGESTION] {request_id}: Ensure amount {amount_raw} is within valid range")
                    raise ValueError(f"ERC20 transaction rejected by blockchain: {broadcast_error}")
                else:
                    print(f"❌ [ERROR] {request_id}: Failed to broadcast ERC20 transaction: {broadcast_error}")
                    raise ValueError(f"ERC20 transaction broadcast failed: {broadcast_error}")
            
            print(f"⏳ [INFO] {request_id}: Transaction broadcast - Hash: {tx_hash_hex}")
            print(f"🔍 [INFO] {request_id}: Waiting for confirmation...")
            
            # Wait for transaction receipt (with timeout)
            try:
                tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
                
                if tx_receipt.status == 1:
                    # Transaction successful
                    actual_gas_used = tx_receipt.gasUsed
                    actual_gas_price = transaction.get('gasPrice', 0)
                    actual_gas_cost_wei = actual_gas_used * actual_gas_price
                    actual_gas_cost_eth = self.w3.from_wei(actual_gas_cost_wei, 'ether')
                    
                    print(f"✅ [SUCCESS] {request_id}: {token_symbol} transfer confirmed!")
                    print(f"⛽ [INFO] {request_id}: Actual gas used: {actual_gas_used} (cost: {float(actual_gas_cost_eth):.8f} ETH)")
                    
                    return {
                        'success': True,
                        'transaction_hash': tx_hash_hex,
                        'recipient': recipient_address,
                        'amount_tokens': amount_tokens,
                        'token_symbol': token_symbol,
                        'token_address': token_info.address,
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
                        'error': f'{token_symbol} transfer failed (status: 0)',
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
            error_msg = f"{token_symbol} transfer failed: {str(e)}"
            print(f"❌ [ERROR] {request_id or 'Unknown'}: {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'request_id': request_id
            }
    
    def initialize_dex_swapper(self, oneinch_api_key: str, swap_config: SwapConfig = None, config_manager=None) -> bool:
        """
        Initialize the DEX swapper for automatic token conversions with rate validation.
        
        Args:
            oneinch_api_key: 1INCH API key for DEX access
            swap_config: Optional swap configuration
            config_manager: Optional ConfigManager for market data API keys
            
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            if not oneinch_api_key:
                print("⚠️ [WARNING] No 1INCH API key provided - DEX swapping disabled")
                return False
            
            self.dex_swapper = DEXSwapper(
                w3=self.w3,
                oneinch_api_key=oneinch_api_key,
                host_address=self.host_address,
                private_key=self.private_key,
                swap_config=swap_config,
                config_manager=config_manager  # Pass config manager for market data validation
            )
            
            print("✅ [INFO] DEX swapper initialized successfully with rate validation")
            return True
            
        except Exception as e:
            print(f"❌ [ERROR] Failed to initialize DEX swapper: {e}")
            return False
    
    def ensure_token_balance(self, token_symbol: str, required_amount: float, 
                           request_id: str = None) -> Dict[str, Any]:
        """
        Ensure sufficient token balance by checking current balance and swapping ETH if needed.
        
        Args:
            token_symbol: Token symbol needed (e.g., "LINK", "USDT")
            required_amount: Required amount of tokens
            request_id: Optional request ID for tracking
            
        Returns:
            Dictionary with balance ensuring result
        """
        try:
            request_id = request_id or f"ENSURE_{int(time.time())}"
            
            print(f"🔍 [INFO] {request_id}: Ensuring {required_amount:.6f} {token_symbol} balance...")
            
            # Check current token balance
            balance_result = self.get_erc20_balance(token_symbol)
            if not balance_result['success']:
                return {
                    'success': False,
                    'error': f"Failed to check {token_symbol} balance: {balance_result.get('error', 'Unknown error')}",
                    'action_taken': 'none'
                }
            
            current_balance = balance_result['balance_tokens']
            print(f"💰 [INFO] {request_id}: Current {token_symbol} balance: {current_balance:.6f}")
            
            # Check if we already have enough
            if current_balance >= required_amount:
                print(f"✅ [INFO] {request_id}: Sufficient {token_symbol} balance available")
                return {
                    'success': True,
                    'message': 'Sufficient balance available',
                    'current_balance': current_balance,
                    'required_amount': required_amount,
                    'action_taken': 'none'
                }
            
            # Calculate deficit
            deficit = required_amount - current_balance
            print(f"📉 [INFO] {request_id}: {token_symbol} deficit: {deficit:.6f} (need {required_amount:.6f}, have {current_balance:.6f})")
            
            # Check if DEX swapper is available
            if not self.dex_swapper:
                return {
                    'success': False,
                    'error': 'DEX swapper not initialized - cannot acquire tokens automatically',
                    'current_balance': current_balance,
                    'required_amount': required_amount,
                    'deficit': deficit,
                    'action_taken': 'none'
                }
            
            # Check ETH balance for swapping
            eth_balance_result = self.get_wallet_balance()
            if not eth_balance_result['success']:
                return {
                    'success': False,
                    'error': 'Failed to check ETH balance for swapping',
                    'action_taken': 'none'
                }
            
            eth_balance = eth_balance_result['balance_eth']
            print(f"⛽ [INFO] {request_id}: ETH available for swapping: {eth_balance:.6f} ETH")
            
            # Ensure we have enough ETH (keep reserve for gas)
            min_eth_reserve = self.dex_swapper.config.min_eth_reserve
            if eth_balance <= min_eth_reserve:
                return {
                    'success': False,
                    'error': f'Insufficient ETH for swapping. Have {eth_balance:.6f} ETH, need at least {min_eth_reserve:.6f} ETH reserve',
                    'action_taken': 'none'
                }
            
            # Calculate ETH needed for the deficit (with some buffer)
            swap_amount = deficit * 1.05  # Add 5% buffer for slippage/estimation errors
            print(f"🔄 [INFO] {request_id}: Attempting to swap ETH for {swap_amount:.6f} {token_symbol}")
            
            # Execute the swap
            swap_result = self.dex_swapper.swap_eth_for_exact_tokens(token_symbol, swap_amount)
            
            if swap_result['success']:
                print(f"✅ [SUCCESS] {request_id}: Successfully swapped ETH for {token_symbol}")
                
                # Verify new balance
                new_balance_result = self.get_erc20_balance(token_symbol)
                if new_balance_result['success']:
                    new_balance = new_balance_result['balance_tokens']
                    print(f"💰 [INFO] {request_id}: New {token_symbol} balance: {new_balance:.6f}")
                    
                    return {
                        'success': True,
                        'message': 'Successfully acquired tokens via swap',
                        'initial_balance': current_balance,
                        'new_balance': new_balance,
                        'required_amount': required_amount,
                        'swap_result': swap_result,
                        'action_taken': 'eth_to_token_swap'
                    }
                else:
                    # Swap succeeded but balance check failed
                    return {
                        'success': True,
                        'message': 'Swap completed but balance verification failed',
                        'swap_result': swap_result,
                        'action_taken': 'eth_to_token_swap',
                        'warning': 'Could not verify new balance'
                    }
            else:
                return {
                    'success': False,
                    'error': f"Token swap failed: {swap_result.get('error', 'Unknown error')}",
                    'current_balance': current_balance,
                    'required_amount': required_amount,
                    'action_taken': 'swap_attempted_failed'
                }
                
        except Exception as e:
            error_msg = f"Balance ensuring failed: {str(e)}"
            print(f"❌ [ERROR] {request_id or 'Unknown'}: {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'action_taken': 'error'
            }
    
    def swap_eth_to_token(self, token_symbol: str, eth_amount: float, 
                         request_id: str = None) -> Dict[str, Any]:
        """
        Swap a specific amount of ETH for tokens.
        
        Args:
            token_symbol: Target token symbol
            eth_amount: Amount of ETH to swap
            request_id: Optional request ID for tracking
            
        Returns:
            Dictionary with swap result
        """
        try:
            request_id = request_id or f"SWAP_{int(time.time())}"
            
            if not self.dex_swapper:
                return {
                    'success': False,
                    'error': 'DEX swapper not initialized'
                }
            
            print(f"🔄 [INFO] {request_id}: Swapping {eth_amount:.6f} ETH for {token_symbol}")
            
            # Convert ETH amount to Wei
            eth_amount_wei = self.w3.to_wei(eth_amount, 'ether')
            
            # Execute swap
            swap_result = self.dex_swapper.execute_eth_to_token_swap(
                token_symbol=token_symbol,
                eth_amount_wei=eth_amount_wei
            )
            
            if swap_result['success']:
                print(f"✅ [SUCCESS] {request_id}: ETH to {token_symbol} swap completed")
            else:
                print(f"❌ [ERROR] {request_id}: ETH to {token_symbol} swap failed")
            
            return swap_result
            
        except Exception as e:
            error_msg = f"ETH to {token_symbol} swap failed: {str(e)}"
            print(f"❌ [ERROR] {request_id or 'Unknown'}: {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }