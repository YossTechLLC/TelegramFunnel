"""
Input validation utilities for PGP services.

Provides comprehensive validation for:
- Telegram user IDs and channel IDs
- Payment identifiers
- Cryptocurrency amounts
- Order ID formats

Prevents logic bugs by validating inputs BEFORE database queries.
"""

from typing import Any
import re
from PGP_COMMON.logging import setup_logger

logger = setup_logger(__name__)


class ValidationError(ValueError):
    """Raised when input validation fails."""
    pass


def validate_telegram_user_id(user_id: Any, field_name: str = "user_id") -> int:
    """
    Validate and convert Telegram user ID.

    Telegram user IDs are:
    - Always positive integers
    - Typically 8-10 digits (range: 10,000,000 to 9,999,999,999)
    - Never 0, negative, or None

    Args:
        user_id: Value to validate (can be string, int, etc.)
        field_name: Name of field for error messages

    Returns:
        Validated integer user_id

    Raises:
        ValidationError: If validation fails

    Examples:
        >>> validate_telegram_user_id(123456789)
        123456789
        >>> validate_telegram_user_id("987654321")
        987654321
        >>> validate_telegram_user_id(None)
        ValidationError: user_id cannot be None
        >>> validate_telegram_user_id(-123)
        ValidationError: user_id must be positive
    """
    # Check for None/empty
    if user_id is None or user_id == '':
        raise ValidationError(f"{field_name} cannot be None or empty")

    # Convert to int
    try:
        uid = int(user_id)
    except (ValueError, TypeError) as e:
        raise ValidationError(
            f"{field_name} must be an integer, got {type(user_id).__name__}: {user_id}"
        )

    # Check positive
    if uid <= 0:
        raise ValidationError(f"{field_name} must be positive, got {uid}")

    # Check realistic range (Telegram user IDs are 8+ digits)
    if uid < 10_000_000:
        raise ValidationError(
            f"{field_name} appears invalid: {uid} (Telegram user IDs are typically 8+ digits)"
        )

    # Sanity check upper bound (current max ~10 digits)
    if uid > 9_999_999_999:
        raise ValidationError(
            f"{field_name} too large: {uid} (max 10 digits for Telegram user IDs)"
        )

    return uid


def validate_telegram_channel_id(channel_id: Any, field_name: str = "channel_id") -> int:
    """
    Validate and convert Telegram channel ID.

    Telegram channel/group IDs:
    - Can be positive or negative (supergroups are negative)
    - Typically 10-13 digits
    - Format: -100xxxxxxxxxx for supergroups
    - Never 0 or None

    Args:
        channel_id: Value to validate
        field_name: Name of field for error messages

    Returns:
        Validated integer channel_id

    Raises:
        ValidationError: If validation fails

    Examples:
        >>> validate_telegram_channel_id(-1001234567890)
        -1001234567890
        >>> validate_telegram_channel_id(1234567890)
        1234567890
        >>> validate_telegram_channel_id(123)
        ValidationError: channel_id too short
    """
    if channel_id is None or channel_id == '':
        raise ValidationError(f"{field_name} cannot be None or empty")

    try:
        cid = int(channel_id)
    except (ValueError, TypeError):
        raise ValidationError(
            f"{field_name} must be an integer, got {type(channel_id).__name__}: {channel_id}"
        )

    if cid == 0:
        raise ValidationError(f"{field_name} cannot be 0")

    # Check length (absolute value)
    abs_cid = abs(cid)
    if abs_cid < 1_000_000_000:  # 10 digits minimum
        raise ValidationError(
            f"{field_name} too short: {cid} (Telegram channels are typically 10+ digits)"
        )

    if abs_cid > 9_999_999_999_999:  # 13 digits maximum
        raise ValidationError(
            f"{field_name} too large: {cid} (max 13 digits for Telegram channels)"
        )

    return cid


def validate_payment_id(payment_id: Any, field_name: str = "payment_id") -> str:
    """
    Validate payment identifier from payment processor.

    Payment IDs should be:
    - Non-empty strings
    - Between 1-100 characters (database limit)
    - Alphanumeric with allowed special chars: -_

    Args:
        payment_id: Value to validate
        field_name: Name of field for error messages

    Returns:
        Validated string payment_id

    Raises:
        ValidationError: If validation fails
    """
    if not payment_id:
        raise ValidationError(f"{field_name} cannot be empty")

    # Convert to string if needed
    pid = str(payment_id).strip()

    if not pid:
        raise ValidationError(f"{field_name} cannot be whitespace only")

    # Check length
    if len(pid) > 100:
        raise ValidationError(
            f"{field_name} too long: {len(pid)} characters (max 100)"
        )

    # Check format (alphanumeric + hyphens/underscores)
    if not re.match(r'^[a-zA-Z0-9_-]+$', pid):
        raise ValidationError(
            f"{field_name} contains invalid characters: {pid} "
            "(only alphanumeric, hyphens, and underscores allowed)"
        )

    return pid


def validate_order_id_format(order_id: Any) -> str:
    """
    Validate NowPayments order_id format.

    Expected format: {user_id}_{open_channel_id}
    Example: "123456789_-1001234567890"

    Args:
        order_id: Order ID to validate

    Returns:
        Validated order_id string

    Raises:
        ValidationError: If format invalid
    """
    if not order_id:
        raise ValidationError("order_id cannot be empty")

    oid = str(order_id).strip()

    # Check format
    if '_' not in oid:
        raise ValidationError(
            f"order_id invalid format: {oid} (expected user_id_channel_id)"
        )

    parts = oid.split('_')
    if len(parts) != 2:
        raise ValidationError(
            f"order_id invalid format: {oid} (expected exactly one underscore)"
        )

    # Validate parts are numeric
    try:
        user_part = int(parts[0])
        channel_part = int(parts[1])
    except ValueError:
        raise ValidationError(
            f"order_id contains non-numeric IDs: {oid}"
        )

    # Validate ID formats
    validate_telegram_user_id(user_part, "order_id user_id part")
    validate_telegram_channel_id(channel_part, "order_id channel_id part")

    return oid


def validate_crypto_amount(amount: Any, field_name: str = "amount") -> float:
    """
    Validate cryptocurrency amount.

    Args:
        amount: Amount to validate
        field_name: Name of field for error messages

    Returns:
        Validated float amount

    Raises:
        ValidationError: If validation fails
    """
    if amount is None:
        raise ValidationError(f"{field_name} cannot be None")

    try:
        amt = float(amount)
    except (ValueError, TypeError):
        raise ValidationError(
            f"{field_name} must be numeric, got {type(amount).__name__}: {amount}"
        )

    if amt < 0:
        raise ValidationError(f"{field_name} cannot be negative: {amt}")

    if amt == 0:
        raise ValidationError(f"{field_name} cannot be zero")

    # Sanity check (no transaction should be > $1M)
    if amt > 1_000_000:
        raise ValidationError(
            f"{field_name} unrealistically large: {amt} (max 1,000,000)"
        )

    return amt


def validate_payment_status(status: Any) -> str:
    """
    Validate NowPayments payment status.

    Args:
        status: Payment status to validate

    Returns:
        Validated lowercase status string

    Raises:
        ValidationError: If status invalid
    """
    if not status:
        raise ValidationError("payment_status cannot be empty")

    status_str = str(status).lower().strip()

    ALLOWED_STATUSES = {
        'waiting', 'confirming', 'confirmed', 'sending',
        'partially_paid', 'finished', 'failed', 'refunded', 'expired'
    }

    if status_str not in ALLOWED_STATUSES:
        raise ValidationError(
            f"Invalid payment_status: {status_str} "
            f"(allowed: {', '.join(sorted(ALLOWED_STATUSES))})"
        )

    return status_str


def validate_crypto_address(address: Any, field_name: str = "address", max_length: int = 150) -> str:
    """
    Validate cryptocurrency wallet address.

    Args:
        address: Address to validate
        field_name: Name of field for error messages
        max_length: Maximum allowed length

    Returns:
        Validated address string

    Raises:
        ValidationError: If validation fails
    """
    if not address:
        raise ValidationError(f"{field_name} cannot be empty")

    addr = str(address).strip()

    if not addr:
        raise ValidationError(f"{field_name} cannot be whitespace only")

    if len(addr) > max_length:
        raise ValidationError(
            f"{field_name} too long: {len(addr)} characters (max {max_length})"
        )

    # Basic format check (alphanumeric only for most crypto addresses)
    if not re.match(r'^[a-zA-Z0-9]+$', addr):
        raise ValidationError(
            f"{field_name} contains invalid characters (only alphanumeric allowed)"
        )

    return addr


def validate_crypto_symbol(symbol: Any, field_name: str = "currency") -> str:
    """
    Validate cryptocurrency symbol/ticker.

    Prevents injection attacks via unvalidated crypto symbols that are:
    - Logged in error messages
    - Used in database queries
    - Passed to external APIs (CoinGecko, NowPayments)

    Args:
        symbol: Crypto symbol to validate (e.g., "BTC", "ETH", "USDT")
        field_name: Name of field for error messages

    Returns:
        Validated uppercase symbol string

    Raises:
        ValidationError: If validation fails

    Security:
        - Prevents SQL injection via currency fields
        - Prevents log injection via special characters
        - Prevents API abuse via malformed symbols

    Examples:
        >>> validate_crypto_symbol("btc")
        'BTC'
        >>> validate_crypto_symbol("USDT")
        'USDT'
        >>> validate_crypto_symbol("'; DROP TABLE users; --")
        ValidationError: currency contains invalid characters
        >>> validate_crypto_symbol("BTC<script>alert(1)</script>")
        ValidationError: currency contains invalid characters
    """
    if not symbol:
        raise ValidationError(f"{field_name} cannot be empty")

    # Convert to string and normalize
    sym = str(symbol).strip().upper()

    if not sym:
        raise ValidationError(f"{field_name} cannot be whitespace only")

    # Length check (crypto symbols are 2-10 characters)
    if len(sym) < 2:
        raise ValidationError(
            f"{field_name} too short: {len(sym)} characters (min 2)"
        )

    if len(sym) > 10:
        raise ValidationError(
            f"{field_name} too long: {len(sym)} characters (max 10)"
        )

    # Strict format: Only uppercase letters, numbers, and hyphens
    # Examples: BTC, ETH, USDT, BNB, MATIC, SOL-20
    if not re.match(r'^[A-Z0-9-]+$', sym):
        raise ValidationError(
            f"{field_name} contains invalid characters: {symbol} "
            "(only letters, numbers, and hyphens allowed)"
        )

    # Additional security: Reject SQL/XSS patterns
    dangerous_patterns = [
        "'", '"', ';', '--', '/*', '*/', '<', '>', '&', '|',
        '\\', '\n', '\r', '\t', '\0'
    ]
    for pattern in dangerous_patterns:
        if pattern in str(symbol):
            raise ValidationError(
                f"{field_name} contains dangerous characters: {symbol}"
            )

    return sym


# Export all validation functions
__all__ = [
    'ValidationError',
    'validate_telegram_user_id',
    'validate_telegram_channel_id',
    'validate_payment_id',
    'validate_order_id_format',
    'validate_crypto_amount',
    'validate_payment_status',
    'validate_crypto_address',
    'validate_crypto_symbol'
]
