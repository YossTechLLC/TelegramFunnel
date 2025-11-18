#!/usr/bin/env python
"""
Crypto Pricing Client for PGP_v1 Services.

Fetches cryptocurrency prices from CoinGecko API.
Consolidates duplicate logic from PGP_NP_IPN_v1 and PGP_INVITE_v1.
"""
import requests
from typing import Optional


class CryptoPricingClient:
    """
    Shared crypto price fetching and conversion logic.

    Used by: PGP_NP_IPN_v1, PGP_INVITE_v1

    Features:
    - Fetches real-time prices from CoinGecko API
    - Converts crypto amounts to USD
    - Handles stablecoins (USDT, USDC, etc.) as $1.00
    - Error handling for API failures
    - No authentication required (uses CoinGecko Free API)
    """

    def __init__(self):
        """
        Initialize CryptoPricingClient with symbol mapping.

        Combines symbol maps from both NP_IPN (uppercase) and INVITE (lowercase)
        to support both naming conventions.
        """
        # Comprehensive symbol map (merged from INVITE + NP_IPN)
        self.symbol_map = {
            # Lowercase (INVITE convention)
            'eth': 'ethereum',
            'btc': 'bitcoin',
            'ltc': 'litecoin',
            'bch': 'bitcoin-cash',
            'xrp': 'ripple',
            'bnb': 'binancecoin',
            'ada': 'cardano',
            'doge': 'dogecoin',
            'trx': 'tron',
            'usdt': 'tether',
            'usdc': 'usd-coin',
            'busd': 'binance-usd',
            'dai': 'dai',
            'sol': 'solana',
            'matic': 'matic-network',
            'avax': 'avalanche-2',
            'dot': 'polkadot',
            # Uppercase (NP_IPN convention) - mapped to same IDs
            'ETH': 'ethereum',
            'BTC': 'bitcoin',
            'LTC': 'litecoin',
            'TRX': 'tron',
            'BNB': 'binancecoin',
            'SOL': 'solana',
            'MATIC': 'matic-network',
            'USDT': 'tether',
            'USDC': 'usd-coin'
        }

        # CoinGecko API endpoint
        self.coingecko_api = "https://api.coingecko.com/api/v3/simple/price"

        # Stablecoin list (case-insensitive)
        self.stablecoins = {'usd', 'usdt', 'usdc', 'busd', 'dai'}

    def get_crypto_usd_price(self, crypto_symbol: str) -> Optional[float]:
        """
        Fetch current USD price from CoinGecko API.

        Handles both uppercase (NP_IPN) and lowercase (INVITE) symbols.

        Args:
            crypto_symbol: Crypto symbol (e.g., 'eth', 'ETH', 'btc', 'BTC')

        Returns:
            USD price or None if failed

        Examples:
            >>> client = CryptoPricingClient()
            >>> client.get_crypto_usd_price('ETH')
            2450.50
            >>> client.get_crypto_usd_price('eth')
            2450.50
        """
        try:
            # Get CoinGecko ID from symbol map (supports both cases)
            crypto_id = self.symbol_map.get(crypto_symbol)
            if not crypto_id:
                print(f"❌ [PRICE] Unknown crypto symbol: {crypto_symbol}")
                print(f"💡 [PRICE] Supported symbols: {', '.join(sorted(set(self.symbol_map.keys())))}")
                return None

            # Build API request
            url = f"{self.coingecko_api}?ids={crypto_id}&vs_currencies=usd"

            print(f"🔍 [PRICE] Fetching {crypto_symbol.upper()} price from CoinGecko...")

            # Make request with timeout
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                usd_price = data.get(crypto_id, {}).get('usd')

                if usd_price:
                    print(f"💰 [PRICE] {crypto_symbol.upper()}/USD = ${usd_price:,.2f}")
                    return float(usd_price)
                else:
                    print(f"❌ [PRICE] USD price not found in response")
                    return None
            else:
                print(f"❌ [PRICE] CoinGecko API error: {response.status_code}")
                return None

        except requests.exceptions.Timeout:
            print(f"❌ [PRICE] CoinGecko API timeout after 10 seconds")
            return None
        except requests.exceptions.RequestException as e:
            print(f"❌ [PRICE] Failed to fetch price from CoinGecko: {e}")
            return None
        except Exception as e:
            print(f"❌ [PRICE] Unexpected error fetching crypto price: {e}")
            return None

    def convert_crypto_to_usd(self, amount: float, crypto_symbol: str) -> Optional[float]:
        """
        Convert crypto amount to USD using current market rate.

        Automatically handles stablecoins (returns 1:1 with USD without API call).

        Args:
            amount: Crypto amount
            crypto_symbol: Crypto symbol (e.g., 'eth', 'ETH', 'btc', 'BTC')

        Returns:
            USD value or None if failed

        Examples:
            >>> client = CryptoPricingClient()
            >>> client.convert_crypto_to_usd(1.5, 'ETH')
            3675.75
            >>> client.convert_crypto_to_usd(100, 'USDT')
            100.0
        """
        try:
            # Check if stablecoin (1:1 with USD, no API call needed)
            if crypto_symbol.lower() in self.stablecoins:
                print(f"💰 [CONVERT] {crypto_symbol.upper()} is stablecoin, treating as 1:1 USD")
                return float(amount)

            # Get current market price
            usd_price = self.get_crypto_usd_price(crypto_symbol)
            if not usd_price:
                print(f"❌ [CONVERT] Could not fetch price for {crypto_symbol}")
                return None

            # Convert to USD
            usd_value = float(amount) * usd_price
            print(f"💰 [CONVERT] {amount} {crypto_symbol.upper()} = ${usd_value:.2f} USD")

            return usd_value

        except Exception as e:
            print(f"❌ [CONVERT] Conversion error: {e}")
            return None
