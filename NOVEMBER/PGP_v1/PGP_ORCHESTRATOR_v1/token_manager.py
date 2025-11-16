#!/usr/bin/env python
"""
Token Manager for PGP_ORCHESTRATOR_v1 (Payment Processor Service).
Handles token decryption from NOWPayments and encryption for PGP_INVITE and PGP_SPLIT1.
"""
import struct
import time
from typing import Tuple, Optional
from PGP_COMMON.tokens import BaseTokenManager


class TokenManager(BaseTokenManager):
    """
    Manages token encryption and decryption for PGP_ORCHESTRATOR_v1.
    Inherits common utility methods from BaseTokenManager.
    """

    def __init__(self, signing_key: str):
        """
        Initialize the TokenManager.

        Args:
            signing_key: SUCCESS_URL_SIGNING_KEY for token verification and encryption
        """
        super().__init__(
            signing_key=signing_key,
            service_name="PGP_ORCHESTRATOR_v1"
        )

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
        # Decode base64 (using inherited method)
        raw = self.decode_base64_urlsafe(token)

        # Minimum size check: 6+6+2+2+1+1+1+1+1+1+16 = 38 bytes
        if len(raw) < 38:
            raise ValueError(f"Invalid token: too small (got {len(raw)}, minimum 38)")

        # Parse 48-bit IDs (using inherited methods)
        user_id, offset = self.unpack_48bit_id(raw, 0)
        closed_channel_id, offset = self.unpack_48bit_id(raw, offset)

        # Parse timestamp and subscription time
        timestamp_minutes = struct.unpack(">H", raw[offset:offset+2])[0]
        offset += 2
        subscription_time_days = struct.unpack(">H", raw[offset:offset+2])[0]
        offset += 2

        # Parse variable strings (using inherited methods)
        subscription_price, offset = self.unpack_string(raw, offset)
        wallet_address, offset = self.unpack_string(raw, offset)
        payout_currency, offset = self.unpack_string(raw, offset)
        payout_network, offset = self.unpack_string(raw, offset)

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

        # Verify signature (using inherited method)
        if not self.verify_hmac_signature(data, sig, truncate_to=16):
            raise ValueError("Signature mismatch")

        # Reconstruct full timestamp from minutes (using inherited method)
        timestamp = self.reconstruct_timestamp_from_minutes(timestamp_minutes)

        print(f"🔓 [TOKEN] Signature verified successfully")
        print(f"⏰ [TOKEN] Timestamp: {timestamp} (from minutes: {timestamp_minutes})")

        # Check for expiration (2hr window)
        now = int(time.time())
        if not (now - 7200 <= timestamp <= now + 300):
            raise ValueError("Token expired or not yet valid")

        return user_id, closed_channel_id, wallet_address, payout_currency, payout_network, subscription_time_days, subscription_price

    def encrypt_token_for_pgp_invite(
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
        Encrypt token to send to PGP_INVITE (formerly PGP_INVITE_v1) - Telegram invite sender.

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

            # Get current timestamp in minutes (using inherited method)
            timestamp_minutes = self.get_timestamp_minutes()

            # Build token data
            packed_data = bytearray()

            # Add fixed fields (using inherited methods)
            packed_data.extend(self.pack_48bit_id(user_id))
            packed_data.extend(self.pack_48bit_id(closed_channel_id))
            packed_data.extend(struct.pack(">H", timestamp_minutes))
            packed_data.extend(struct.pack(">H", subscription_time_days))

            # Add variable fields (using inherited methods)
            packed_data.extend(self.pack_string(subscription_price))
            packed_data.extend(self.pack_string(wallet_address))
            packed_data.extend(self.pack_string(payout_currency))
            packed_data.extend(self.pack_string(payout_network))

            # Calculate truncated HMAC signature (using inherited method)
            signature = self.generate_hmac_signature(bytes(packed_data), truncate_to=16)

            # Combine data + signature
            final_data = bytes(packed_data) + signature

            # Encode to base64 (using inherited method)
            token = self.encode_base64_urlsafe(final_data)

            print(f"🔐 [TOKEN] Encrypted token for PGP_INVITE (length: {len(token)})")
            return token

        except Exception as e:
            print(f"❌ [TOKEN] Error encrypting token for PGP_INVITE: {e}")
            return None
