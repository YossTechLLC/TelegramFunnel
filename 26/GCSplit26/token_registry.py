#!/usr/bin/env python
"""
ERC20 Token Registry - Comprehensive token contract addresses and metadata.
Supports major ERC20 tokens across different networks.
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

@dataclass
class TokenInfo:
    """Token information dataclass."""
    symbol: str
    name: str
    address: str
    decimals: int
    is_stablecoin: bool = False
    coingecko_id: str = ""

class TokenRegistry:
    """Registry for ERC20 token contract addresses and metadata."""
    
    def __init__(self):
        """Initialize the token registry with supported tokens."""
        self.tokens_by_network = self._initialize_token_registry()
        print("🪙 [INFO] Token Registry initialized with supported ERC20 tokens")
    
    def _initialize_token_registry(self) -> Dict[int, Dict[str, TokenInfo]]:
        """
        Initialize token registry with contract addresses by network.
        
        Returns:
            Dictionary mapping chain_id to token symbol to TokenInfo
        """
        return {
            # Ethereum Mainnet (Chain ID: 1)
            1: {
                "USDT": TokenInfo(
                    symbol="USDT",
                    name="Tether USD",
                    address="0xdAC17F958D2ee523a2206206994597C13D831ec7",
                    decimals=6,
                    is_stablecoin=True,
                    coingecko_id="tether"
                ),
                "USDC": TokenInfo(
                    symbol="USDC",
                    name="USD Coin",
                    address="0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",  # FIXED: Official USDC contract address (Circle verified)
                    decimals=6,
                    is_stablecoin=True,
                    coingecko_id="usd-coin"
                ),
                "DAI": TokenInfo(
                    symbol="DAI",
                    name="Dai Stablecoin",
                    address="0x6B175474E89094C44Da98b954EedeAC495271d0F",
                    decimals=18,
                    is_stablecoin=True,
                    coingecko_id="dai"
                ),
                "WETH": TokenInfo(
                    symbol="WETH",
                    name="Wrapped Ether",
                    address="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                    decimals=18,
                    coingecko_id="weth"
                ),
                "LINK": TokenInfo(
                    symbol="LINK",
                    name="Chainlink Token",
                    address="0x514910771AF9Ca656af840dff83E8264EcF986CA",
                    decimals=18,
                    coingecko_id="chainlink"
                ),
                "UNI": TokenInfo(
                    symbol="UNI",
                    name="Uniswap",
                    address="0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
                    decimals=18,
                    coingecko_id="uniswap"
                ),
                "AAVE": TokenInfo(
                    symbol="AAVE",
                    name="Aave Token",
                    address="0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9",
                    decimals=18,
                    coingecko_id="aave"
                ),
                "COMP": TokenInfo(
                    symbol="COMP",
                    name="Compound",
                    address="0xc00e94Cb662C3520282E6f5717214004A7f26888",
                    decimals=18,
                    coingecko_id="compound-governance-token"
                ),
                "MATIC": TokenInfo(
                    symbol="MATIC",
                    name="Polygon",
                    address="0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0",
                    decimals=18,
                    coingecko_id="matic-network"
                ),
                "SHIB": TokenInfo(
                    symbol="SHIB",
                    name="Shiba Inu",
                    address="0x95aD61b0a150d79219dCF64E1E6Cc01f0B64C4cE",
                    decimals=18,
                    coingecko_id="shiba-inu"
                )
            },
            # Polygon Mainnet (Chain ID: 137)
            137: {
                "USDT": TokenInfo(
                    symbol="USDT",
                    name="Tether USD (PoS)",
                    address="0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
                    decimals=6,
                    is_stablecoin=True,
                    coingecko_id="tether"
                ),
                "USDC": TokenInfo(
                    symbol="USDC",
                    name="USD Coin (PoS)",
                    address="0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
                    decimals=6,
                    is_stablecoin=True,
                    coingecko_id="usd-coin"
                ),
                "WETH": TokenInfo(
                    symbol="WETH",
                    name="Wrapped Ether",
                    address="0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
                    decimals=18,
                    coingecko_id="weth"
                ),
                "WMATIC": TokenInfo(
                    symbol="WMATIC",
                    name="Wrapped Matic",
                    address="0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",
                    decimals=18,
                    coingecko_id="wmatic"
                )
            },
            # BSC Mainnet (Chain ID: 56)
            56: {
                "USDT": TokenInfo(
                    symbol="USDT",
                    name="Tether USD (BSC)",
                    address="0x55d398326f99059fF775485246999027B3197955",
                    decimals=18,
                    is_stablecoin=True,
                    coingecko_id="tether"
                ),
                "USDC": TokenInfo(
                    symbol="USDC",
                    name="USD Coin (BSC)",
                    address="0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
                    decimals=18,
                    is_stablecoin=True,
                    coingecko_id="usd-coin"
                ),
                "WBNB": TokenInfo(
                    symbol="WBNB",
                    name="Wrapped BNB",
                    address="0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
                    decimals=18,
                    coingecko_id="wbnb"
                )
            }
        }
    
    def get_token_info(self, chain_id: int, symbol: str) -> Optional[TokenInfo]:
        """
        Get token information for a specific chain and symbol.
        
        Args:
            chain_id: Blockchain network ID
            symbol: Token symbol (e.g., "USDT", "USDC")
            
        Returns:
            TokenInfo if found, None otherwise
        """
        chain_tokens = self.tokens_by_network.get(chain_id, {})
        return chain_tokens.get(symbol.upper())
    
    def get_supported_tokens(self, chain_id: int) -> List[str]:
        """
        Get list of supported token symbols for a specific chain.
        
        Args:
            chain_id: Blockchain network ID
            
        Returns:
            List of supported token symbols
        """
        return list(self.tokens_by_network.get(chain_id, {}).keys())
    
    def is_token_supported(self, chain_id: int, symbol: str) -> bool:
        """
        Check if a token is supported on a specific chain.
        
        Args:
            chain_id: Blockchain network ID
            symbol: Token symbol to check
            
        Returns:
            True if supported, False otherwise
        """
        return self.get_token_info(chain_id, symbol) is not None
    
    def get_stablecoins(self, chain_id: int) -> List[str]:
        """
        Get list of stablecoin symbols for a specific chain.
        
        Args:
            chain_id: Blockchain network ID
            
        Returns:
            List of stablecoin symbols
        """
        chain_tokens = self.tokens_by_network.get(chain_id, {})
        return [symbol for symbol, info in chain_tokens.items() if info.is_stablecoin]
    
    def get_all_supported_chains(self) -> List[int]:
        """
        Get list of all supported chain IDs.
        
        Returns:
            List of supported chain IDs
        """
        return list(self.tokens_by_network.keys())
    
    def get_token_summary(self) -> Dict[str, Any]:
        """
        Get summary of all supported tokens across all chains.
        
        Returns:
            Dictionary with token registry summary
        """
        total_tokens = sum(len(tokens) for tokens in self.tokens_by_network.values())
        chains_info = {}
        
        for chain_id, tokens in self.tokens_by_network.items():
            stablecoins = [symbol for symbol, info in tokens.items() if info.is_stablecoin]
            chains_info[chain_id] = {
                "total_tokens": len(tokens),
                "stablecoins": stablecoins,
                "all_tokens": list(tokens.keys())
            }
        
        return {
            "total_tokens": total_tokens,
            "total_chains": len(self.tokens_by_network),
            "chains": chains_info
        }

# Standard ERC20 ABI for token transfers
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "name",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function"
    }
]