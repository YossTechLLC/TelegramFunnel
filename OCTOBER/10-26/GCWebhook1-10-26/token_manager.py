#!/usr/bin/env python
"""
Token Manager for GCWebhook1-10-26 (Payment Processor Service).
Handles token decryption from NOWPayments and encryption for GCWebhook2 and GCSplit1.
"""
import base64
import hmac
import hashlib
import struct
import time
from typing import Tuple, Dict, Any, Optional


class TokenManager:
    """
    Manages token encryption and decryption for GCWebhook1-10-26.
    """

    def __init__(self, signing_key: str):
        """
        Initialize the TokenManager.

        Args:
            signing_key: SUCCESS_URL_SIGNING_KEY for token verification and encryption
        """
        self.signing_key = signing_key
        print(f"🔐 [TOKEN] TokenManager initialized")

    def decode_and_verify_token(self, token: str) -> Tuple[int, int, str, str, str, int, str]:
        """
        Decode and verify token from NOWPayments success_url.

        Token format (optimized):
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
            token: Base64-encoded token from URL parameter

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

        # Parse fixed part: 6 bytes user_id, 6 bytes channel_id, 2 bytes timestamp_minutes, 2 bytes subscription_time
        user_id = int.from_bytes(raw[0:6], 'big')
        closed_channel_id = int.from_bytes(raw[6:12], 'big')
        timestamp_minutes = struct.unpack(">H", raw[12:14])[0]
        subscription_time_days = struct.unpack(">H", raw[14:16])[0]

        # Parse variable part: subscription price, wallet address, currency, and network
        offset = 16

        # Read subscription price length and data
        if offset + 1 > len(raw):
            raise ValueError("Invalid token: missing price length field")
        price_len = struct.unpack(">B", raw[offset:offset+1])[0]
        offset += 1

        if offset + price_len > len(raw):
            raise ValueError("Invalid token: incomplete subscription price")
        subscription_price = raw[offset:offset+price_len].decode('utf-8')
        offset += price_len

        # Read wallet address length and data
        if offset + 1 > len(raw):
            raise ValueError("Invalid token: missing wallet length field")
        wallet_len = struct.unpack(">B", raw[offset:offset+1])[0]
        offset += 1

        if offset + wallet_len > len(raw):
            raise ValueError("Invalid token: incomplete wallet address")
        wallet_address = raw[offset:offset+wallet_len].decode('utf-8')
        offset += wallet_len

        # Read currency length and data
        if offset + 1 > len(raw):
            raise ValueError("Invalid token: missing currency length field")
        currency_len = struct.unpack(">B", raw[offset:offset+1])[0]
        offset += 1

        if offset + currency_len > len(raw):
            raise ValueError("Invalid token: incomplete currency")
        payout_currency = raw[offset:offset+currency_len].decode('utf-8')
        offset += currency_len

        # Read network length and data
        if offset + 1 > len(raw):
            raise ValueError("Invalid token: missing network length field")
        network_len = struct.unpack(">B", raw[offset:offset+1])[0]
        offset += 1

        if offset + network_len > len(raw):
            raise ValueError("Invalid token: incomplete network")
        payout_network = raw[offset:offset+network_len].decode('utf-8')
        offset += network_len

        # The remaining bytes should be the 16-byte truncated signature
        if len(raw) - offset != 16:
            raise ValueError(f"Invalid token: wrong signature size (got {len(raw) - offset}, expected 16)")

        data = raw[:offset]  # All data except signature
        sig = raw[offset:]   # The signature

        # Debug logs
        print(f"🔍 [TOKEN] Token decoded successfully")
        print(f"👤 [TOKEN] User: {user_id}, Channel: {closed_channel_id}")
        print(f"💰 [TOKEN] Price: ${subscription_price}, Duration: {subscription_time_days} days")
        print(f"🏦 [TOKEN] Wallet: {wallet_address}")
        print(f"🌐 [TOKEN] Currency: {payout_currency}, Network: {payout_network}")

        # Verify truncated signature
        expected_full_sig = hmac.new(self.signing_key.encode(), data, hashlib.sha256).digest()
        expected_sig = expected_full_sig[:16]  # Compare only first 16 bytes
        if not hmac.compare_digest(sig, expected_sig):
            raise ValueError("Signature mismatch")

        # If IDs are "negative" in Telegram, fix here (48-bit range):
        if user_id > 2**47 - 1:
            user_id -= 2**48
        if closed_channel_id > 2**47 - 1:
            closed_channel_id -= 2**48

        # Reconstruct full timestamp from minutes
        current_time = int(time.time())
        current_minutes = current_time // 60

        # Handle timestamp wrap-around (65536 minute cycle ≈ 45 days)
        minutes_in_current_cycle = current_minutes % 65536
        base_minutes = current_minutes - minutes_in_current_cycle

        if timestamp_minutes > minutes_in_current_cycle:
            # Timestamp is likely from previous cycle
            timestamp = (base_minutes - 65536 + timestamp_minutes) * 60
        else:
            # Timestamp is from current cycle
            timestamp = (base_minutes + timestamp_minutes) * 60

        # Additional validation: ensure timestamp is reasonable (within ~45 days)
        time_diff = abs(current_time - timestamp)
        if time_diff > 45 * 24 * 3600:  # 45 days in seconds
            raise ValueError(f"Timestamp too far from current time: {time_diff} seconds difference")

        print(f"🔓 [TOKEN] Signature verified successfully")
        print(f"⏰ [TOKEN] Timestamp: {timestamp} (from minutes: {timestamp_minutes})")

        # Check for expiration (2hr window)
        now = int(time.time())
        if not (now - 7200 <= timestamp <= now + 300):
            raise ValueError("Token expired or not yet valid")

        return user_id, closed_channel_id, wallet_address, payout_currency, payout_network, subscription_time_days, subscription_price

    def encrypt_token_for_gcwebhook2(
        self,
        user_id: int,
        closed_channel_id: int,
        wallet_address: str,
        payout_currency: str,
        payout_network: str,
        subscription_time_days: int,
        subscription_price: str
    ) -> Optional[str]:
        """
        Encrypt token to send to GCWebhook2 (Telegram invite sender).

        Token format (same as NOWPayments token, but freshly encrypted):
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
            user_id: User's Telegram ID
            closed_channel_id: Channel ID
            wallet_address: Client's wallet address
            payout_currency: Client's preferred payout currency
            payout_network: Client's payout network
            subscription_time_days: Subscription duration in days
            subscription_price: Subscription price as string

        Returns:
            Base64-encoded encrypted token or None if failed
        """
        try:
            # Validate input types
            if not isinstance(user_id, int):
                raise ValueError(f"user_id must be integer, got {type(user_id).__name__}: {user_id}")
            if not isinstance(closed_channel_id, int):
                raise ValueError(f"closed_channel_id must be integer, got {type(closed_channel_id).__name__}: {closed_channel_id}")
            if not isinstance(subscription_time_days, int):
                raise ValueError(f"subscription_time_days must be integer, got {type(subscription_time_days).__name__}: {subscription_time_days}")
            if not isinstance(subscription_price, str):
                raise ValueError(f"subscription_price must be string, got {type(subscription_price).__name__}: {subscription_price}")

            # Convert IDs to 48-bit format (handle negative IDs)
            if user_id < 0:
                user_id += 2**48
            if closed_channel_id < 0:
                closed_channel_id += 2**48

            # Get current timestamp in minutes (for 16-bit wrap-around)
            current_time = int(time.time())
            timestamp_minutes = (current_time // 60) % 65536

            # Build token data
            packed_data = bytearray()

            # Add fixed fields
            packed_data.extend(user_id.to_bytes(6, 'big'))
            packed_data.extend(closed_channel_id.to_bytes(6, 'big'))
            packed_data.extend(struct.pack(">H", timestamp_minutes))
            packed_data.extend(struct.pack(">H", subscription_time_days))

            # Add variable fields
            price_bytes = subscription_price.encode('utf-8')
            packed_data.append(len(price_bytes))
            packed_data.extend(price_bytes)

            wallet_bytes = wallet_address.encode('utf-8')
            packed_data.append(len(wallet_bytes))
            packed_data.extend(wallet_bytes)

            currency_bytes = payout_currency.encode('utf-8')
            packed_data.append(len(currency_bytes))
            packed_data.extend(currency_bytes)

            network_bytes = payout_network.encode('utf-8')
            packed_data.append(len(network_bytes))
            packed_data.extend(network_bytes)

            # Calculate truncated HMAC signature
            full_signature = hmac.new(self.signing_key.encode(), bytes(packed_data), hashlib.sha256).digest()
            truncated_signature = full_signature[:16]

            # Combine data + signature
            final_data = bytes(packed_data) + truncated_signature

            # Encode to base64 (URL-safe, without padding)
            token = base64.urlsafe_b64encode(final_data).rstrip(b'=').decode('utf-8')

            print(f"🔐 [TOKEN] Encrypted token for GCWebhook2 (length: {len(token)})")
            return token

        except Exception as e:
            print(f"❌ [TOKEN] Error encrypting token for GCWebhook2: {e}")
            return None
