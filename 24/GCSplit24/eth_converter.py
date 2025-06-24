#!/usr/bin/env python
"""
ETH Converter - USD to ETH conversion using 1INCH API and fallback services.
Handles real-time price conversion with caching and error handling.
"""
import time
import requests
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

class EthConverter:
    """Handles USD to ETH conversion using multiple price APIs."""
    
    def __init__(self, oneinch_api_key: str):
        """
        Initialize the ETH converter.
        
        Args:
            oneinch_api_key: API key for 1INCH services
        """
        self.oneinch_api_key = oneinch_api_key
        self.cache = {}
        self.cache_duration = 30  # Cache for 30 seconds
        
        # API endpoints and configurations
        self.oneinch_spot_url = "https://api.1inch.dev/price/v1.1/1"  # Ethereum mainnet
        self.fallback_apis = [
            {
                'name': 'CryptoCompare',
                'url': 'https://min-api.cryptocompare.com/data/price',
                'params': {'fsym': 'ETH', 'tsyms': 'USD'},
                'headers': {},
                'path': ['USD']
            },
            {
                'name': 'CoinGecko',
                'url': 'https://api.coingecko.com/api/v3/simple/price',
                'params': {'ids': 'ethereum', 'vs_currencies': 'usd'},
                'headers': {},
                'path': ['ethereum', 'usd']
            }
        ]
        
        print(f"💱 [INFO] ETH Converter initialized with 1INCH API and {len(self.fallback_apis)} fallback services")
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """
        Check if cached data is still valid.
        
        Args:
            cache_key: Key to check in cache
            
        Returns:
            True if cache is valid, False otherwise
        """
        if cache_key not in self.cache:
            return False
        
        cached_time = self.cache[cache_key].get('timestamp', 0)
        return time.time() - cached_time < self.cache_duration
    
    def _get_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Get data from cache if valid.
        
        Args:
            cache_key: Key to retrieve from cache
            
        Returns:
            Cached data if valid, None otherwise
        """
        if self._is_cache_valid(cache_key):
            print(f"📋 [INFO] Using cached ETH rate (age: {time.time() - self.cache[cache_key]['timestamp']:.1f}s)")
            return self.cache[cache_key]['data']
        return None
    
    def _save_to_cache(self, cache_key: str, data: Dict[str, Any]) -> None:
        """
        Save data to cache with timestamp.
        
        Args:
            cache_key: Key to store in cache
            data: Data to cache
        """
        self.cache[cache_key] = {
            'data': data,
            'timestamp': time.time()
        }
    
    def _get_oneinch_rate(self) -> Dict[str, Any]:
        """
        Get ETH/USD rate from 1INCH Spot Price API.
        
        Returns:
            Dictionary with success status and rate data
        """
        try:
            print("🔄 [INFO] Fetching ETH rate from 1INCH Spot Price API...")
            
            # 1INCH API uses token addresses - ETH is typically the native currency
            # For Ethereum mainnet, we'll use WETH address as a proxy for ETH
            weth_address = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
            
            url = f"{self.oneinch_spot_url}/{weth_address}"
            headers = {
                'Authorization': f'Bearer {self.oneinch_api_key}',
                'Accept': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # 1INCH Spot Price API returns price in USD
                if isinstance(data, dict) and 'price' in data:
                    usd_per_eth = float(data['price'])
                    eth_per_usd = 1.0 / usd_per_eth
                    
                    result = {
                        'success': True,
                        'eth_per_usd': eth_per_usd,
                        'usd_per_eth': usd_per_eth,
                        'source': '1INCH',
                        'timestamp': datetime.utcnow().isoformat(),
                        'raw_response': data
                    }
                    
                    print(f"✅ [INFO] 1INCH rate: 1 ETH = ${usd_per_eth:.2f} USD (1 USD = {eth_per_usd:.8f} ETH)")
                    return result
                else:
                    return {
                        'success': False,
                        'error': f'Unexpected response format from 1INCH API: {data}',
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
    
    def _get_fallback_rate(self, api_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get ETH rate from a fallback API.
        
        Args:
            api_config: Configuration for the fallback API
            
        Returns:
            Dictionary with success status and rate data
        """
        try:
            print(f"🔄 [INFO] Fetching ETH rate from {api_config['name']}...")
            
            response = requests.get(
                api_config['url'],
                params=api_config['params'],
                headers=api_config['headers'],
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Navigate to the USD price using the path
                usd_price = data
                for key in api_config['path']:
                    if isinstance(usd_price, dict) and key in usd_price:
                        usd_price = usd_price[key]
                    else:
                        raise ValueError(f"Cannot find path {api_config['path']} in response")
                
                usd_per_eth = float(usd_price)
                eth_per_usd = 1.0 / usd_per_eth
                
                result = {
                    'success': True,
                    'eth_per_usd': eth_per_usd,
                    'usd_per_eth': usd_per_eth,
                    'source': api_config['name'],
                    'timestamp': datetime.utcnow().isoformat(),
                    'raw_response': data
                }
                
                print(f"✅ [INFO] {api_config['name']} rate: 1 ETH = ${usd_per_eth:.2f} USD (1 USD = {eth_per_usd:.8f} ETH)")
                return result
            else:
                return {
                    'success': False,
                    'error': f"{api_config['name']} API returned status {response.status_code}: {response.text}",
                    'status_code': response.status_code
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f"{api_config['name']} API error: {str(e)}"
            }
    
    def get_usd_to_eth_rate(self) -> Dict[str, Any]:
        """
        Get current USD to ETH conversion rate.
        
        Returns:
            Dictionary containing:
            - success: bool
            - eth_per_usd: float (if successful)
            - usd_per_eth: float (if successful)
            - source: str (API source used)
            - timestamp: str (ISO format)
            - error: str (if failed)
        """
        cache_key = 'eth_usd_rate'
        
        # Check cache first
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            return cached_result
        
        # Try 1INCH API first
        print("💱 [INFO] Getting ETH conversion rate...")
        result = self._get_oneinch_rate()
        
        if result['success']:
            self._save_to_cache(cache_key, result)
            return result
        
        print(f"⚠️ [WARNING] 1INCH API failed: {result.get('error', 'Unknown error')}")
        print("🔄 [INFO] Trying fallback APIs...")
        
        # Try fallback APIs
        for api_config in self.fallback_apis:
            fallback_result = self._get_fallback_rate(api_config)
            
            if fallback_result['success']:
                print(f"✅ [INFO] Successfully got rate from fallback API: {api_config['name']}")
                self._save_to_cache(cache_key, fallback_result)
                return fallback_result
            else:
                print(f"⚠️ [WARNING] {api_config['name']} failed: {fallback_result.get('error', 'Unknown error')}")
        
        # All APIs failed
        error_msg = "All ETH price APIs failed"
        print(f"❌ [ERROR] {error_msg}")
        
        return {
            'success': False,
            'error': error_msg,
            'attempted_sources': ['1INCH'] + [api['name'] for api in self.fallback_apis]
        }
    
    def convert_usd_to_eth(self, usd_amount: float) -> Dict[str, Any]:
        """
        Convert USD amount to ETH.
        
        Args:
            usd_amount: Amount in USD to convert
            
        Returns:
            Dictionary with conversion result
        """
        if usd_amount <= 0:
            return {
                'success': False,
                'error': 'USD amount must be positive'
            }
        
        rate_result = self.get_usd_to_eth_rate()
        
        if not rate_result['success']:
            return {
                'success': False,
                'error': f"Failed to get conversion rate: {rate_result.get('error', 'Unknown error')}"
            }
        
        eth_per_usd = rate_result['eth_per_usd']
        eth_amount = usd_amount * eth_per_usd
        
        result = {
            'success': True,
            'usd_amount': usd_amount,
            'eth_amount': eth_amount,
            'eth_per_usd': eth_per_usd,
            'usd_per_eth': rate_result.get('usd_per_eth'),
            'source': rate_result.get('source'),
            'timestamp': rate_result.get('timestamp')
        }
        
        print(f"💰 [INFO] Converted ${usd_amount:.2f} USD → {eth_amount:.8f} ETH (rate: {eth_per_usd:.8f})")
        
        return result
    
    def get_rate_history_summary(self) -> Dict[str, Any]:
        """
        Get summary of recent rate requests and cache status.
        
        Returns:
            Dictionary with cache and request statistics
        """
        cache_info = {}
        
        for key, cached_item in self.cache.items():
            age_seconds = time.time() - cached_item['timestamp']
            cache_info[key] = {
                'age_seconds': round(age_seconds, 1),
                'is_valid': age_seconds < self.cache_duration,
                'source': cached_item['data'].get('source', 'unknown'),
                'rate': cached_item['data'].get('eth_per_usd', 'unknown')
            }
        
        return {
            'cache_duration_seconds': self.cache_duration,
            'cached_items': cache_info,
            'available_sources': ['1INCH'] + [api['name'] for api in self.fallback_apis]
        }