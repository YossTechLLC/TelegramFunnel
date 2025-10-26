#!/usr/bin/env python
"""
Custom validators for GCRegister10-5 Channel Registration Service.
Provides validation functions for form fields.
"""
from wtforms.validators import ValidationError
import re

def validate_channel_id(form, field):
    """
    Validate that a channel ID is properly formatted.

    Rules:
    - Must be numeric (can start with -)
    - Maximum 14 characters

    Args:
        form: The form instance
        field: The field to validate

    Raises:
        ValidationError: If validation fails
    """
    channel_id = field.data.strip()

    # Check if it's numeric (allowing negative sign)
    if not re.match(r'^-?\d+$', channel_id):
        raise ValidationError('❌ Channel ID must be a number (e.g., -1001234567890)')

    # Check length (≤14 characters)
    if len(channel_id) > 14:
        raise ValidationError('❌ Channel ID must be 14 characters or less')

    print(f"✅ [VALIDATOR] Channel ID validated: {channel_id}")


def validate_price(form, field):
    """
    Validate that a subscription price is properly formatted.

    Rules:
    - Must be between 0 and 9999.99
    - Maximum 2 decimal places

    Args:
        form: The form instance
        field: The field to validate

    Raises:
        ValidationError: If validation fails
    """
    price = field.data

    # Skip validation if field is empty (optional tiers)
    if price is None:
        return

    # Check range
    if not (0 <= price <= 9999.99):
        raise ValidationError('❌ Price must be between $0.00 and $9999.99')

    # Check decimal places (convert to string to check)
    price_str = str(price)
    if '.' in price_str:
        decimal_places = len(price_str.split('.')[1])
        if decimal_places > 2:
            raise ValidationError('❌ Price can have maximum 2 decimal places')

    print(f"✅ [VALIDATOR] Price validated: ${price:.2f}")


def validate_time(form, field):
    """
    Validate that a subscription time is properly formatted.

    Rules:
    - Must be between 1 and 999 days

    Args:
        form: The form instance
        field: The field to validate

    Raises:
        ValidationError: If validation fails
    """
    time_days = field.data

    # Skip validation if field is empty (optional tiers)
    if time_days is None:
        return

    # Check range
    if not (1 <= time_days <= 999):
        raise ValidationError('❌ Subscription time must be between 1 and 999 days')

    print(f"✅ [VALIDATOR] Subscription time validated: {time_days} days")


def validate_wallet_address(form, field):
    """
    Validate that a wallet address is properly formatted.

    Rules:
    - Maximum 110 characters
    - Alphanumeric plus common crypto address characters

    Args:
        form: The form instance
        field: The field to validate

    Raises:
        ValidationError: If validation fails
    """
    wallet_address = field.data.strip()

    # Check length
    if len(wallet_address) > 110:
        raise ValidationError('❌ Wallet address must be 110 characters or less')

    # Check for valid characters (alphanumeric plus common crypto chars)
    if not re.match(r'^[a-zA-Z0-9\-_]+$', wallet_address):
        raise ValidationError('❌ Wallet address contains invalid characters (use only letters, numbers, - and _)')

    print(f"✅ [VALIDATOR] Wallet address validated: {wallet_address[:20]}...")


def validate_title(form, field):
    """
    Validate that a title is properly formatted.

    Rules:
    - Minimum 1 character
    - Maximum 100 characters

    Args:
        form: The form instance
        field: The field to validate

    Raises:
        ValidationError: If validation fails
    """
    title = field.data.strip()

    # Check length
    if len(title) < 1:
        raise ValidationError('❌ Title cannot be empty')

    if len(title) > 100:
        raise ValidationError('❌ Title must be 100 characters or less')

    print(f"✅ [VALIDATOR] Title validated: {title[:30]}...")


def validate_description(form, field):
    """
    Validate that a description is properly formatted.

    Rules:
    - Minimum 1 character
    - Maximum 500 characters

    Args:
        form: The form instance
        field: The field to validate

    Raises:
        ValidationError: If validation fails
    """
    description = field.data.strip()

    # Check length
    if len(description) < 1:
        raise ValidationError('❌ Description cannot be empty')

    if len(description) > 500:
        raise ValidationError('❌ Description must be 500 characters or less')

    print(f"✅ [VALIDATOR] Description validated: {description[:30]}...")
