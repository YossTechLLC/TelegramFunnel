#!/usr/bin/env python
"""
Input validation functions for GCPaymentGateway-10-26
"""

from typing import Any


def validate_user_id(user_id: Any) -> bool:
    """
    Validate Telegram user ID.

    Args:
        user_id: User ID to validate

    Returns:
        True if valid, False otherwise
    """
    try:
        user_id_int = int(user_id)
        return user_id_int > 0
    except (ValueError, TypeError):
        return False


def validate_amount(amount: Any) -> bool:
    """
    Validate payment amount.

    Args:
        amount: Amount to validate

    Returns:
        True if valid (between $1.00 and $9999.99), False otherwise
    """
    try:
        amount_float = float(amount)
        if not (1.00 <= amount_float <= 9999.99):
            return False

        # Check decimal places (max 2)
        amount_str = str(amount)
        if '.' in amount_str:
            decimal_places = len(amount_str.split('.')[1])
            if decimal_places > 2:
                return False

        return True
    except (ValueError, TypeError):
        return False


def validate_channel_id(channel_id: Any) -> bool:
    """
    Validate Telegram channel ID format.

    Args:
        channel_id: Channel ID to validate

    Returns:
        True if valid format, False otherwise
    """
    if not channel_id:
        return False

    channel_id_str = str(channel_id)

    # Special case: donation_default
    if channel_id_str == "donation_default":
        return True

    # Standard validation: numeric (with optional negative sign)
    if channel_id_str.lstrip("-").isdigit():
        return len(channel_id_str) <= 15  # Max length for Telegram IDs

    return False


def validate_subscription_time(days: Any) -> bool:
    """
    Validate subscription duration in days.

    Args:
        days: Duration in days to validate

    Returns:
        True if valid (1-999 days), False otherwise
    """
    try:
        days_int = int(days)
        return 1 <= days_int <= 999
    except (ValueError, TypeError):
        return False


def validate_payment_type(payment_type: Any) -> bool:
    """
    Validate payment type.

    Args:
        payment_type: Payment type to validate

    Returns:
        True if valid ('subscription' or 'donation'), False otherwise
    """
    if not isinstance(payment_type, str):
        return False

    return payment_type.lower() in ["subscription", "donation"]


def sanitize_channel_id(channel_id: str) -> str:
    """
    Sanitize channel ID to ensure correct format.
    Telegram channel IDs must be negative for supergroups/channels.

    Args:
        channel_id: Channel ID to sanitize

    Returns:
        Sanitized channel ID
    """
    channel_id_str = str(channel_id)

    # Special case: donation_default
    if channel_id_str == "donation_default":
        return channel_id_str

    # Ensure negative sign for Telegram channels
    if not channel_id_str.startswith('-'):
        print(f"⚠️ [VALIDATION] Channel ID should be negative: {channel_id_str}")
        print(f"⚠️ [VALIDATION] Telegram channel IDs are always negative for supergroups/channels")
        channel_id_str = f"-{channel_id_str}"
        print(f"✅ [VALIDATION] Corrected to: {channel_id_str}")

    return channel_id_str
