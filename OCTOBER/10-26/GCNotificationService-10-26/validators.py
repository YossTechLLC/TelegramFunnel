#!/usr/bin/env python
"""
✅ Validators for GCNotificationService
Input validation utilities
"""
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


def validate_notification_request(data: Dict[str, Any]) -> tuple[bool, List[str]]:
    """
    Validate notification request payload

    Args:
        data: Request data dictionary

    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []

    # Check required top-level fields
    required_fields = ['open_channel_id', 'payment_type', 'payment_data']
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    if errors:
        return False, errors

    # Validate open_channel_id format
    if not isinstance(data['open_channel_id'], str):
        errors.append("open_channel_id must be a string")
    elif not data['open_channel_id'].startswith('-'):
        errors.append("open_channel_id must start with '-'")

    # Validate payment_type
    if data['payment_type'] not in ['subscription', 'donation']:
        errors.append("payment_type must be 'subscription' or 'donation'")

    # Validate payment_data
    if not isinstance(data['payment_data'], dict):
        errors.append("payment_data must be a dictionary")
    else:
        payment_data = data['payment_data']

        # Check common required fields
        common_fields = ['user_id', 'amount_crypto', 'amount_usd', 'crypto_currency']
        for field in common_fields:
            if field not in payment_data:
                errors.append(f"payment_data missing field: {field}")

        # Check subscription-specific fields
        if data['payment_type'] == 'subscription':
            subscription_fields = ['tier', 'tier_price', 'duration_days']
            for field in subscription_fields:
                if field not in payment_data:
                    errors.append(f"payment_data missing subscription field: {field}")

    return (len(errors) == 0, errors)


def validate_channel_id(channel_id: str) -> bool:
    """
    Validate that a channel ID is properly formatted

    Args:
        channel_id: Channel ID string

    Returns:
        True if valid, False otherwise
    """
    if not isinstance(channel_id, str):
        return False

    if not channel_id.startswith('-'):
        return False

    if not channel_id.lstrip("-").isdigit():
        return False

    if len(channel_id) > 14:
        return False

    return True
