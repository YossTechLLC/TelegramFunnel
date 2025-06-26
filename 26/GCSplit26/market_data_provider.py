#!/usr/bin/env python
"""
Real-Time Market Data Provider - Multi-source cryptocurrency price fetching with validation.
Provides robust, validated price data from multiple APIs to prevent rate calculation errors.
"""
import time
import requests
import statistics
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from google.cloud import secretmanager

@dataclass
class PriceDataPoint:
    """Single price data point from an API source."""
    source: str
    token_symbol: str
    usd_per_token: float
    tokens_per_usd: float
    timestamp: datetime
    confidence: float = 1.0  # 0.0 to 1.0 confidence score
    raw_data: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AggregatedPrice:
    """Aggregated price from multiple sources."""
    token_symbol: str
    usd_per_token: float
    tokens_per_usd: float
    sources_used: List[str]
    confidence: float
    price_points: List[PriceDataPoint]
    timestamp: datetime
    validation_result: Dict[str, Any]

class RealTimeMarketDataProvider:
    """
    Real-time cryptocurrency market data provider with multi-source aggregation,
    validation, and robust error handling to prevent rate calculation errors.
    """
    
    def __init__(self, config_manager=None):
        """
        Initialize the market data provider.
        
        Args:
            config_manager: Optional ConfigManager instance for API key management
        """
        self.config_manager = config_manager
        self.cache = {}
        self.cache_duration = 60  # Cache for 60 seconds in production
        self.api_timeout = 10  # 10 second timeout per API
        self.max_price_deviation = 0.15  # 15% max deviation between sources
        
        # Price source configurations
        self.price_sources = {
            'coingecko': {
                'name': 'CoinGecko',
                'weight': 0.5,  # Higher weight since only 2 sources now
                'url': 'https://api.coingecko.com/api/v3/simple/price',
                'requires_api_key': False,
                'rate_limit': 50,  # requests per minute
                'enabled': True
            },
            'cryptocompare': {
                'name': 'CryptoCompare',
                'weight': 0.5,  # Equal weight with CoinGecko
                'url': 'https://min-api.cryptocompare.com/data/price',
                'requires_api_key': True,
                'rate_limit': 100,
                'enabled': True
            }
        }
        
        # Token symbol mappings for different APIs
        self.token_mappings = {
            'coingecko': {
                'ETH': 'ethereum',
                'WETH': 'weth',
                'BTC': 'bitcoin',
                'USDT': 'tether',
                'USDC': 'usd-coin',
                'DAI': 'dai',
                'LINK': 'chainlink',
                'UNI': 'uniswap',
                'AAVE': 'aave',
                'COMP': 'compound-governance-token',
                'SUSHI': 'sushi',
                'CRV': 'curve-dao-token',
                'SNX': 'havven',
                'MKR': 'maker',
                'YFI': 'yearn-finance'
            },
            'cryptocompare': {
                # CryptoCompare uses direct symbols
                'ETH': 'ETH',
                'WETH': 'WETH',
                'BTC': 'BTC',
                'USDT': 'USDT',
                'USDC': 'USDC',
                'DAI': 'DAI',
                'LINK': 'LINK',
                'UNI': 'UNI',
                'AAVE': 'AAVE',
                'COMP': 'COMP',
                'SUSHI': 'SUSHI',
                'CRV': 'CRV',
                'SNX': 'SNX',
                'MKR': 'MKR',
                'YFI': 'YFI'
            }
        }
        
        print("📊 [INFO] Real-Time Market Data Provider initialized")
        print(f"💼 [INFO] Enabled sources: {[src['name'] for src in self.price_sources.values() if src['enabled']]}")
    
    def _get_api_key(self, api_name: str) -> Optional[str]:
        """
        Get API key for a specific service.
        
        Args:
            api_name: Name of the API service
            
        Returns:
            API key if available, None otherwise
        """
        if not self.config_manager:
            return None
            
        try:
            # Try to get API key from config manager
            env_var_name = f"{api_name.upper()}_API_KEY"
            return self.config_manager.fetch_secret(env_var_name, required=False)
        except Exception as e:
            print(f"⚠️ [WARNING] Could not fetch {api_name} API key: {e}")
            return None
    
    def _fetch_coingecko_price(self, token_symbol: str) -> Optional[PriceDataPoint]:
        """Fetch price from CoinGecko API."""
        try:
            if token_symbol not in self.token_mappings['coingecko']:
                return None
            
            token_id = self.token_mappings['coingecko'][token_symbol]
            url = self.price_sources['coingecko']['url']
            
            params = {
                'ids': token_id,
                'vs_currencies': 'usd',
                'include_market_cap': 'false',
                'include_24hr_vol': 'false',
                'include_24hr_change': 'false'
            }
            
            response = requests.get(url, params=params, timeout=self.api_timeout)
            
            if response.status_code == 200:
                data = response.json()
                if token_id in data and 'usd' in data[token_id]:
                    usd_per_token = float(data[token_id]['usd'])
                    
                    return PriceDataPoint(
                        source='coingecko',
                        token_symbol=token_symbol,
                        usd_per_token=usd_per_token,
                        tokens_per_usd=1.0 / usd_per_token,
                        timestamp=datetime.utcnow(),
                        confidence=0.95,  # High confidence for CoinGecko
                        raw_data=data
                    )
            
            print(f"⚠️ [WARNING] CoinGecko API error: {response.status_code}")
            return None
            
        except Exception as e:
            print(f"❌ [ERROR] CoinGecko fetch failed for {token_symbol}: {e}")
            return None
    
    def _fetch_cryptocompare_price(self, token_symbol: str) -> Optional[PriceDataPoint]:
        """Fetch price from CryptoCompare API."""
        try:
            if token_symbol not in self.token_mappings['cryptocompare']:
                return None
            
            url = self.price_sources['cryptocompare']['url']
            symbol = self.token_mappings['cryptocompare'][token_symbol]
            
            params = {
                'fsym': symbol,
                'tsyms': 'USD'
            }
            
            # Add API key if available
            api_key = self._get_api_key('cryptocompare')
            headers = {}
            if api_key:
                headers['Authorization'] = f'Apikey {api_key}'
            
            response = requests.get(url, params=params, headers=headers, timeout=self.api_timeout)
            
            if response.status_code == 200:
                data = response.json()
                if 'USD' in data:
                    usd_per_token = float(data['USD'])
                    
                    return PriceDataPoint(
                        source='cryptocompare',
                        token_symbol=token_symbol,
                        usd_per_token=usd_per_token,
                        tokens_per_usd=1.0 / usd_per_token,
                        timestamp=datetime.utcnow(),
                        confidence=0.90,  # Good confidence for CryptoCompare
                        raw_data=data
                    )
            
            print(f"⚠️ [WARNING] CryptoCompare API error: {response.status_code}")
            return None
            
        except Exception as e:
            print(f"❌ [ERROR] CryptoCompare fetch failed for {token_symbol}: {e}")
            return None
    
    def _validate_price_consistency(self, price_points: List[PriceDataPoint]) -> Dict[str, Any]:
        """
        Validate consistency across multiple price sources.
        
        Args:
            price_points: List of price data points from different sources
            
        Returns:
            Validation result dictionary
        """
        if len(price_points) < 2:
            return {
                'consistent': True,
                'reason': 'Single source - no consistency check possible',
                'outliers': [],
                'deviation': 0.0
            }
        
        prices = [point.usd_per_token for point in price_points]
        median_price = statistics.median(prices)
        
        outliers = []
        max_deviation = 0.0
        
        for i, point in enumerate(price_points):
            deviation = abs(point.usd_per_token - median_price) / median_price
            max_deviation = max(max_deviation, deviation)
            
            if deviation > self.max_price_deviation:
                outliers.append({
                    'source': point.source,
                    'price': point.usd_per_token,
                    'deviation': deviation,
                    'median_price': median_price
                })
        
        is_consistent = len(outliers) == 0
        
        return {
            'consistent': is_consistent,
            'reason': f'Max deviation: {max_deviation:.1%}' if is_consistent else f'Found {len(outliers)} outlier(s)',
            'outliers': outliers,
            'deviation': max_deviation,
            'median_price': median_price,
            'total_sources': len(price_points)
        }
    
    def _aggregate_prices(self, price_points: List[PriceDataPoint], token_symbol: str) -> Optional[AggregatedPrice]:
        """
        Aggregate prices from multiple sources using weighted average.
        
        Args:
            price_points: List of price data points
            token_symbol: Token symbol being priced
            
        Returns:
            Aggregated price or None if no valid data
        """
        if not price_points:
            return None
        
        # Validate consistency
        validation = self._validate_price_consistency(price_points)
        
        # Remove outliers if consistency check failed
        valid_points = price_points.copy()
        if not validation['consistent']:
            outlier_sources = {outlier['source'] for outlier in validation['outliers']}
            valid_points = [point for point in price_points if point.source not in outlier_sources]
            print(f"⚠️ [WARNING] Removed {len(outlier_sources)} outlier source(s) for {token_symbol}: {outlier_sources}")
        
        if not valid_points:
            print(f"❌ [ERROR] No valid price points remaining for {token_symbol} after outlier removal")
            return None
        
        # Calculate weighted average
        total_weight = 0.0
        weighted_price_sum = 0.0
        
        for point in valid_points:
            source_config = self.price_sources.get(point.source, {})
            weight = source_config.get('weight', 0.1) * point.confidence
            weighted_price_sum += point.usd_per_token * weight
            total_weight += weight
        
        if total_weight == 0:
            return None
        
        final_usd_per_token = weighted_price_sum / total_weight
        final_tokens_per_usd = 1.0 / final_usd_per_token
        
        # Calculate overall confidence
        confidence = min(1.0, total_weight / len(valid_points))
        
        return AggregatedPrice(
            token_symbol=token_symbol,
            usd_per_token=final_usd_per_token,
            tokens_per_usd=final_tokens_per_usd,
            sources_used=[point.source for point in valid_points],
            confidence=confidence,
            price_points=valid_points,
            timestamp=datetime.utcnow(),
            validation_result=validation
        )
    
    def get_token_price(self, token_symbol: str, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get current token price with multi-source aggregation and validation.
        
        Args:
            token_symbol: Token symbol (e.g., "LINK", "ETH")
            force_refresh: Force refresh cache
            
        Returns:
            Dictionary with price data and metadata
        """
        cache_key = f"aggregated_{token_symbol.lower()}"
        
        # Check cache first
        if not force_refresh and cache_key in self.cache:
            cached_data = self.cache[cache_key]
            cache_age = time.time() - cached_data['timestamp']
            if cache_age < self.cache_duration:
                print(f"📋 [INFO] Using cached price for {token_symbol} (age: {cache_age:.1f}s)")
                return cached_data['data']
        
        print(f"📊 [INFO] Fetching real-time price for {token_symbol} from multiple sources...")
        
        # Fetch from all enabled sources concurrently
        price_points = []
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_to_source = {}
            
            # Submit requests to all enabled sources
            for source_key, source_config in self.price_sources.items():
                if not source_config['enabled']:
                    continue
                
                if source_key == 'coingecko':
                    future = executor.submit(self._fetch_coingecko_price, token_symbol)
                    future_to_source[future] = source_key
                elif source_key == 'cryptocompare':
                    future = executor.submit(self._fetch_cryptocompare_price, token_symbol)
                    future_to_source[future] = source_key
            
            # Collect results
            for future in as_completed(future_to_source):
                source_key = future_to_source[future]
                try:
                    result = future.result()
                    if result:
                        price_points.append(result)
                        print(f"✅ [INFO] Got {token_symbol} price from {source_key}: ${result.usd_per_token:.6f}")
                    else:
                        print(f"⚠️ [WARNING] No price data from {source_key} for {token_symbol}")
                except Exception as e:
                    print(f"❌ [ERROR] {source_key} failed for {token_symbol}: {e}")
        
        # Aggregate prices
        aggregated = self._aggregate_prices(price_points, token_symbol)
        
        if not aggregated:
            error_msg = f"Failed to get valid price data for {token_symbol} from any source"
            print(f"❌ [ERROR] {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'token_symbol': token_symbol,
                'sources_attempted': list(self.price_sources.keys())
            }
        
        # Prepare result
        result = {
            'success': True,
            'token_symbol': token_symbol,
            'usd_per_token': aggregated.usd_per_token,
            'tokens_per_usd': aggregated.tokens_per_usd,
            'sources_used': aggregated.sources_used,
            'confidence': aggregated.confidence,
            'validation': aggregated.validation_result,
            'timestamp': aggregated.timestamp.isoformat(),
            'cache_duration': self.cache_duration
        }
        
        # Cache the result
        self.cache[cache_key] = {
            'data': result,
            'timestamp': time.time()
        }
        
        print(f"🎯 [SUCCESS] {token_symbol} price: ${aggregated.usd_per_token:.6f} USD (sources: {', '.join(aggregated.sources_used)})")
        print(f"📊 [INFO] Confidence: {aggregated.confidence:.1%}, Validation: {aggregated.validation_result['reason']}")
        
        return result
    
    def convert_usd_to_token(self, usd_amount: float, token_symbol: str) -> Dict[str, Any]:
        """
        Convert USD amount to token amount using validated market rates.
        
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
        
        price_result = self.get_token_price(token_symbol)
        
        if not price_result['success']:
            return {
                'success': False,
                'error': f"Failed to get {token_symbol} price: {price_result.get('error', 'Unknown error')}"
            }
        
        tokens_per_usd = price_result['tokens_per_usd']
        token_amount = usd_amount * tokens_per_usd
        
        result = {
            'success': True,
            'usd_amount': usd_amount,
            'token_amount': round(token_amount, 8),
            'token_symbol': token_symbol,
            'tokens_per_usd': tokens_per_usd,
            'usd_per_token': price_result['usd_per_token'],
            'sources_used': price_result['sources_used'],
            'confidence': price_result['confidence'],
            'timestamp': price_result['timestamp']
        }
        
        print(f"💱 [INFO] Converted ${usd_amount:.2f} USD → {token_amount:.8f} {token_symbol}")
        print(f"📊 [INFO] Rate: {tokens_per_usd:.8f} {token_symbol}/USD (confidence: {price_result['confidence']:.1%})")
        
        return result
    
    def get_supported_tokens(self) -> List[str]:
        """Get list of supported tokens."""
        supported = set()
        for mapping in self.token_mappings.values():
            supported.update(mapping.keys())
        return sorted(list(supported))
    
    def get_provider_status(self) -> Dict[str, Any]:
        """Get status of all price providers."""
        return {
            'provider': 'RealTimeMarketDataProvider',
            'cache_items': len(self.cache),
            'cache_duration': self.cache_duration,
            'sources': {
                source_key: {
                    'name': config['name'],
                    'enabled': config['enabled'],
                    'weight': config['weight'],
                    'requires_api_key': config['requires_api_key']
                }
                for source_key, config in self.price_sources.items()
            },
            'supported_tokens': self.get_supported_tokens(),
            'total_supported_tokens': len(self.get_supported_tokens())
        }