#!/usr/bin/env python
"""
Base Token Manager for PGP_v1 Services.
Provides common token utility methods shared across all PGP_v1 microservices.
"""
import base64
import hmac
import hashlib
import struct
import time
from typing import Tuple, Optional


class BaseTokenManager:
    """
    Base class for token management across all PGP_v1 services.

    This class provides common utility methods for:
    - HMAC signature generation and verification
    - Base64 encoding/decoding
    - String packing/unpacking with length prefixes
    - Timestamp handling

    Service-specific token formats remain in subclasses.
    """

    def __init__(self, signing_key: str, service_name: str, secondary_key: Optional[str] = None):
        """
        Initialize the BaseTokenManager.

        Args:
            signing_key: Primary signing key (SUCCESS_URL_SIGNING_KEY) for token verification and encryption
            service_name: Name of the service (for logging)
            secondary_key: Optional secondary signing key for dual-key services (e.g., TPS_HOSTPAY_SIGNING_KEY, PGP_INTERNAL_SIGNING_KEY)
        """
        self.signing_key = signing_key
        self.secondary_key = secondary_key if secondary_key else signing_key
        self.service_name = service_name
        print(f"🔐 [TOKEN] TokenManager initialized for {service_name}")
        if secondary_key:
            print(f"🔐 [TOKEN] Secondary signing key configured for {service_name}")

    def generate_hmac_signature(self, data: bytes, truncate_to: int = 16) -> bytes:
        """
        Generate HMAC-SHA256 signature for data.

        Args:
            data: Data to sign
            truncate_to: Number of bytes to truncate signature to (default 16)

        Returns:
            HMAC signature bytes (truncated if specified)
        """
        full_signature = hmac.new(
            self.signing_key.encode(),
            data,
            hashlib.sha256
        ).digest()

        if truncate_to > 0:
            return full_signature[:truncate_to]
        return full_signature

    def verify_hmac_signature(self, data: bytes, signature: bytes, truncate_to: int = 16) -> bool:
        """
        Verify HMAC-SHA256 signature.

        Args:
            data: Data that was signed
            signature: Signature to verify
            truncate_to: Number of bytes signature was truncated to (default 16)

        Returns:
            True if signature is valid, False otherwise
        """
        expected_sig = self.generate_hmac_signature(data, truncate_to)
        return hmac.compare_digest(signature, expected_sig)

    def generate_hmac_signature_secondary(self, data: bytes, truncate_to: int = 16) -> bytes:
        """
        Generate HMAC-SHA256 signature using secondary key for dual-key services.

        Args:
            data: Data to sign
            truncate_to: Number of bytes to truncate signature to (default 16)

        Returns:
            HMAC signature bytes (truncated if specified)
        """
        full_signature = hmac.new(
            self.secondary_key.encode(),
            data,
            hashlib.sha256
        ).digest()

        if truncate_to > 0:
            return full_signature[:truncate_to]
        return full_signature

    def verify_hmac_signature_secondary(self, data: bytes, signature: bytes, truncate_to: int = 16) -> bool:
        """
        Verify HMAC-SHA256 signature using secondary key for dual-key services.

        Args:
            data: Data that was signed
            signature: Signature to verify
            truncate_to: Number of bytes signature was truncated to (default 16)

        Returns:
            True if signature is valid, False otherwise
        """
        expected_sig = self.generate_hmac_signature_secondary(data, truncate_to)
        return hmac.compare_digest(signature, expected_sig)

    def pack_string(self, value: str) -> bytes:
        """
        Pack a string with length prefix (1 byte length + UTF-8 bytes).

        This method is 100% identical across all services using tokens.

        Args:
            value: String to pack

        Returns:
            Packed bytes (1 byte length + string data)

        Raises:
            ValueError: If string is longer than 255 bytes when encoded
        """
        value_bytes = value.encode('utf-8')
        if len(value_bytes) > 255:
            raise ValueError(f"String too long: {len(value_bytes)} bytes (max 255)")

        packed = bytearray()
        packed.append(len(value_bytes))
        packed.extend(value_bytes)
        return bytes(packed)

    def unpack_string(self, raw: bytes, offset: int) -> Tuple[str, int]:
        """
        Unpack a string with length prefix from raw bytes.

        This method is 100% identical across all services using tokens.

        Args:
            raw: Raw bytes containing packed string
            offset: Starting offset in raw bytes

        Returns:
            Tuple of (unpacked_string, new_offset)

        Raises:
            ValueError: If data is invalid or incomplete
        """
        if offset + 1 > len(raw):
            raise ValueError(f"Invalid token: missing string length field at offset {offset}")

        string_len = struct.unpack(">B", raw[offset:offset+1])[0]
        offset += 1

        if offset + string_len > len(raw):
            raise ValueError(f"Invalid token: incomplete string data at offset {offset}")

        string_value = raw[offset:offset+string_len].decode('utf-8')
        offset += string_len

        return string_value, offset

    def encode_base64_urlsafe(self, data: bytes) -> str:
        """
        Encode bytes to URL-safe base64 string (without padding).

        Args:
            data: Bytes to encode

        Returns:
            Base64-encoded string (URL-safe, no padding)
        """
        return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')

    def decode_base64_urlsafe(self, token: str) -> bytes:
        """
        Decode URL-safe base64 string to bytes (handles missing padding).

        Args:
            token: Base64-encoded string

        Returns:
            Decoded bytes

        Raises:
            ValueError: If token cannot be decoded
        """
        # Add padding if needed
        padding = '=' * (-len(token) % 4)
        try:
            return base64.urlsafe_b64decode(token + padding)
        except Exception as e:
            raise ValueError(f"Invalid token: cannot decode base64 - {e}")

    def get_timestamp_minutes(self) -> int:
        """
        Get current timestamp in minutes (for 16-bit wrap-around).

        Returns:
            Current time in minutes modulo 65536
        """
        current_time = int(time.time())
        return (current_time // 60) % 65536

    def reconstruct_timestamp_from_minutes(self, timestamp_minutes: int, max_age_days: int = 45) -> int:
        """
        Reconstruct full timestamp from 16-bit minutes value.

        Handles wrap-around (65536 minute cycle ≈ 45 days).

        Args:
            timestamp_minutes: Timestamp in minutes (16-bit)
            max_age_days: Maximum age in days to consider valid

        Returns:
            Reconstructed Unix timestamp in seconds

        Raises:
            ValueError: If timestamp is too far from current time
        """
        current_time = int(time.time())
        current_minutes = current_time // 60

        # Handle timestamp wrap-around
        minutes_in_current_cycle = current_minutes % 65536
        base_minutes = current_minutes - minutes_in_current_cycle

        if timestamp_minutes > minutes_in_current_cycle:
            # Timestamp is likely from previous cycle
            timestamp = (base_minutes - 65536 + timestamp_minutes) * 60
        else:
            # Timestamp is from current cycle
            timestamp = (base_minutes + timestamp_minutes) * 60

        # Validate timestamp is reasonable
        time_diff = abs(current_time - timestamp)
        max_age_seconds = max_age_days * 24 * 3600
        if time_diff > max_age_seconds:
            raise ValueError(f"Timestamp too far from current time: {time_diff} seconds difference (max {max_age_seconds})")

        return timestamp

    def convert_48bit_id(self, id_value: int) -> int:
        """
        Convert 48-bit ID to signed integer (handle negative Telegram IDs).

        Args:
            id_value: ID value in 48-bit unsigned format

        Returns:
            Signed integer ID
        """
        # If ID is in upper half of 48-bit range, it's negative in Telegram
        if id_value > 2**47 - 1:
            return id_value - 2**48
        return id_value

    def pack_48bit_id(self, id_value: int) -> bytes:
        """
        Pack signed integer ID to 48-bit unsigned bytes.

        Args:
            id_value: Signed integer ID (can be negative for Telegram)

        Returns:
            6 bytes representing 48-bit unsigned integer
        """
        # Convert negative IDs to 48-bit unsigned format
        if id_value < 0:
            id_value += 2**48

        return id_value.to_bytes(6, 'big')

    def unpack_48bit_id(self, raw: bytes, offset: int) -> Tuple[int, int]:
        """
        Unpack 48-bit ID from raw bytes and convert to signed integer.

        Args:
            raw: Raw bytes containing packed ID
            offset: Starting offset in raw bytes

        Returns:
            Tuple of (unpacked_id, new_offset)

        Raises:
            ValueError: If data is incomplete
        """
        if offset + 6 > len(raw):
            raise ValueError(f"Invalid token: missing 48-bit ID at offset {offset}")

        id_value = int.from_bytes(raw[offset:offset+6], 'big')
        id_value = self.convert_48bit_id(id_value)
        return id_value, offset + 6
