#!/usr/bin/env python
"""
Currency Manager for TelegramFunnel
Provides dynamic currency validation using ChangeNOW API with intelligent caching
"""
import asyncio
import time
from typing import Dict, Any, Optional, Tuple, Set, List
from changenow_manager import ChangeNOWManager


class CurrencyManager:
    """
    Manages cryptocurrency validation with ChangeNOW API integration.
    Features smart caching, fallback mechanisms, and both sync/async support.
    """
    
    def __init__(self):
        """Initialize the Currency Manager with caching and fallback systems."""
        self.changenow_manager = None
        self.cache_ttl = 3600  # 1 hour cache TTL
        self.last_cache_update = 0
        self.supported_currencies_cache: Set[str] = set()
        self.currency_details_cache: Dict[str, Dict] = {}
        self.cache_initialized = False
        
        # Extended fallback list of popular cryptocurrencies
        self.fallback_currencies = {
            # Major cryptocurrencies
            "btc", "eth", "xrp", "ltc", "ada", "dot", "link", "bch", "xmr", "etc",
            "trx", "bnb", "sol", "avax", "matic", "atom", "algo", "xtz", "icp", "ftm",
            "near", "luna", "axs", "sand", "mana", "enj", "chz", "bat", "zrx", "1inch",
            
            # Stablecoins (various networks)
            "usdt", "usdc", "dai", "busd", "tusd", "usdp", "frax", "lusd",
            "usdterc20", "usdtbsc", "usdttrc20", "usdtpolygon",
            "usdc", "usdcbsc", "usdcpolygon",
            
            # Exchange tokens
            "cro", "ftt", "ht", "okb", "kcs", "leo",
            
            # DeFi tokens
            "uni", "sushi", "cake", "comp", "aave", "mkr", "snx", "crv", "bal", "yfi",
            "inch", "rune", "alpha", "cream", "badger", "pickle", "bnt", "lrc",
            
            # Gaming/NFT tokens
            "axs", "slp", "sand", "mana", "enj", "chr", "alice", "tlm", "waxp",
            
            # Layer 2 and scaling
            "matic", "ftm", "one", "celo", "xdai", "movr", "metis",
            
            # Polkadot ecosystem
            "dot", "ksm", "acala", "moonbeam", "astar",
            
            # Cosmos ecosystem  
            "atom", "osmo", "juno", "scrt", "regen", "akash",
            
            # Solana ecosystem
            "sol", "ray", "srm", "cope", "fida", "maps", "media",
            
            # BSC ecosystem
            "bnb", "cake", "bake", "burger", "auto", "belt", "alpaca",
            
            # Ethereum tokens
            "shib", "lrc", "grt", "fet", "inj", "ocean", "rndr", "ankr"
        }
        
        print("💰 [INFO] CurrencyManager initialized with fallback support for 100+ currencies")
    
    async def _ensure_changenow_manager(self) -> bool:
        """Ensure ChangeNOW manager is initialized."""
        if self.changenow_manager is None:
            try:
                self.changenow_manager = ChangeNOWManager()
                print("✅ [INFO] ChangeNOW manager initialized for currency validation")
                return True
            except Exception as e:
                print(f"❌ [WARNING] Failed to initialize ChangeNOW manager: {e}")
                print("🔄 [INFO] Falling back to cached/hardcoded currency list")
                return False
        return True
    
    async def _update_currency_cache(self) -> bool:
        """Update the currency cache from ChangeNOW API."""
        try:
            if not await self._ensure_changenow_manager():
                return False
            
            print("🔄 [INFO] Updating currency cache from ChangeNOW API...")
            currencies_result = await self.changenow_manager.get_supported_currencies()
            
            if currencies_result["success"]:
                currencies = currencies_result["data"]
                
                # Clear and rebuild cache
                self.supported_currencies_cache.clear()
                self.currency_details_cache.clear()
                
                available_count = 0
                for curr in currencies:
                    ticker = curr.get("ticker", "").lower()
                    is_available = curr.get("isAvailable", False)
                    
                    if ticker:
                        # Add to supported currencies set
                        self.supported_currencies_cache.add(ticker)
                        
                        # Store detailed info
                        self.currency_details_cache[ticker] = {
                            "ticker": ticker,
                            "name": curr.get("name", "unknown"),
                            "network": curr.get("network", "unknown"),
                            "isAvailable": is_available,
                            "minAmount": curr.get("minAmount"),
                            "maxAmount": curr.get("maxAmount")
                        }
                        
                        if is_available:
                            available_count += 1
                
                self.last_cache_update = time.time()
                self.cache_initialized = True
                
                print(f"✅ [SUCCESS] Currency cache updated: {len(self.supported_currencies_cache)} total, {available_count} available")
                print(f"📋 [CACHE] Popular currencies cached: {', '.join(sorted(list(self.supported_currencies_cache.intersection(self.fallback_currencies))[:10]))}")
                
                return True
            else:
                print(f"❌ [ERROR] Failed to fetch currencies: {currencies_result['error']}")
                return False
                
        except Exception as e:
            print(f"❌ [ERROR] Cache update failed: {str(e)}")
            return False
    
    async def _is_cache_valid(self) -> bool:
        """Check if the currency cache is still valid."""
        if not self.cache_initialized:
            return False
        
        cache_age = time.time() - self.last_cache_update
        is_valid = cache_age < self.cache_ttl
        
        if not is_valid:
            print(f"⏰ [INFO] Currency cache expired (age: {cache_age/60:.1f} minutes)")
        
        return is_valid
    
    async def _ensure_cache_ready(self) -> bool:
        """Ensure currency cache is ready and up-to-date."""
        if await self._is_cache_valid():
            return True
        
        print("🔄 [INFO] Currency cache needs refresh...")
        return await self._update_currency_cache()
    
    async def is_currency_supported_async(self, currency: str) -> Tuple[bool, str]:
        """
        Async version: Check if a currency is supported.
        
        Args:
            currency: Currency ticker to validate
            
        Returns:
            Tuple of (is_supported, message)
        """
        if not currency:
            return False, "Currency cannot be empty"
        
        currency_lower = currency.strip().lower()
        
        print(f"🔍 [DEBUG] Validating currency: {currency.upper()}")
        
        # Try to ensure cache is ready
        cache_ready = await self._ensure_cache_ready()
        
        if cache_ready and currency_lower in self.supported_currencies_cache:
            # Check detailed availability
            details = self.currency_details_cache.get(currency_lower, {})
            is_available = details.get("isAvailable", False)
            network = details.get("network", "unknown")
            name = details.get("name", "unknown")
            
            if is_available:
                message = f"✅ Currency {currency.upper()} ({name}) is supported and available on {network}"
                print(f"✅ [CACHE_HIT] {message}")
                return True, message
            else:
                message = f"⚠️ Currency {currency.upper()} ({name}) is supported but temporarily unavailable on {network}"
                print(f"⚠️ [CACHE_HIT] {message}")
                return False, message
        
        # Fallback to hardcoded list if cache is not available
        if currency_lower in self.fallback_currencies:
            message = f"✅ Currency {currency.upper()} is supported (fallback validation)"
            print(f"✅ [FALLBACK] {message}")
            return True, message
        
        # Not found in any validation method
        cache_status = "with cache" if cache_ready else "with fallback only"
        message = f"❌ Currency {currency.upper()} is not supported ({cache_status})"
        print(f"❌ [NOT_SUPPORTED] {message}")
        
        # Provide helpful suggestions
        if cache_ready:
            popular_supported = sorted(list(self.supported_currencies_cache.intersection(self.fallback_currencies)))[:10]
            print(f"💡 [SUGGESTION] Popular supported currencies: {', '.join([c.upper() for c in popular_supported])}")
        else:
            fallback_list = sorted(list(self.fallback_currencies))[:10]
            print(f"💡 [FALLBACK_SUGGESTION] Common supported currencies: {', '.join([c.upper() for c in fallback_list])}")
        
        return False, message
    
    def is_currency_supported_sync(self, currency: str) -> Tuple[bool, str]:
        """
        Sync version: Check if a currency is supported.
        Uses cached data only, no API calls.
        
        Args:
            currency: Currency ticker to validate
            
        Returns:
            Tuple of (is_supported, message)
        """
        if not currency:
            return False, "Currency cannot be empty"
        
        currency_lower = currency.strip().lower()
        
        print(f"🔍 [SYNC] Validating currency: {currency.upper()}")
        
        # Check cache first
        if self.cache_initialized and currency_lower in self.supported_currencies_cache:
            details = self.currency_details_cache.get(currency_lower, {})
            is_available = details.get("isAvailable", False)
            network = details.get("network", "unknown")
            name = details.get("name", "unknown")
            
            if is_available:
                message = f"✅ Currency {currency.upper()} ({name}) is supported and available on {network}"
                print(f"✅ [SYNC_CACHE] {message}")
                return True, message
            else:
                message = f"⚠️ Currency {currency.upper()} ({name}) is supported but temporarily unavailable on {network}"
                print(f"⚠️ [SYNC_CACHE] {message}")
                return False, message
        
        # Fallback to hardcoded list
        if currency_lower in self.fallback_currencies:
            message = f"✅ Currency {currency.upper()} is supported (sync fallback validation)"
            print(f"✅ [SYNC_FALLBACK] {message}")
            return True, message
        
        message = f"❌ Currency {currency.upper()} is not supported"
        print(f"❌ [SYNC_NOT_SUPPORTED] {message}")
        return False, message
    
    async def get_supported_currencies_list(self) -> List[str]:
        """
        Get list of all supported currencies.
        
        Returns:
            List of supported currency tickers
        """
        await self._ensure_cache_ready()
        
        if self.cache_initialized:
            return sorted(list(self.supported_currencies_cache))
        else:
            return sorted(list(self.fallback_currencies))
    
    async def get_currency_details(self, currency: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a currency.
        
        Args:
            currency: Currency ticker
            
        Returns:
            Dictionary with currency details or None if not found
        """
        currency_lower = currency.strip().lower()
        
        await self._ensure_cache_ready()
        
        if self.cache_initialized and currency_lower in self.currency_details_cache:
            return self.currency_details_cache[currency_lower]
        
        return None
    
    async def refresh_cache(self) -> bool:
        """
        Force refresh the currency cache.
        
        Returns:
            True if refresh was successful
        """
        print("🔄 [INFO] Force refreshing currency cache...")
        self.cache_initialized = False
        return await self._update_currency_cache()
    
    def get_cache_status(self) -> Dict[str, Any]:
        """
        Get current cache status information.
        
        Returns:
            Dictionary with cache status details
        """
        cache_age = time.time() - self.last_cache_update if self.last_cache_update > 0 else 0
        
        return {
            "initialized": self.cache_initialized,
            "cache_age_minutes": cache_age / 60,
            "cache_valid": self.cache_initialized and cache_age < self.cache_ttl,
            "cached_currencies_count": len(self.supported_currencies_cache),
            "fallback_currencies_count": len(self.fallback_currencies),
            "last_update_timestamp": self.last_cache_update,
            "changenow_available": self.changenow_manager is not None
        }
    
    async def validate_currency_with_details(self, currency: str) -> Dict[str, Any]:
        """
        Comprehensive currency validation with detailed response.
        
        Args:
            currency: Currency ticker to validate
            
        Returns:
            Dictionary with validation results and details
        """
        is_supported, message = await self.is_currency_supported_async(currency)
        details = await self.get_currency_details(currency) if is_supported else None
        cache_status = self.get_cache_status()
        
        return {
            "currency": currency.upper(),
            "is_supported": is_supported,
            "message": message,
            "details": details,
            "validation_method": "cache" if cache_status["cache_valid"] else "fallback",
            "cache_status": cache_status
        }