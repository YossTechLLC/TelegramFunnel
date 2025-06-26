#!/usr/bin/env python
"""
Multi-Token Converter - USD to any ERC20 token conversion using robust multi-source pricing.
Provides validated, real-time cryptocurrency prices from multiple trusted sources.
"""
import time
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime
from token_registry import TokenRegistry, TokenInfo
from market_data_provider import RealTimeMarketDataProvider

class MultiTokenConverter:
    """Handles USD to ERC20 token conversion using robust multi-source pricing."""
    
    def __init__(self, oneinch_api_key: str = None, chain_id: int = 1, config_manager=None):
        """
        Initialize the multi-token converter with robust market data provider.
        
        Args:
            oneinch_api_key: Legacy parameter for backward compatibility (optional)
            chain_id: Blockchain network ID (default: 1 for Ethereum Mainnet)
            config_manager: ConfigManager instance for API key management
        """
        self.chain_id = chain_id
        self.token_registry = TokenRegistry()
        self.config_manager = config_manager
        
        # Initialize robust market data provider
        self.market_data_provider = RealTimeMarketDataProvider(config_manager=config_manager)
        
        # Legacy 1INCH support (kept as fallback)
        self.oneinch_api_key = oneinch_api_key
        self.oneinch_spot_url = f"https://api.1inch.dev/price/v1.1/{chain_id}" if oneinch_api_key else None
        
        # Legacy cache for backward compatibility
        self.cache = {}
        self.cache_duration = 60  # Increased from 30 to 60 seconds
        
        print(f"🪙 [INFO] Multi-Token Converter initialized with robust multi-source pricing")
        print(f"📊 [INFO] Chain: {chain_id}, Supported tokens: {len(self.token_registry.get_supported_tokens(chain_id))}")
        print(f"🔧 [INFO] Market data sources: {len([s for s in self.market_data_provider.price_sources.values() if s['enabled']])}")
    
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
    
    def _validate_token_price(self, token_symbol: str, usd_per_token: float) -> Dict[str, Any]:
        """
        Validate token price against known reasonable ranges.
        
        Args:
            token_symbol: Token symbol to validate
            usd_per_token: Price in USD per token
            
        Returns:
            Dictionary with validation result
        """
        # Define reasonable price ranges for major tokens (updated as of 2024)
        price_ranges = {
            'ETH': {'min': 1000, 'max': 10000},      # ETH: $1,000 - $10,000
            'WETH': {'min': 1000, 'max': 10000},     # WETH same as ETH
            'BTC': {'min': 20000, 'max': 200000},    # BTC: $20,000 - $200,000
            'USDT': {'min': 0.95, 'max': 1.05},      # USDT: $0.95 - $1.05
            'USDC': {'min': 0.95, 'max': 1.05},      # USDC: $0.95 - $1.05
            'DAI': {'min': 0.95, 'max': 1.05},       # DAI: $0.95 - $1.05
            'LINK': {'min': 5, 'max': 50},           # LINK: $5 - $50
            'UNI': {'min': 3, 'max': 30},            # UNI: $3 - $30
            'AAVE': {'min': 50, 'max': 500},         # AAVE: $50 - $500
            'COMP': {'min': 30, 'max': 300},         # COMP: $30 - $300
            'SUSHI': {'min': 0.5, 'max': 10},        # SUSHI: $0.5 - $10
            'CRV': {'min': 0.2, 'max': 5},           # CRV: $0.2 - $5
            'SNX': {'min': 1, 'max': 20},            # SNX: $1 - $20
            'MKR': {'min': 500, 'max': 5000},        # MKR: $500 - $5,000
            'YFI': {'min': 3000, 'max': 50000},      # YFI: $3,000 - $50,000
        }
        
        # Get expected range for this token
        token_upper = token_symbol.upper()
        if token_upper in price_ranges:
            price_range = price_ranges[token_upper]
            
            if usd_per_token < price_range['min']:
                return {
                    'valid': False,
                    'reason': f'{token_symbol} price ${usd_per_token:.6f} below expected minimum ${price_range["min"]}',
                    'expected_range': price_range,
                    'severity': 'high'
                }
            elif usd_per_token > price_range['max']:
                return {
                    'valid': False,
                    'reason': f'{token_symbol} price ${usd_per_token:.6f} above expected maximum ${price_range["max"]}',
                    'expected_range': price_range,
                    'severity': 'high'
                }
            else:
                return {
                    'valid': True,
                    'reason': f'{token_symbol} price ${usd_per_token:.6f} within expected range ${price_range["min"]}-${price_range["max"]}',
                    'expected_range': price_range,
                    'severity': 'none'
                }
        else:
            # Unknown token - perform basic sanity checks
            if usd_per_token < 0.00001:  # Less than $0.00001
                return {
                    'valid': False,
                    'reason': f'{token_symbol} price ${usd_per_token:.6f} suspiciously low (possible decimal error)',
                    'expected_range': None,
                    'severity': 'medium'
                }
            elif usd_per_token > 1000000:  # More than $1M
                return {
                    'valid': False,
                    'reason': f'{token_symbol} price ${usd_per_token:.6f} suspiciously high (possible decimal error)',
                    'expected_range': None,
                    'severity': 'medium'
                }
            else:
                return {
                    'valid': True,
                    'reason': f'{token_symbol} price ${usd_per_token:.6f} passes basic sanity checks',
                    'expected_range': None,
                    'severity': 'none'
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
            print(f"🔍 [DEBUG] Token address: {token_info.address}, Decimals: {token_info.decimals}")
            
            url = f"{self.oneinch_spot_url}/{token_info.address}"
            headers = {
                'Authorization': f'Bearer {self.oneinch_api_key}',
                'Accept': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                print(f"🔍 [DEBUG] 1INCH raw response: {data}")
                
                # 1INCH API typically returns price in USD
                if isinstance(data, dict) and token_info.address.lower() in data:
                    # The API might return prices in different formats
                    price_data = data[token_info.address.lower()]
                    print(f"🔍 [DEBUG] Price data for {token_symbol}: {price_data} (type: {type(price_data)})")
                    
                    # Parse price data with proper decimal handling
                    usd_per_token = None
                    
                    if isinstance(price_data, (int, float)):
                        # Direct numeric value - check if it's in wei or USD
                        raw_value = float(price_data)
                        
                        # Apply intelligent conversion based on value magnitude
                        if raw_value > 1e15:  # Likely wei amount (> 1000 ETH equivalent)
                            # Convert from wei to USD using token decimals
                            usd_per_token = raw_value / (10 ** token_info.decimals)
                            print(f"🔄 [INFO] Converted {token_symbol} from wei: {raw_value} → ${usd_per_token:.6f}")
                        else:
                            # Direct USD value
                            usd_per_token = raw_value
                            print(f"✅ [INFO] Direct USD value for {token_symbol}: ${usd_per_token:.6f}")
                            
                    elif isinstance(price_data, str):
                        try:
                            raw_value = float(price_data)
                            
                            # Apply same logic as numeric values
                            if raw_value > 1e15:  # Likely wei amount
                                usd_per_token = raw_value / (10 ** token_info.decimals)
                                print(f"🔄 [INFO] Converted {token_symbol} from string wei: {price_data} → ${usd_per_token:.6f}")
                            else:
                                usd_per_token = raw_value
                                print(f"✅ [INFO] String USD value for {token_symbol}: {price_data} → ${usd_per_token:.6f}")
                                
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
                    
                    # Validate price reasonableness
                    if usd_per_token is None or usd_per_token <= 0:
                        return {
                            'success': False,
                            'error': f'Invalid price from 1INCH: {usd_per_token}'
                        }
                    
                    # Sanity check: validate against known token price ranges
                    validation_result = self._validate_token_price(token_symbol, usd_per_token)
                    if not validation_result['valid']:
                        print(f"⚠️ [WARNING] 1INCH price validation failed: {validation_result['reason']}")
                        print(f"🔍 [DEBUG] Questionable price: {token_symbol} = ${usd_per_token:.6f}")
                        # Don't return error, but log the concern
                    
                    tokens_per_usd = 1.0 / usd_per_token
                    
                    result = {
                        'success': True,
                        'tokens_per_usd': tokens_per_usd,
                        'usd_per_token': usd_per_token,
                        'token_symbol': token_symbol,
                        'source': '1INCH',
                        'timestamp': datetime.utcnow().isoformat(),
                        'raw_response': data,
                        'price_validation': validation_result
                    }
                    
                    print(f"✅ [INFO] 1INCH rate: 1 {token_symbol} = ${usd_per_token:.6f} USD (1 USD = {tokens_per_usd:.6f} {token_symbol})")
                    return result
                else:
                    return {
                        'success': False,
                        'error': f'Unexpected 1INCH response format - missing token address key: {data}',
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
        Get current USD to token conversion rate using robust multi-source pricing.
        
        Args:
            token_symbol: Token symbol (e.g., "USDT", "ETH", "USDC")
            
        Returns:
            Dictionary containing:
            - success: bool
            - tokens_per_usd: float (if successful)
            - usd_per_token: float (if successful)
            - token_symbol: str
            - sources_used: list (API sources used)
            - confidence: float (price confidence score)
            - timestamp: str (ISO format)
            - error: str (if failed)
        """
        # Use robust market data provider for real-time validated pricing
        print(f"📊 [INFO] Getting validated {token_symbol} conversion rate from multiple sources...")
        
        # Check if token is supported by either the registry or market data provider
        registry_supported = self.token_registry.is_token_supported(self.chain_id, token_symbol)
        provider_supported = token_symbol.upper() in self.market_data_provider.get_supported_tokens()
        
        if not registry_supported and not provider_supported and token_symbol.upper() != "ETH":
            error_msg = f"Token {token_symbol} not supported on chain {self.chain_id}"
            print(f"❌ [ERROR] {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'supported_tokens': self.token_registry.get_supported_tokens(self.chain_id),
                'provider_supported_tokens': self.market_data_provider.get_supported_tokens()
            }
        
        # Get price from robust market data provider
        price_result = self.market_data_provider.get_token_price(token_symbol)
        
        if price_result['success']:
            # Convert to expected format for backward compatibility
            result = {
                'success': True,
                'tokens_per_usd': price_result['tokens_per_usd'],
                'usd_per_token': price_result['usd_per_token'],
                'token_symbol': token_symbol,
                'sources_used': price_result['sources_used'],  # Multiple sources
                'source': f"Multi-source ({', '.join(price_result['sources_used'])})",  # Legacy compatibility
                'confidence': price_result['confidence'],
                'validation': price_result['validation'],
                'timestamp': price_result['timestamp'],
                'provider': 'RealTimeMarketDataProvider'
            }
            
            print(f"✅ [SUCCESS] Got validated {token_symbol} rate: ${price_result['usd_per_token']:.6f} USD")
            print(f"📊 [INFO] Sources: {', '.join(price_result['sources_used'])}, Confidence: {price_result['confidence']:.1%}")
            
            return result
        
        # If robust provider fails, try legacy 1INCH as fallback (if available)
        if self.oneinch_api_key:
            print(f"⚠️ [WARNING] Multi-source provider failed for {token_symbol}: {price_result.get('error', 'Unknown error')}")
            print("🔄 [INFO] Trying legacy 1INCH API as fallback...")
            
            legacy_result = self._get_oneinch_token_rate(token_symbol)
            
            if legacy_result['success']:
                print(f"✅ [INFO] Got {token_symbol} rate from legacy 1INCH fallback")
                return legacy_result
            else:
                print(f"❌ [ERROR] Legacy 1INCH fallback also failed: {legacy_result.get('error', 'Unknown error')}")
        
        # All methods failed
        error_msg = f"Failed to get {token_symbol} rate from all available sources"
        print(f"❌ [ERROR] {error_msg}")
        
        return {
            'success': False,
            'error': error_msg,
            'token_symbol': token_symbol,
            'attempted_sources': ['RealTimeMarketDataProvider'] + (['1INCH-legacy'] if self.oneinch_api_key else []),
            'provider_error': price_result.get('error', 'Unknown error')
        }
    
    def convert_usd_to_token(self, usd_amount: float, token_symbol: str) -> Dict[str, Any]:
        """
        Convert USD amount to token amount using robust multi-source pricing.
        
        Args:
            usd_amount: Amount in USD to convert
            token_symbol: Target token symbol
            
        Returns:
            Dictionary with conversion result including validation info
        """
        if usd_amount <= 0:
            return {
                'success': False,
                'error': 'USD amount must be positive'
            }
        
        # Use market data provider directly for better integration
        conversion_result = self.market_data_provider.convert_usd_to_token(usd_amount, token_symbol)
        
        if conversion_result['success']:
            # Get token info for additional metadata
            token_info = self.token_registry.get_token_info(self.chain_id, token_symbol)
            
            # Enhance result with registry information
            enhanced_result = conversion_result.copy()
            enhanced_result.update({
                'chain_id': self.chain_id,
                'token_info': {
                    'decimals': token_info.decimals if token_info else 18,
                    'address': token_info.address if token_info else None,
                    'name': token_info.name if token_info else token_symbol
                } if token_info else None,
                'provider_type': 'MultiTokenConverter-v2-Robust'
            })
            
            print(f"💰 [SUCCESS] Robust conversion: ${usd_amount:.2f} USD → {conversion_result['token_amount']:.8f} {token_symbol}")
            print(f"📊 [INFO] Multi-source rate with {conversion_result['confidence']:.1%} confidence")
            
            return enhanced_result
        
        else:
            # If market data provider fails, fall back to legacy method
            print(f"⚠️ [WARNING] Market data provider conversion failed: {conversion_result.get('error', 'Unknown error')}")
            print("🔄 [INFO] Falling back to legacy conversion method...")
            
            # Use legacy rate fetching method
            rate_result = self.get_usd_to_token_rate(token_symbol)
            
            if not rate_result['success']:
                return {
                    'success': False,
                    'error': f"Failed to get {token_symbol} conversion rate: {rate_result.get('error', 'Unknown error')}",
                    'fallback_attempted': True
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
                'sources_used': rate_result.get('sources_used', [rate_result.get('source', 'unknown')]),
                'source': rate_result.get('source'),  # Legacy compatibility
                'confidence': rate_result.get('confidence', 0.5),
                'timestamp': rate_result.get('timestamp'),
                'fallback_used': True,
                'provider_type': 'MultiTokenConverter-v2-Legacy'
            }
            
            print(f"💰 [INFO] Legacy conversion: ${usd_amount:.2f} USD → {formatted_amount:.8f} {token_symbol}")
            
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