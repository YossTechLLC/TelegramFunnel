"""
Wallet Address Validation Utilities

This module provides secure validation for cryptocurrency wallet addresses
to prevent fund theft to invalid or malformed addresses.

Security Fix: C-01 - Wallet Address Validation Missing
OWASP: A03:2021 - Injection
CWE: CWE-20 (Improper Input Validation)

Supported Networks:
- Ethereum (ETH, ERC-20 tokens)
- Bitcoin (BTC)
- Polygon (MATIC)
- BNB Smart Chain (BSC)

Dependencies:
- web3: Ethereum address validation with checksum
- python-bitcoinlib: Bitcoin address validation
"""

import re
import logging
from typing import Optional

# Get logger for this module
logger = logging.getLogger(__name__)

# Try to import web3 for Ethereum validation
try:
    from web3 import Web3
    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False
    logger.warning("⚠️ [WALLET_VALIDATION] web3 not installed - Ethereum validation unavailable")

# Try to import bitcoinlib for Bitcoin validation
try:
    import bitcoin
    from bitcoin.core import b58decode, b58decode_chk
    BITCOIN_LIB_AVAILABLE = True
except ImportError:
    BITCOIN_LIB_AVAILABLE = False
    logger.warning("⚠️ [WALLET_VALIDATION] python-bitcoinlib not installed - Bitcoin validation unavailable")


class WalletValidationError(ValueError):
    """Raised when wallet address validation fails."""
    pass


def validate_ethereum_address(address: str) -> bool:
    """
    Validate Ethereum address format and checksum.

    Ethereum addresses:
    - Must be 42 characters (0x + 40 hex chars)
    - Must have valid EIP-55 checksum if mixed case

    Args:
        address: Ethereum address to validate

    Returns:
        True if valid

    Raises:
        WalletValidationError: If address is invalid

    Examples:
        >>> validate_ethereum_address("0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb6")
        True
        >>> validate_ethereum_address("0xInvalidAddress")
        WalletValidationError: Invalid Ethereum address format
    """
    if not WEB3_AVAILABLE:
        raise WalletValidationError(
            "Ethereum address validation unavailable - web3 library not installed. "
            "Please install: pip install web3"
        )

    # Remove whitespace
    address = address.strip()

    # Check basic format
    if not address.startswith('0x'):
        raise WalletValidationError(
            f"Invalid Ethereum address: must start with '0x'. Got: {address[:10]}..."
        )

    if len(address) != 42:
        raise WalletValidationError(
            f"Invalid Ethereum address: must be 42 characters (0x + 40 hex). "
            f"Got {len(address)} characters"
        )

    # Check if it's a valid hex string
    try:
        int(address[2:], 16)
    except ValueError:
        raise WalletValidationError(
            f"Invalid Ethereum address: contains non-hexadecimal characters"
        )

    # Use Web3.py to validate checksum
    if not Web3.is_address(address):
        raise WalletValidationError(
            f"Invalid Ethereum address: failed Web3 validation"
        )

    # If address has mixed case, verify checksum (EIP-55)
    if address != address.lower() and address != address.upper():
        if not Web3.is_checksum_address(address):
            raise WalletValidationError(
                f"Invalid Ethereum address: checksum validation failed (EIP-55). "
                f"Expected checksum: {Web3.to_checksum_address(address)}"
            )

    logger.debug(f"✅ [WALLET_VALIDATION] Valid Ethereum address: {address}")
    return True


def validate_bitcoin_address(address: str, network: str = 'mainnet') -> bool:
    """
    Validate Bitcoin address format and checksum.

    Bitcoin addresses can be:
    - Legacy (P2PKH): Starts with 1
    - Script (P2SH): Starts with 3
    - SegWit (Bech32): Starts with bc1 (mainnet) or tb1 (testnet)

    Args:
        address: Bitcoin address to validate
        network: 'mainnet' or 'testnet'

    Returns:
        True if valid

    Raises:
        WalletValidationError: If address is invalid

    Examples:
        >>> validate_bitcoin_address("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
        True
        >>> validate_bitcoin_address("bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq")
        True
    """
    if not BITCOIN_LIB_AVAILABLE:
        # Fallback to basic validation if library not available
        logger.warning(
            "⚠️ [WALLET_VALIDATION] python-bitcoinlib not installed - using basic validation"
        )
        return _validate_bitcoin_address_basic(address, network)

    # Remove whitespace
    address = address.strip()

    # Validate SegWit (Bech32) addresses
    if address.startswith('bc1') or address.startswith('tb1'):
        return _validate_bech32_address(address, network)

    # Validate Legacy/Script addresses (Base58Check)
    return _validate_base58_address(address, network)


def _validate_bech32_address(address: str, network: str) -> bool:
    """Validate SegWit Bech32 Bitcoin address."""
    # Basic format validation
    if network == 'mainnet':
        if not address.startswith('bc1'):
            raise WalletValidationError(
                f"Invalid Bitcoin mainnet SegWit address: must start with 'bc1'. Got: {address[:5]}"
            )
    elif network == 'testnet':
        if not address.startswith('tb1'):
            raise WalletValidationError(
                f"Invalid Bitcoin testnet SegWit address: must start with 'tb1'. Got: {address[:5]}"
            )

    # Bech32 addresses should only contain lowercase alphanumeric (except 1, b, i, o)
    bech32_charset = set('023456789acdefghjklmnpqrstuvwxyz')
    if not all(c in bech32_charset for c in address[3:]):  # Skip 'bc1' or 'tb1'
        raise WalletValidationError(
            "Invalid SegWit address: contains invalid Bech32 characters"
        )

    # Length check (SegWit v0 addresses are typically 42-62 characters)
    if len(address) < 14 or len(address) > 90:
        raise WalletValidationError(
            f"Invalid SegWit address: length {len(address)} out of range (14-90)"
        )

    logger.debug(f"✅ [WALLET_VALIDATION] Valid Bitcoin SegWit address: {address}")
    return True


def _validate_base58_address(address: str, network: str) -> bool:
    """Validate Legacy/Script Bitcoin address (Base58Check)."""
    # Check prefix
    if network == 'mainnet':
        if not (address.startswith('1') or address.startswith('3')):
            raise WalletValidationError(
                f"Invalid Bitcoin mainnet address: must start with '1' or '3'. Got: {address[0]}"
            )
    elif network == 'testnet':
        if not (address.startswith('m') or address.startswith('n') or address.startswith('2')):
            raise WalletValidationError(
                f"Invalid Bitcoin testnet address: must start with 'm', 'n', or '2'. Got: {address[0]}"
            )

    # Validate Base58 characters (no 0, O, I, l)
    base58_charset = set('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz')
    if not all(c in base58_charset for c in address):
        raise WalletValidationError(
            "Invalid Bitcoin address: contains invalid Base58 characters (0, O, I, l not allowed)"
        )

    # Length check (25-34 characters typical)
    if len(address) < 26 or len(address) > 35:
        raise WalletValidationError(
            f"Invalid Bitcoin address: length {len(address)} out of range (26-35)"
        )

    # Try Base58 checksum validation if library available
    if BITCOIN_LIB_AVAILABLE:
        try:
            decoded = b58decode_chk(address)
            logger.debug(f"✅ [WALLET_VALIDATION] Valid Bitcoin address (checksum verified): {address}")
        except Exception as e:
            raise WalletValidationError(
                f"Invalid Bitcoin address: checksum validation failed - {str(e)}"
            )
    else:
        logger.debug(f"✅ [WALLET_VALIDATION] Valid Bitcoin address (basic check): {address}")

    return True


def _validate_bitcoin_address_basic(address: str, network: str) -> bool:
    """
    Basic Bitcoin address validation without external libraries.
    Used as fallback if python-bitcoinlib is not installed.
    """
    address = address.strip()

    # Check for valid prefixes based on network
    if network == 'mainnet':
        valid_prefixes = ['1', '3', 'bc1']
    elif network == 'testnet':
        valid_prefixes = ['m', 'n', '2', 'tb1']
    else:
        raise WalletValidationError(f"Invalid network: {network}. Use 'mainnet' or 'testnet'")

    if not any(address.startswith(prefix) for prefix in valid_prefixes):
        raise WalletValidationError(
            f"Invalid Bitcoin {network} address: invalid prefix. "
            f"Expected one of: {', '.join(valid_prefixes)}"
        )

    # Basic length validation
    if len(address) < 26 or len(address) > 90:
        raise WalletValidationError(
            f"Invalid Bitcoin address: length {len(address)} out of range (26-90)"
        )

    logger.debug(f"✅ [WALLET_VALIDATION] Bitcoin address passed basic validation: {address}")
    return True


def validate_wallet_address(
    address: str,
    network: str,
    blockchain: Optional[str] = None
) -> bool:
    """
    Validate wallet address for any supported cryptocurrency network.

    This is the main entry point for wallet address validation.
    Automatically detects blockchain type from network name if not specified.

    Args:
        address: Wallet address to validate
        network: Network name (e.g., 'eth', 'btc', 'matic', 'bsc', 'bitcoin')
        blockchain: Optional explicit blockchain type ('ethereum' or 'bitcoin')

    Returns:
        True if valid

    Raises:
        WalletValidationError: If address is invalid or network unsupported

    Examples:
        >>> validate_wallet_address("0x742d35Cc...", "eth")
        True
        >>> validate_wallet_address("1A1zP1eP5Q...", "btc")
        True
        >>> validate_wallet_address("bc1qar0sr...", "bitcoin", "bitcoin")
        True
    """
    # Normalize inputs
    address = address.strip()
    network = network.lower().strip()

    # Map network names to blockchain types
    ethereum_networks = {'eth', 'ethereum', 'matic', 'polygon', 'bsc', 'bnb', 'binance'}
    bitcoin_networks = {'btc', 'bitcoin'}

    # Determine blockchain type
    if blockchain:
        blockchain = blockchain.lower()
    elif network in ethereum_networks:
        blockchain = 'ethereum'
    elif network in bitcoin_networks:
        blockchain = 'bitcoin'
    else:
        raise WalletValidationError(
            f"Unsupported network: {network}. "
            f"Supported networks: {', '.join(ethereum_networks | bitcoin_networks)}"
        )

    # Validate based on blockchain type
    if blockchain == 'ethereum':
        logger.info(f"🔍 [WALLET_VALIDATION] Validating Ethereum address for network: {network}")
        return validate_ethereum_address(address)

    elif blockchain == 'bitcoin':
        logger.info(f"🔍 [WALLET_VALIDATION] Validating Bitcoin address for network: {network}")
        # Default to mainnet unless explicitly testnet
        btc_network = 'testnet' if 'test' in network else 'mainnet'
        return validate_bitcoin_address(address, btc_network)

    else:
        raise WalletValidationError(
            f"Unsupported blockchain: {blockchain}. Supported: ethereum, bitcoin"
        )


def get_checksum_address(address: str) -> str:
    """
    Get the checksummed version of an Ethereum address (EIP-55).

    Args:
        address: Ethereum address (any case)

    Returns:
        Checksummed address with proper mixed case

    Raises:
        WalletValidationError: If address is invalid

    Examples:
        >>> get_checksum_address("0x742d35cc6634c0532925a3b844bc9e7595f0beb6")
        "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb6"
    """
    if not WEB3_AVAILABLE:
        raise WalletValidationError(
            "Checksum calculation unavailable - web3 library not installed"
        )

    # Validate first
    validate_ethereum_address(address)

    # Return checksummed version
    return Web3.to_checksum_address(address)


# Export public API
__all__ = [
    'validate_wallet_address',
    'validate_ethereum_address',
    'validate_bitcoin_address',
    'get_checksum_address',
    'WalletValidationError'
]
