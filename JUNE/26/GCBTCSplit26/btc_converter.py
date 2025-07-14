#!/usr/bin/env python
"""
BTC Converter - USD to WBTC conversion with real-time market data.
Handles Bitcoin price fetching and conversion calculations for the BTC payout system.
"""
import time
import requests
from typing import Dict, Any, Optional
from decimal import Decimal, ROUND_DOWN


class BTCConverter:
    """Handles USD to WBTC conversion with multiple price sources."""
    
    def __init__(self, config_manager=None):
        """
        Initialize the BTC converter.
        
        Args:
            config_manager: Optional ConfigManager for API key access
        """
        self.config_manager = config_manager
        self.last_rate_fetch = 0
        self.cached_rate = None
        self.cache_duration = 30  # 30 second cache
        
        # Price source endpoints
        self.price_sources = {
            'coingecko': {
                'url': 'https://api.coingecko.com/api/v3/simple/price',
                'params': {'ids': 'bitcoin,wrapped-bitcoin', 'vs_currencies': 'usd'},
                'enabled': True
            },
            'cryptocompare': {
                'url': 'https://min-api.cryptocompare.com/data/price',
                'params': {'fsym': 'BTC', 'tsyms': 'USD'},
                'enabled': True
            }
        }
        
        print("₿ [INFO] BTC Converter initialized with multiple price sources")
    
    def get_usd_to_wbtc_rate(self) -> Dict[str, Any]:
        """
        Get current USD to WBTC conversion rate.
        
        Returns:
            Dictionary with success status, rate, and metadata
        """
        try:
            # Check cache first
            current_time = time.time()
            if (self.cached_rate and 
                current_time - self.last_rate_fetch < self.cache_duration):
                print(f"📊 [INFO] Using cached BTC rate: ${self.cached_rate['usd_per_btc']:.2f}/BTC")
                return {
                    'success': True,
                    'wbtc_per_usd': self.cached_rate['wbtc_per_usd'],
                    'usd_per_btc': self.cached_rate['usd_per_btc'],
                    'source': self.cached_rate['source'],
                    'timestamp': self.cached_rate['timestamp'],
                    'cached': True
                }
            
            # Try each price source
            for source_name, source_config in self.price_sources.items():
                if not source_config['enabled']:
                    continue
                
                try:
                    print(f"💱 [INFO] Fetching BTC price from {source_name}...")
                    rate_data = self._fetch_from_source(source_name, source_config)
                    
                    if rate_data:
                        # Cache the successful result
                        self.cached_rate = rate_data
                        self.last_rate_fetch = current_time
                        
                        print(f"✅ [INFO] BTC rate fetched: ${rate_data['usd_per_btc']:.2f}/BTC from {source_name}")
                        return {
                            'success': True,
                            'wbtc_per_usd': rate_data['wbtc_per_usd'],
                            'usd_per_btc': rate_data['usd_per_btc'],
                            'source': source_name,
                            'timestamp': current_time,
                            'cached': False
                        }
                        
                except Exception as e:
                    print(f"⚠️ [WARNING] Failed to fetch from {source_name}: {e}")
                    continue
            
            # If all sources fail, try to use cached data if available
            if self.cached_rate:
                age_minutes = (current_time - self.last_rate_fetch) / 60
                print(f"⚠️ [WARNING] Using stale cached rate (age: {age_minutes:.1f} minutes)")
                return {
                    'success': True,
                    'wbtc_per_usd': self.cached_rate['wbtc_per_usd'],
                    'usd_per_btc': self.cached_rate['usd_per_btc'],
                    'source': f"{self.cached_rate['source']} (stale)",
                    'timestamp': self.cached_rate['timestamp'],
                    'cached': True
                }
            
            return {
                'success': False,
                'error': 'All price sources failed and no cached data available'
            }
            
        except Exception as e:
            print(f"❌ [ERROR] BTC rate fetch failed: {e}")
            return {
                'success': False,
                'error': f'Rate fetch error: {str(e)}'
            }
    
    def _fetch_from_source(self, source_name: str, source_config: Dict) -> Optional[Dict]:
        """
        Fetch rate from a specific price source.
        
        Args:
            source_name: Name of the price source
            source_config: Configuration for the source
            
        Returns:
            Rate data dictionary or None if failed
        """
        try:
            response = requests.get(
                source_config['url'],
                params=source_config['params'],
                timeout=10,
                headers={'User-Agent': 'TPBTCS1-BTC-Service/1.0'}
            )
            response.raise_for_status()
            data = response.json()
            
            if source_name == 'coingecko':
                btc_price = data.get('bitcoin', {}).get('usd')
                if btc_price:
                    wbtc_per_usd = Decimal('1') / Decimal(str(btc_price))
                    return {
                        'wbtc_per_usd': float(wbtc_per_usd),
                        'usd_per_btc': btc_price,
                        'source': source_name
                    }
            
            elif source_name == 'cryptocompare':
                btc_price = data.get('USD')
                if btc_price:
                    wbtc_per_usd = Decimal('1') / Decimal(str(btc_price))
                    return {
                        'wbtc_per_usd': float(wbtc_per_usd),
                        'usd_per_btc': btc_price,
                        'source': source_name
                    }
            
            return None
            
        except Exception as e:
            print(f"❌ [ERROR] {source_name} fetch failed: {e}")
            return None
    
    def convert_usd_to_wbtc(self, usd_amount: float) -> Dict[str, Any]:
        """
        Convert USD amount to WBTC tokens.
        
        Args:
            usd_amount: USD amount to convert
            
        Returns:
            Dictionary with conversion results
        """
        try:
            if usd_amount <= 0:
                return {
                    'success': False,
                    'error': 'Invalid USD amount'
                }
            
            # Get current rate
            rate_result = self.get_usd_to_wbtc_rate()
            if not rate_result['success']:
                return rate_result
            
            wbtc_per_usd = rate_result['wbtc_per_usd']
            usd_per_btc = rate_result['usd_per_btc']
            
            # Calculate WBTC amount with proper decimal handling
            usd_decimal = Decimal(str(usd_amount))
            rate_decimal = Decimal(str(wbtc_per_usd))
            wbtc_amount = usd_decimal * rate_decimal
            
            # Round down to 8 decimal places (WBTC decimals)
            wbtc_amount = wbtc_amount.quantize(Decimal('0.00000001'), rounding=ROUND_DOWN)
            
            print(f"💱 [INFO] Converting ${usd_amount:.2f} USD to WBTC")
            print(f"📊 [INFO] Rate: {wbtc_per_usd:.8f} WBTC/USD (${usd_per_btc:.2f}/BTC)")
            print(f"🎯 [INFO] Result: {float(wbtc_amount):.8f} WBTC")
            
            return {
                'success': True,
                'wbtc_amount': float(wbtc_amount),
                'wbtc_per_usd': wbtc_per_usd,
                'usd_per_btc': usd_per_btc,
                'source': rate_result['source'],
                'timestamp': rate_result['timestamp']
            }
            
        except Exception as e:
            print(f"❌ [ERROR] USD to WBTC conversion failed: {e}")
            return {
                'success': False,
                'error': f'Conversion error: {str(e)}'
            }
    
    def validate_btc_amount(self, wbtc_amount: float, min_amount: float = 0.00000001) -> bool:
        """
        Validate WBTC amount is above minimum threshold.
        
        Args:
            wbtc_amount: WBTC amount to validate
            min_amount: Minimum WBTC amount (default 1 satoshi equivalent)
            
        Returns:
            True if valid, False otherwise
        """
        try:
            if wbtc_amount < min_amount:
                print(f"⚠️ [WARNING] WBTC amount {wbtc_amount:.8f} below minimum {min_amount:.8f}")
                return False
            
            # Check for reasonable maximum (prevent accidental large transfers)
            max_amount = 1.0  # 1 WBTC maximum per transaction
            if wbtc_amount > max_amount:
                print(f"⚠️ [WARNING] WBTC amount {wbtc_amount:.8f} exceeds maximum {max_amount:.8f}")
                return False
            
            return True
            
        except Exception as e:
            print(f"❌ [ERROR] WBTC amount validation failed: {e}")
            return False
    
    def get_market_summary(self) -> Dict[str, Any]:
        """
        Get current market summary for monitoring.
        
        Returns:
            Dictionary with market data
        """
        try:
            rate_result = self.get_usd_to_wbtc_rate()
            
            return {
                'btc_price_usd': rate_result.get('usd_per_btc', 0),
                'wbtc_per_usd': rate_result.get('wbtc_per_usd', 0),
                'last_update': rate_result.get('timestamp', 0),
                'data_source': rate_result.get('source', 'unknown'),
                'cache_status': 'cached' if rate_result.get('cached', False) else 'fresh'
            }
            
        except Exception as e:
            print(f"❌ [ERROR] Market summary failed: {e}")
            return {
                'error': str(e)
            }