#!/usr/bin/env python
"""
Token Manager for PGP_INVITE_v1 (Telegram Invite Sender Service).
Handles token decryption from PGP_ORCHESTRATOR_v1.
"""
import base64
import hmac
import hashlib
import struct
import time
from typing import Tuple, Dict, Any, Optional
from PGP_COMMON.tokens import BaseTokenManager


class TokenManager(BaseTokenManager):
    """
    Manages token decryption for PGP_INVITE_v1.
    Inherits common methods from BaseTokenManager.
    """

    def __init__(self, signing_key: str):
        """
        Initialize the TokenManager.

        Args:
            signing_key: SUCCESS_URL_SIGNING_KEY for token verification
        """
        super().__init__(signing_key, service_name="PGP_INVITE_v1")

    def decode_and_verify_token(self, token: str) -> Tuple[int, int, str, str, str, int, str]:
        """
        Decode and verify token from PGP_ORCHESTRATOR_v1.

        Token format (same as NOWPayments token):
        - 6 bytes user_id (48-bit)
        - 6 bytes closed_channel_id (48-bit)
        - 2 bytes timestamp_minutes
        - 2 bytes subscription_time_days
        - 1 byte price_length + subscription_price
        - 1 byte wallet_length + wallet_address
        - 1 byte currency_length + payout_currency
        - 1 byte network_length + payout_network
        - 16 bytes truncated HMAC signature

        Args:
            token: Base64-encoded token from PGP_ORCHESTRATOR_v1

        Returns:
            Tuple of (user_id, closed_channel_id, wallet_address, payout_currency,
                     payout_network, subscription_time_days, subscription_price)

        Raises:
            ValueError: If token is invalid or expired
        """
        # Pad the token if base64 length is not a multiple of 4
        padding = '=' * (-len(token) % 4)
        try:
            raw = base64.urlsafe_b64decode(token + padding)
        except Exception:
            raise ValueError("Invalid token: cannot decode base64")

        # Minimum size check: 6+6+2+2+1+1+1+1+1+1+16 = 38 bytes
        if len(raw) < 38:
            raise ValueError(f"Invalid token: too small (got {len(raw)}, minimum 38)")

        # Parse fixed part
        user_id = int.from_bytes(raw[0:6], 'big')
        closed_channel_id = int.from_bytes(raw[6:12], 'big')
        timestamp_minutes = struct.unpack(">H", raw[12:14])[0]
        subscription_time_days = struct.unpack(">H", raw[14:16])[0]

        # Parse variable part
        offset = 16

        # Read subscription price
        if offset + 1 > len(raw):
            raise ValueError("Invalid token: missing price length field")
        price_len = struct.unpack(">B", raw[offset:offset+1])[0]
        offset += 1

        if offset + price_len > len(raw):
            raise ValueError("Invalid token: incomplete subscription price")
        subscription_price = raw[offset:offset+price_len].decode('utf-8')
        offset += price_len

        # Read wallet address
        if offset + 1 > len(raw):
            raise ValueError("Invalid token: missing wallet length field")
        wallet_len = struct.unpack(">B", raw[offset:offset+1])[0]
        offset += 1

        if offset + wallet_len > len(raw):
            raise ValueError("Invalid token: incomplete wallet address")
        wallet_address = raw[offset:offset+wallet_len].decode('utf-8')
        offset += wallet_len

        # Read currency
        if offset + 1 > len(raw):
            raise ValueError("Invalid token: missing currency length field")
        currency_len = struct.unpack(">B", raw[offset:offset+1])[0]
        offset += 1

        if offset + currency_len > len(raw):
            raise ValueError("Invalid token: incomplete currency")
        payout_currency = raw[offset:offset+currency_len].decode('utf-8')
        offset += currency_len

        # Read network
        if offset + 1 > len(raw):
            raise ValueError("Invalid token: missing network length field")
        network_len = struct.unpack(">B", raw[offset:offset+1])[0]
        offset += 1

        if offset + network_len > len(raw):
            raise ValueError("Invalid token: incomplete network")
        payout_network = raw[offset:offset+network_len].decode('utf-8')
        offset += network_len

        # Verify signature
        if len(raw) - offset != 16:
            raise ValueError(f"Invalid token: wrong signature size (got {len(raw) - offset}, expected 16)")

        data = raw[:offset]
        sig = raw[offset:]

        # Debug logs
        print(f"🔍 [TOKEN] Token decoded successfully")
        print(f"👤 [TOKEN] User: {user_id}, Channel: {closed_channel_id}")
        print(f"💰 [TOKEN] Price: ${subscription_price}, Duration: {subscription_time_days} days")

        # Verify truncated signature
        expected_full_sig = hmac.new(self.signing_key.encode(), data, hashlib.sha256).digest()
        expected_sig = expected_full_sig[:16]
        if not hmac.compare_digest(sig, expected_sig):
            raise ValueError("Signature mismatch")

        # Fix negative IDs (48-bit range)
        if user_id > 2**47 - 1:
            user_id -= 2**48
        if closed_channel_id > 2**47 - 1:
            closed_channel_id -= 2**48

        # Reconstruct timestamp (same logic as PGP_ORCHESTRATOR_v1)
        current_time = int(time.time())
        current_minutes = current_time // 60
        minutes_in_current_cycle = current_minutes % 65536
        base_minutes = current_minutes - minutes_in_current_cycle

        if timestamp_minutes > minutes_in_current_cycle:
            timestamp = (base_minutes - 65536 + timestamp_minutes) * 60
        else:
            timestamp = (base_minutes + timestamp_minutes) * 60

        # Validate timestamp is reasonable (within ~45 days)
        time_diff = abs(current_time - timestamp)
        if time_diff > 45 * 24 * 3600:
            raise ValueError(f"Timestamp too far from current time: {time_diff} seconds difference")

        print(f"🔓 [TOKEN] Signature verified successfully")
        print(f"⏰ [TOKEN] Timestamp: {timestamp}")

        # Check for expiration (24hr window to accommodate retry delays)
        now = int(time.time())
        if not (now - 86400 <= timestamp <= now + 300):
            raise ValueError("Token expired or not yet valid")

        return user_id, closed_channel_id, wallet_address, payout_currency, payout_network, subscription_time_days, subscription_price
