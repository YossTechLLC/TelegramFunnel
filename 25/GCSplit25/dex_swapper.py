#!/usr/bin/env python
"""
DEX Swapper - Automated ETH to ERC20 token swapping using 1INCH DEX aggregator.
Handles automatic token acquisition for the payment splitting system.
"""
import time
import requests
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from web3 import Web3
from token_registry import TokenRegistry, TokenInfo

@dataclass
class SwapConfig:
    """Configuration for DEX swap parameters."""
    max_slippage_percent: float = 1.0  # 1% maximum slippage
    max_eth_per_swap: float = 0.1  # Maximum 0.1 ETH per swap
    min_eth_reserve: float = 0.01  # Keep 0.01 ETH minimum for gas
    swap_timeout_seconds: int = 30  # API timeout
    enable_swapping: bool = True  # Global swap enable/disable

class DEXSwapper:
    """Handles ETH to ERC20 token swaps using 1INCH DEX aggregator."""
    
    def __init__(self, w3: Web3, oneinch_api_key: str, host_address: str, private_key: str, 
                 swap_config: SwapConfig = None):
        """
        Initialize the DEX swapper.
        
        Args:
            w3: Web3 instance
            oneinch_api_key: 1INCH API key for DEX access
            host_address: Host wallet address
            private_key: Host wallet private key
            swap_config: Swap configuration parameters
        """
        self.w3 = w3
        self.oneinch_api_key = oneinch_api_key
        self.host_address = Web3.to_checksum_address(host_address)
        self.private_key = private_key
        self.config = swap_config or SwapConfig()
        self.token_registry = TokenRegistry()
        self.chain_id = w3.eth.chain_id
        
        # 1INCH API endpoints
        self.swap_api_base = f"https://api.1inch.dev/swap/v6.0/{self.chain_id}"
        self.quote_endpoint = f"{self.swap_api_base}/quote"
        self.swap_endpoint = f"{self.swap_api_base}/swap"
        
        print(f"🔄 [INFO] DEX Swapper initialized for chain {self.chain_id}")
        print(f"⚙️ [INFO] Swap config: max_slippage={self.config.max_slippage_percent}%, max_eth={self.config.max_eth_per_swap} ETH")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for 1INCH API requests."""
        return {
            'Authorization': f'Bearer {self.oneinch_api_key}',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
    
    def _get_token_address(self, token_symbol: str) -> Optional[str]:
        """
        Get token contract address for a given symbol.
        
        Args:
            token_symbol: Token symbol (e.g., "LINK", "USDT")
            
        Returns:
            Token contract address or None if not found
        """
        if token_symbol.upper() == "ETH":
            return "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"  # ETH address in 1INCH
        
        token_info = self.token_registry.get_token_info(self.chain_id, token_symbol)
        return token_info.address if token_info else None
    
    def get_swap_quote(self, from_token: str, to_token: str, amount_wei: int) -> Dict[str, Any]:
        """
        Get a swap quote from 1INCH without executing the swap.
        
        Args:
            from_token: Source token symbol (typically "ETH")
            to_token: Target token symbol (e.g., "LINK", "USDT")
            amount_wei: Amount to swap in Wei
            
        Returns:
            Dictionary with quote information
        """
        try:
            from_address = self._get_token_address(from_token)
            to_address = self._get_token_address(to_token)
            
            if not from_address or not to_address:
                return {
                    'success': False,
                    'error': f'Token address not found: from={from_token}, to={to_token}'
                }
            
            params = {
                'src': from_address,
                'dst': to_address,
                'amount': str(amount_wei),
                'includeTokensInfo': 'true',
                'includeProtocols': 'true',
                'includeGas': 'true'
            }
            
            print(f"🔍 [INFO] Getting 1INCH quote: {amount_wei} Wei {from_token} → {to_token}")
            
            response = requests.get(
                self.quote_endpoint,
                params=params,
                headers=self._get_headers(),
                timeout=self.config.swap_timeout_seconds
            )
            
            if response.status_code == 200:
                quote_data = response.json()
                
                # Extract key information
                from_amount = int(quote_data.get('fromTokenAmount', 0))
                to_amount = int(quote_data.get('toTokenAmount', 0))
                gas_estimate = int(quote_data.get('estimatedGas', 0))
                
                return {
                    'success': True,
                    'from_token': from_token,
                    'to_token': to_token,
                    'from_amount_wei': from_amount,
                    'to_amount_wei': to_amount,
                    'from_amount_eth': float(self.w3.from_wei(from_amount, 'ether')),
                    'gas_estimate': gas_estimate,
                    'quote_data': quote_data
                }
            else:
                error_msg = f"1INCH quote failed: {response.status_code} - {response.text}"
                print(f"❌ [ERROR] {error_msg}")
                return {
                    'success': False,
                    'error': error_msg,
                    'status_code': response.status_code
                }
                
        except Exception as e:
            error_msg = f"Quote request failed: {str(e)}"
            print(f"❌ [ERROR] {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
    
    def calculate_eth_needed_for_tokens(self, token_symbol: str, token_amount: float) -> Dict[str, Any]:
        """
        Calculate how much ETH is needed to acquire a specific amount of tokens.
        
        Args:
            token_symbol: Target token symbol
            token_amount: Desired amount of tokens
            
        Returns:
            Dictionary with ETH calculation results
        """
        try:
            token_info = self.token_registry.get_token_info(self.chain_id, token_symbol)
            if not token_info:
                return {
                    'success': False,
                    'error': f'Token {token_symbol} not supported on chain {self.chain_id}'
                }
            
            # Convert token amount to Wei (smallest unit)
            token_amount_wei = int(token_amount * (10 ** token_info.decimals))
            
            # Start with an initial ETH estimate (we'll iterate to find the right amount)
            # Use 0.001 ETH as starting point for quote
            initial_eth_wei = self.w3.to_wei(0.001, 'ether')
            
            # Get initial quote to understand the rate
            quote_result = self.get_swap_quote("ETH", token_symbol, initial_eth_wei)
            
            if not quote_result['success']:
                return quote_result
            
            # Calculate approximate ETH needed based on the rate
            initial_token_wei = quote_result['to_amount_wei']
            if initial_token_wei == 0:
                return {
                    'success': False,
                    'error': 'Quote returned zero tokens'
                }
            
            # Estimate ETH needed with slippage buffer
            estimated_eth_wei = int((token_amount_wei * initial_eth_wei) / initial_token_wei)
            slippage_buffer = 1 + (self.config.max_slippage_percent / 100)
            eth_needed_wei = int(estimated_eth_wei * slippage_buffer)
            
            # Get more accurate quote with estimated amount
            final_quote = self.get_swap_quote("ETH", token_symbol, eth_needed_wei)
            
            if final_quote['success']:
                eth_needed_eth = float(self.w3.from_wei(eth_needed_wei, 'ether'))
                tokens_received = final_quote['to_amount_wei'] / (10 ** token_info.decimals)
                
                print(f"💱 [INFO] ETH needed calculation: {eth_needed_eth:.6f} ETH → {tokens_received:.6f} {token_symbol}")
                print(f"🎯 [INFO] Target: {token_amount:.6f} {token_symbol}, Will receive: {tokens_received:.6f}")
                
                return {
                    'success': True,
                    'token_symbol': token_symbol,
                    'target_token_amount': token_amount,
                    'eth_needed_wei': eth_needed_wei,
                    'eth_needed_eth': eth_needed_eth,
                    'expected_tokens_received': tokens_received,
                    'tokens_received_wei': final_quote['to_amount_wei'],
                    'gas_estimate': final_quote['gas_estimate'],
                    'sufficient_output': tokens_received >= token_amount
                }
            else:
                return final_quote
                
        except Exception as e:
            error_msg = f"ETH calculation failed: {str(e)}"
            print(f"❌ [ERROR] {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
    
    def execute_eth_to_token_swap(self, token_symbol: str, eth_amount_wei: int, 
                                  min_token_amount_wei: int = 0) -> Dict[str, Any]:
        """
        Execute an ETH to ERC20 token swap.
        
        Args:
            token_symbol: Target token symbol
            eth_amount_wei: Amount of ETH to swap (in Wei)
            min_token_amount_wei: Minimum tokens to receive (slippage protection)
            
        Returns:
            Dictionary with swap transaction result
        """
        try:
            if not self.config.enable_swapping:
                return {
                    'success': False,
                    'error': 'Swapping is disabled in configuration'
                }
            
            eth_amount_eth = float(self.w3.from_wei(eth_amount_wei, 'ether'))
            
            # Safety checks
            if eth_amount_eth > self.config.max_eth_per_swap:
                return {
                    'success': False,
                    'error': f'Swap amount {eth_amount_eth:.6f} ETH exceeds maximum {self.config.max_eth_per_swap} ETH'
                }
            
            from_address = self._get_token_address("ETH")
            to_address = self._get_token_address(token_symbol)
            
            if not from_address or not to_address:
                return {
                    'success': False,
                    'error': f'Token address not found for {token_symbol}'
                }
            
            # Build swap parameters
            swap_params = {
                'src': from_address,
                'dst': to_address,
                'amount': str(eth_amount_wei),
                'from': self.host_address,
                'slippage': str(self.config.max_slippage_percent),
                'disableEstimate': 'false',
                'allowPartialFill': 'false'
            }
            
            if min_token_amount_wei > 0:
                swap_params['minTokenAmount'] = str(min_token_amount_wei)
            
            print(f"🔄 [INFO] Executing 1INCH swap: {eth_amount_eth:.6f} ETH → {token_symbol}")
            
            # Get swap transaction data
            response = requests.get(
                self.swap_endpoint,
                params=swap_params,
                headers=self._get_headers(),
                timeout=self.config.swap_timeout_seconds
            )
            
            if response.status_code != 200:
                error_msg = f"1INCH swap API failed: {response.status_code} - {response.text}"
                print(f"❌ [ERROR] {error_msg}")
                return {
                    'success': False,
                    'error': error_msg,
                    'status_code': response.status_code
                }
            
            swap_data = response.json()
            tx_data = swap_data.get('tx', {})
            
            if not tx_data:
                return {
                    'success': False,
                    'error': 'No transaction data received from 1INCH'
                }
            
            # Build and sign transaction
            transaction = {
                'from': self.host_address,
                'to': Web3.to_checksum_address(tx_data['to']),
                'value': int(tx_data['value']),
                'gas': int(tx_data['gas']),
                'gasPrice': int(tx_data['gasPrice']),
                'data': tx_data['data'],
                'nonce': self.w3.eth.get_transaction_count(self.host_address)
            }
            
            print(f"📝 [INFO] Swap transaction: gas={transaction['gas']}, gasPrice={transaction['gasPrice']}")
            
            # Sign and send transaction
            signed_txn = self.w3.eth.account.sign_transaction(transaction, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Wait for confirmation
            print(f"⏳ [INFO] Waiting for swap confirmation: {tx_hash.hex()}")
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if receipt['status'] == 1:
                gas_used = receipt['gasUsed']
                effective_gas_price = receipt.get('effectiveGasPrice', transaction['gasPrice'])
                
                print(f"✅ [SUCCESS] Swap completed! TX: {tx_hash.hex()}")
                print(f"⛽ [INFO] Gas used: {gas_used}, Effective price: {effective_gas_price}")
                
                return {
                    'success': True,
                    'transaction_hash': tx_hash.hex(),
                    'from_token': 'ETH',
                    'to_token': token_symbol,
                    'eth_amount_wei': eth_amount_wei,
                    'eth_amount_eth': eth_amount_eth,
                    'gas_used': gas_used,
                    'gas_price': effective_gas_price,
                    'block_number': receipt['blockNumber'],
                    'swap_data': swap_data
                }
            else:
                return {
                    'success': False,
                    'error': 'Swap transaction failed',
                    'transaction_hash': tx_hash.hex(),
                    'receipt': receipt
                }
                
        except Exception as e:
            error_msg = f"Swap execution failed: {str(e)}"
            print(f"❌ [ERROR] {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
    
    def swap_eth_for_exact_tokens(self, token_symbol: str, target_token_amount: float) -> Dict[str, Any]:
        """
        Swap ETH to get a specific amount of tokens.
        
        Args:
            token_symbol: Target token symbol
            target_token_amount: Exact amount of tokens needed
            
        Returns:
            Dictionary with swap result
        """
        try:
            print(f"🎯 [INFO] Starting swap for exactly {target_token_amount:.6f} {token_symbol}")
            
            # Calculate ETH needed
            calc_result = self.calculate_eth_needed_for_tokens(token_symbol, target_token_amount)
            
            if not calc_result['success']:
                return calc_result
            
            eth_needed = calc_result['eth_needed_wei']
            expected_tokens = calc_result['expected_tokens_received']
            
            # Safety check: ensure we're not using too much ETH
            eth_needed_eth = float(self.w3.from_wei(eth_needed, 'ether'))
            
            if eth_needed_eth > self.config.max_eth_per_swap:
                return {
                    'success': False,
                    'error': f'Required ETH {eth_needed_eth:.6f} exceeds maximum {self.config.max_eth_per_swap} ETH per swap'
                }
            
            # Calculate minimum tokens with slippage protection
            token_info = self.token_registry.get_token_info(self.chain_id, token_symbol)
            min_tokens = target_token_amount * 0.95  # Accept 5% less due to slippage
            min_token_wei = int(min_tokens * (10 ** token_info.decimals))
            
            # Execute the swap
            swap_result = self.execute_eth_to_token_swap(
                token_symbol=token_symbol,
                eth_amount_wei=eth_needed,
                min_token_amount_wei=min_token_wei
            )
            
            if swap_result['success']:
                print(f"🎉 [SUCCESS] Swapped {eth_needed_eth:.6f} ETH for {token_symbol}")
                
            return swap_result
            
        except Exception as e:
            error_msg = f"Exact token swap failed: {str(e)}"
            print(f"❌ [ERROR] {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }