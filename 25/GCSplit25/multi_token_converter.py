#!/usr/bin/env python
"""
Multi-Token Converter - USD to any ERC20 token conversion using 1INCH API and fallbacks.
Extends the existing eth_converter.py to support multiple ERC20 tokens.
"""
import time
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime
from token_registry import TokenRegistry, TokenInfo

class MultiTokenConverter:
    """Handles USD to ERC20 token conversion using multiple price APIs."""
    
    def __init__(self, oneinch_api_key: str, chain_id: int = 1):
        """
        Initialize the multi-token converter.
        
        Args:
            oneinch_api_key: API key for 1INCH services
            chain_id: Blockchain network ID (default: 1 for Ethereum Mainnet)
        """
        self.oneinch_api_key = oneinch_api_key
        self.chain_id = chain_id
        self.token_registry = TokenRegistry()
        self.cache = {}
        self.cache_duration = 30  # Cache for 30 seconds
        
        # API endpoints
        self.oneinch_spot_url = f"https://api.1inch.dev/price/v1.1/{chain_id}"
        self.fallback_apis = [
            {
                'name': 'CryptoCompare',
                'url': 'https://min-api.cryptocompare.com/data/price',
                'headers': {},
                'supports_custom_tokens': False
            },
            {
                'name': 'CoinGecko',
                'url': 'https://api.coingecko.com/api/v3/simple/price',
                'headers': {},
                'supports_custom_tokens': True
            }
        ]
        
        print(f"🪙 [INFO] Multi-Token Converter initialized for chain {chain_id} with {len(self.token_registry.get_supported_tokens(chain_id))} supported tokens")
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid."""
        if cache_key not in self.cache:
            return False
        cached_time = self.cache[cache_key].get('timestamp', 0)
        return time.time() - cached_time < self.cache_duration
    
    def _get_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get data from cache if valid."""
        if self._is_cache_valid(cache_key):
            print(f"📋 [INFO] Using cached rate for {cache_key} (age: {time.time() - self.cache[cache_key]['timestamp']:.1f}s)")
            return self.cache[cache_key]['data']
        return None
    
    def _save_to_cache(self, cache_key: str, data: Dict[str, Any]) -> None:
        """Save data to cache with timestamp."""
        self.cache[cache_key] = {
            'data': data,
            'timestamp': time.time()
        }
    
    def _get_oneinch_token_rate(self, token_symbol: str) -> Dict[str, Any]:
        """
        Get token/USD rate from 1INCH Spot Price API.
        
        Args:
            token_symbol: Token symbol (e.g., "USDT", "USDC")
            
        Returns:
            Dictionary with success status and rate data
        """
        try:
            # Handle ETH as a special case
            if token_symbol.upper() == "ETH":
                # Use WETH address for ETH pricing
                token_info = self.token_registry.get_token_info(self.chain_id, "WETH")
            else:
                token_info = self.token_registry.get_token_info(self.chain_id, token_symbol)
            
            if not token_info:
                return {
                    'success': False,
                    'error': f'Token {token_symbol} not supported on chain {self.chain_id}'
                }
            
            print(f"🔄 [INFO] Fetching {token_symbol} rate from 1INCH Spot Price API...")
            
            url = f"{self.oneinch_spot_url}/{token_info.address}"
            headers = {
                'Authorization': f'Bearer {self.oneinch_api_key}',
                'Accept': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # 1INCH API typically returns price in USD
                if isinstance(data, dict) and token_info.address.lower() in data:
                    # The API might return prices in different formats
                    price_data = data[token_info.address.lower()]
                    
                    # Try to parse the price - format may vary
                    if isinstance(price_data, (int, float)):
                        usd_per_token = float(price_data)
                    elif isinstance(price_data, str):
                        try:
                            # If it's a wei amount, convert based on decimals
                            if len(price_data) > 10:  # Likely wei amount
                                usd_per_token = float(price_data) / (10 ** 18)  # Assume 18 decimals for USD representation
                            else:
                                usd_per_token = float(price_data)
                        except ValueError:
                            return {
                                'success': False,
                                'error': f'Cannot parse 1INCH price data: {price_data}'
                            }
                    else:
                        return {
                            'success': False,
                            'error': f'Unexpected 1INCH price format: {type(price_data)}'
                        }
                    
                    if usd_per_token <= 0:
                        return {
                            'success': False,
                            'error': f'Invalid price from 1INCH: {usd_per_token}'
                        }
                    
                    tokens_per_usd = 1.0 / usd_per_token
                    
                    result = {
                        'success': True,
                        'tokens_per_usd': tokens_per_usd,
                        'usd_per_token': usd_per_token,
                        'token_symbol': token_symbol,
                        'source': '1INCH',
                        'timestamp': datetime.utcnow().isoformat(),
                        'raw_response': data
                    }
                    
                    print(f"✅ [INFO] 1INCH rate: 1 {token_symbol} = ${usd_per_token:.6f} USD (1 USD = {tokens_per_usd:.6f} {token_symbol})")
                    return result
                else:
                    return {
                        'success': False,
                        'error': f'Unexpected 1INCH response format: {data}',
                        'status_code': response.status_code
                    }
            else:
                return {
                    'success': False,
                    'error': f'1INCH API returned status {response.status_code}: {response.text}',
                    'status_code': response.status_code
                }
                
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'1INCH API request failed: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'1INCH API processing error: {str(e)}'
            }
    
    def _get_fallback_token_rate(self, token_symbol: str, api_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get token rate from a fallback API.
        
        Args:
            token_symbol: Token symbol to get rate for
            api_config: Configuration for the fallback API
            
        Returns:
            Dictionary with success status and rate data
        """
        try:
            print(f"🔄 [INFO] Fetching {token_symbol} rate from {api_config['name']}...")
            
            if api_config['name'] == 'CryptoCompare':
                # CryptoCompare API
                params = {'fsym': token_symbol, 'tsyms': 'USD'}
                response = requests.get(api_config['url'], params=params, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'USD' in data:
                        usd_per_token = float(data['USD'])
                        tokens_per_usd = 1.0 / usd_per_token
                        
                        result = {
                            'success': True,
                            'tokens_per_usd': tokens_per_usd,
                            'usd_per_token': usd_per_token,
                            'token_symbol': token_symbol,
                            'source': api_config['name'],
                            'timestamp': datetime.utcnow().isoformat()
                        }
                        
                        print(f"✅ [INFO] {api_config['name']} rate: 1 {token_symbol} = ${usd_per_token:.6f} USD")
                        return result
            
            elif api_config['name'] == 'CoinGecko':
                # CoinGecko API
                token_info = self.token_registry.get_token_info(self.chain_id, token_symbol)
                if token_info and token_info.coingecko_id:
                    params = {'ids': token_info.coingecko_id, 'vs_currencies': 'usd'}
                    response = requests.get(api_config['url'], params=params, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        if token_info.coingecko_id in data and 'usd' in data[token_info.coingecko_id]:
                            usd_per_token = float(data[token_info.coingecko_id]['usd'])
                            tokens_per_usd = 1.0 / usd_per_token
                            
                            result = {
                                'success': True,
                                'tokens_per_usd': tokens_per_usd,
                                'usd_per_token': usd_per_token,
                                'token_symbol': token_symbol,
                                'source': api_config['name'],
                                'timestamp': datetime.utcnow().isoformat()
                            }
                            
                            print(f"✅ [INFO] {api_config['name']} rate: 1 {token_symbol} = ${usd_per_token:.6f} USD")
                            return result
                else:
                    return {
                        'success': False,
                        'error': f'No CoinGecko ID available for {token_symbol}'
                    }
            
            return {
                'success': False,
                'error': f'{api_config["name"]} API returned status {response.status_code}: {response.text}',
                'status_code': response.status_code
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'{api_config["name"]} API error: {str(e)}'
            }
    
    def get_usd_to_token_rate(self, token_symbol: str) -> Dict[str, Any]:
        """
        Get current USD to token conversion rate.
        
        Args:
            token_symbol: Token symbol (e.g., "USDT", "ETH", "USDC")
            
        Returns:
            Dictionary containing:
            - success: bool
            - tokens_per_usd: float (if successful)
            - usd_per_token: float (if successful)
            - token_symbol: str
            - source: str (API source used)
            - timestamp: str (ISO format)
            - error: str (if failed)
        """
        cache_key = f'{token_symbol.lower()}_usd_rate'
        
        # Check cache first
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            return cached_result
        
        # Handle ETH specially (legacy compatibility)
        if token_symbol.upper() == "ETH":
            print("💱 [INFO] Getting ETH conversion rate...")
        else:
            print(f"🪙 [INFO] Getting {token_symbol} conversion rate...")
        
        # Check if token is supported
        if not self.token_registry.is_token_supported(self.chain_id, token_symbol) and token_symbol.upper() != "ETH":
            error_msg = f"Token {token_symbol} not supported on chain {self.chain_id}"
            print(f"❌ [ERROR] {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'supported_tokens': self.token_registry.get_supported_tokens(self.chain_id)
            }
        
        # Try 1INCH API first
        result = self._get_oneinch_token_rate(token_symbol)
        
        if result['success']:
            self._save_to_cache(cache_key, result)
            return result
        
        print(f"⚠️ [WARNING] 1INCH API failed for {token_symbol}: {result.get('error', 'Unknown error')}")
        print("🔄 [INFO] Trying fallback APIs...")
        
        # Try fallback APIs
        for api_config in self.fallback_apis:
            fallback_result = self._get_fallback_token_rate(token_symbol, api_config)
            
            if fallback_result['success']:
                print(f"✅ [INFO] Successfully got {token_symbol} rate from fallback API: {api_config['name']}")
                self._save_to_cache(cache_key, fallback_result)
                return fallback_result
            else:
                print(f"⚠️ [WARNING] {api_config['name']} failed for {token_symbol}: {fallback_result.get('error', 'Unknown error')}")
        
        # All APIs failed
        error_msg = f"All {token_symbol} price APIs failed"
        print(f"❌ [ERROR] {error_msg}")
        
        return {
            'success': False,
            'error': error_msg,
            'token_symbol': token_symbol,
            'attempted_sources': ['1INCH'] + [api['name'] for api in self.fallback_apis]
        }
    
    def convert_usd_to_token(self, usd_amount: float, token_symbol: str) -> Dict[str, Any]:
        """
        Convert USD amount to token amount.
        
        Args:
            usd_amount: Amount in USD to convert
            token_symbol: Target token symbol
            
        Returns:
            Dictionary with conversion result
        """
        if usd_amount <= 0:
            return {
                'success': False,
                'error': 'USD amount must be positive'
            }
        
        rate_result = self.get_usd_to_token_rate(token_symbol)
        
        if not rate_result['success']:
            return {
                'success': False,
                'error': f"Failed to get {token_symbol} conversion rate: {rate_result.get('error', 'Unknown error')}"
            }
        
        tokens_per_usd = rate_result['tokens_per_usd']
        token_amount = usd_amount * tokens_per_usd
        
        # Get token info for proper decimal formatting
        token_info = self.token_registry.get_token_info(self.chain_id, token_symbol)
        if token_info:
            # Format based on token decimals
            formatted_amount = round(token_amount, min(8, token_info.decimals))
        else:
            formatted_amount = round(token_amount, 8)
        
        result = {
            'success': True,
            'usd_amount': usd_amount,
            'token_amount': formatted_amount,
            'token_symbol': token_symbol,
            'tokens_per_usd': tokens_per_usd,
            'usd_per_token': rate_result.get('usd_per_token'),
            'source': rate_result.get('source'),
            'timestamp': rate_result.get('timestamp')
        }
        
        print(f"💰 [INFO] Converted ${usd_amount:.2f} USD → {formatted_amount:.8f} {token_symbol}")
        
        return result
    
    def get_supported_tokens(self) -> List[str]:
        """Get list of supported tokens for current chain."""
        tokens = self.token_registry.get_supported_tokens(self.chain_id)
        # Add ETH as it's always supported
        if "ETH" not in tokens:
            tokens.append("ETH")
        return sorted(tokens)
    
    def get_registry_summary(self) -> Dict[str, Any]:
        """Get summary of token registry and converter status."""
        return {
            'chain_id': self.chain_id,
            'supported_tokens': self.get_supported_tokens(),
            'total_supported_tokens': len(self.get_supported_tokens()),
            'cache_items': len(self.cache),
            'registry_summary': self.token_registry.get_token_summary()
        }