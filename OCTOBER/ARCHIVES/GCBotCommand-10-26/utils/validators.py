#!/usr/bin/env python
"""
Input validators for GCBotCommand
Validates all user input before processing
"""
from typing import Tuple

def valid_channel_id(text: str) -> bool:
    """Validate channel ID format (≤14 char integer)"""
    if text.lstrip("-").isdigit():
        return len(text) <= 14
    return False

def valid_sub_price(text: str) -> bool:
    """Validate subscription price (0-9999.99 with max 2 decimals)"""
    try:
        val = float(text)
    except ValueError:
        return False
    if not (0 <= val <= 9999.99):
        return False
    parts = text.split(".")
    return len(parts) == 1 or len(parts[1]) <= 2

def valid_sub_time(text: str) -> bool:
    """Validate subscription time (1-999 days)"""
    return text.isdigit() and 1 <= int(text) <= 999

def validate_donation_amount(text: str) -> Tuple[bool, float]:
    """
    Validate donation amount (1-9999 USD with max 2 decimals)

    Returns:
        Tuple of (is_valid, amount_value)
    """
    # Remove $ symbol if present
    if text.startswith('$'):
        text = text[1:]

    try:
        val = float(text)
    except ValueError:
        return False, 0.0

    if not (1.0 <= val <= 9999.99):
        return False, 0.0

    parts = text.split(".")
    if len(parts) == 2 and len(parts[1]) > 2:
        return False, 0.0

    return True, val

def valid_channel_title(text: str) -> bool:
    """Validate channel title (1-100 characters)"""
    return 1 <= len(text.strip()) <= 100

def valid_channel_description(text: str) -> bool:
    """Validate channel description (1-500 characters)"""
    return 1 <= len(text.strip()) <= 500

def valid_wallet_address(text: str) -> bool:
    """Validate wallet address (basic format check)"""
    stripped = text.strip()
    return 10 <= len(stripped) <= 200

def valid_currency(text: str) -> bool:
    """Validate currency code (3-10 uppercase letters)"""
    stripped = text.strip().upper()
    return 2 <= len(stripped) <= 10 and stripped.replace("-", "").replace("_", "").isalpha()
