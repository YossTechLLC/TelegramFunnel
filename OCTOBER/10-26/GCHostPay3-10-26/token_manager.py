#!/usr/bin/env python
"""
Token Manager for GCHostPay Services (GCHostPay1, GCHostPay2, GCHostPay3).
Handles token encryption/decryption for secure inter-service communication.

Token Encryption Strategy:
- GCSplit1 → GCHostPay1: Uses TPS_HOSTPAY_SIGNING_KEY (external communication)
- GCHostPay1 ↔ GCHostPay2: Uses SUCCESS_URL_SIGNING_KEY (internal communication)
- GCHostPay1 ↔ GCHostPay3: Uses SUCCESS_URL_SIGNING_KEY (internal communication)

All tokens use:
- Binary packing with struct module
- HMAC-SHA256 signatures (16-byte truncated)
- Base64 URL-safe encoding
- Timestamp validation (configurable windows)
"""
import time
import struct
import base64
import hmac
import hashlib
from typing import Optional, Dict, Any


class TokenManager:
    """
    Manages token encryption and decryption for GCHostPay services.
    """

    def __init__(self, tps_hostpay_signing_key: str, internal_signing_key: str):
        """
        Initialize TokenManager with signing keys.

        Args:
            tps_hostpay_signing_key: Key for GCSplit1 → GCHostPay1 communication
            internal_signing_key: Key for internal GCHostPay service communication
        """
        self.tps_hostpay_key = tps_hostpay_signing_key
        self.internal_key = internal_signing_key
        print(f"✅ [TOKEN_MGR] TokenManager initialized")

    def _pack_string(self, s: str) -> bytes:
        """Pack a string with length prefix (1 byte length + string bytes)."""
        s_bytes = s.encode('utf-8')
        if len(s_bytes) > 255:
            raise ValueError(f"String too long: {len(s_bytes)} bytes (max 255)")
        return bytes([len(s_bytes)]) + s_bytes

    def _unpack_string(self, data: bytes, offset: int) -> tuple:
        """
        Unpack a length-prefixed string.

        Returns:
            Tuple of (string_value, new_offset)
        """
        if offset >= len(data):
            raise ValueError("Offset beyond data length")

        str_len = data[offset]
        offset += 1

        if offset + str_len > len(data):
            raise ValueError(f"String extends beyond data ({offset + str_len} > {len(data)})")

        str_val = data[offset:offset+str_len].decode('utf-8')
        offset += str_len

        return str_val, offset

    # ========================================================================
    # TOKEN 1: GCSplit1 → GCHostPay1 (Incoming from external service)
    # ========================================================================

    def decrypt_gcsplit1_to_gchostpay1_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decrypt token from GCSplit1 → GCHostPay1.
        Token is valid for 60 seconds from creation (1-minute window).

        Token Format (from GCSplit1 build_hostpay_token):
        - 16 bytes: unique_id (UTF-8, fixed length, padded with nulls)
        - 1 byte: cn_api_id length + variable bytes for cn_api_id
        - 1 byte: from_currency length + variable bytes for from_currency
        - 1 byte: from_network length + variable bytes for from_network
        - 8 bytes: from_amount (double precision float)
        - 1 byte: payin_address length + variable bytes for payin_address
        - 4 bytes: timestamp (unix timestamp as uint32)
        - 16 bytes: HMAC-SHA256 signature (truncated)

        Args:
            token: Base64 URL-safe encoded token from GCSplit1

        Returns:
            Dictionary with decrypted data or None if invalid

        Raises:
            ValueError: If token is invalid, expired, or signature verification fails
        """
        padding = '=' * (-len(token) % 4)
        try:
            raw = base64.urlsafe_b64decode(token + padding)
        except Exception:
            raise ValueError("Invalid token: cannot decode base64")

        # Minimum size check
        if len(raw) < 52:
            raise ValueError(f"Invalid token: too small (got {len(raw)}, minimum 52)")

        offset = 0

        # Parse fixed 16-byte unique_id
        unique_id_bytes = raw[offset:offset+16]
        unique_id = unique_id_bytes.rstrip(b'\x00').decode('utf-8')
        offset += 16

        # Parse variable-length cn_api_id
        if offset + 1 > len(raw):
            raise ValueError("Invalid token: missing cn_api_id length field")
        cn_api_id_len = raw[offset]
        offset += 1

        if offset + cn_api_id_len > len(raw):
            raise ValueError("Invalid token: incomplete cn_api_id")
        cn_api_id = raw[offset:offset+cn_api_id_len].decode('utf-8')
        offset += cn_api_id_len

        # Parse variable-length from_currency
        if offset + 1 > len(raw):
            raise ValueError("Invalid token: missing from_currency length field")
        from_currency_len = raw[offset]
        offset += 1

        if offset + from_currency_len > len(raw):
            raise ValueError("Invalid token: incomplete from_currency")
        from_currency = raw[offset:offset+from_currency_len].decode('utf-8')
        offset += from_currency_len

        # Parse variable-length from_network
        if offset + 1 > len(raw):
            raise ValueError("Invalid token: missing from_network length field")
        from_network_len = raw[offset]
        offset += 1

        if offset + from_network_len > len(raw):
            raise ValueError("Invalid token: incomplete from_network")
        from_network = raw[offset:offset+from_network_len].decode('utf-8')
        offset += from_network_len

        # Parse 8-byte double for amount
        if offset + 8 > len(raw):
            raise ValueError("Invalid token: incomplete from_amount")
        from_amount = struct.unpack(">d", raw[offset:offset+8])[0]
        offset += 8

        # Parse variable-length payin_address
        if offset + 1 > len(raw):
            raise ValueError("Invalid token: missing payin_address length field")
        payin_address_len = raw[offset]
        offset += 1

        if offset + payin_address_len > len(raw):
            raise ValueError("Invalid token: incomplete payin_address")
        payin_address = raw[offset:offset+payin_address_len].decode('utf-8')
        offset += payin_address_len

        # Parse 4-byte timestamp
        if offset + 4 > len(raw):
            raise ValueError("Invalid token: incomplete timestamp")
        timestamp = struct.unpack(">I", raw[offset:offset+4])[0]
        offset += 4

        # The remaining bytes should be the 16-byte truncated signature
        if len(raw) - offset != 16:
            raise ValueError(f"Invalid token: wrong signature size (got {len(raw) - offset}, expected 16)")

        data = raw[:offset]  # All data except signature
        sig = raw[offset:]   # The signature

        # Verify truncated signature using TPS_HOSTPAY_SIGNING_KEY
        expected_full_sig = hmac.new(self.tps_hostpay_key.encode(), data, hashlib.sha256).digest()
        expected_sig = expected_full_sig[:16]
        if not hmac.compare_digest(sig, expected_sig):
            raise ValueError("Signature mismatch - token may be tampered or invalid signing key")

        # Validate timestamp (2-hour window: current_time - 7200 to current_time + 5)
        # Extended window to accommodate ETH transaction confirmation times (10-20 minutes),
        # Cloud Tasks retry backoff, and ChangeNow processing delays
        current_time = int(time.time())
        if not (current_time - 7200 <= timestamp <= current_time + 5):
            time_diff = current_time - timestamp
            raise ValueError(f"Token expired (created {abs(time_diff)} seconds ago, max 7200 seconds)")

        print(f"🔓 [TOKEN_DEC] GCSplit1→GCHostPay1: Token validated successfully")
        print(f"⏰ [TOKEN_DEC] Token age: {current_time - timestamp} seconds")

        return {
            "unique_id": unique_id,
            "cn_api_id": cn_api_id,
            "from_currency": from_currency,
            "from_network": from_network,
            "from_amount": from_amount,
            "payin_address": payin_address,
            "timestamp": timestamp
        }

    # ========================================================================
    # TOKEN 2: GCHostPay1 → GCHostPay2 (Status check request)
    # ========================================================================

    def encrypt_gchostpay1_to_gchostpay2_token(
        self,
        unique_id: str,
        cn_api_id: str,
        from_currency: str,
        from_network: str,
        from_amount: float,
        payin_address: str
    ) -> Optional[str]:
        """
        Encrypt token for GCHostPay1 → GCHostPay2 (Status check request).

        **CRITICAL FIX**: Includes ALL payment details so GCHostPay2 can pass them back
        in the response, enabling GCHostPay1 to create the GCHostPay3 payment request.

        Token Structure:
        - 16 bytes: unique_id (fixed)
        - 1 byte: cn_api_id length + variable bytes
        - 1 byte: from_currency length + variable bytes
        - 1 byte: from_network length + variable bytes
        - 8 bytes: from_amount (double)
        - 1 byte: payin_address length + variable bytes
        - 4 bytes: timestamp
        - 16 bytes: HMAC signature

        Args:
            unique_id: Database linking ID
            cn_api_id: ChangeNow transaction ID
            from_currency: Source currency (e.g., "eth")
            from_network: Source network (e.g., "eth")
            from_amount: Amount to send
            payin_address: ChangeNow payin address

        Returns:
            Base64 URL-safe encoded token or None if failed
        """
        try:
            print(f"🔐 [TOKEN_ENC] GCHostPay1→GCHostPay2: Encrypting status check request")

            unique_id_bytes = unique_id.encode('utf-8')[:16].ljust(16, b'\x00')

            packed_data = bytearray()
            packed_data.extend(unique_id_bytes)
            packed_data.extend(self._pack_string(cn_api_id))
            packed_data.extend(self._pack_string(from_currency.lower()))
            packed_data.extend(self._pack_string(from_network.lower()))
            packed_data.extend(struct.pack(">d", from_amount))
            packed_data.extend(self._pack_string(payin_address))

            current_timestamp = int(time.time())
            packed_data.extend(struct.pack(">I", current_timestamp))

            # Sign with internal key
            full_signature = hmac.new(
                self.internal_key.encode(),
                bytes(packed_data),
                hashlib.sha256
            ).digest()
            truncated_signature = full_signature[:16]

            final_data = bytes(packed_data) + truncated_signature
            token = base64.urlsafe_b64encode(final_data).rstrip(b'=').decode('utf-8')

            print(f"✅ [TOKEN_ENC] Status check request token encrypted ({len(token)} chars)")
            return token

        except Exception as e:
            print(f"❌ [TOKEN_ENC] Encryption error: {e}")
            return None

    def decrypt_gchostpay1_to_gchostpay2_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decrypt token from GCHostPay1 → GCHostPay2.
        Token valid for 300 seconds (5 minutes).

        Returns:
            Dictionary with {unique_id, cn_api_id, from_currency, from_network, from_amount, payin_address, timestamp}
        """
        padding = '=' * (-len(token) % 4)
        try:
            raw = base64.urlsafe_b64decode(token + padding)
        except Exception:
            raise ValueError("Invalid token: cannot decode base64")

        if len(raw) < 52:
            raise ValueError(f"Invalid token: too small (got {len(raw)}, minimum 52)")

        offset = 0

        # Parse unique_id
        unique_id = raw[offset:offset+16].rstrip(b'\x00').decode('utf-8')
        offset += 16

        # Parse cn_api_id
        cn_api_id, offset = self._unpack_string(raw, offset)

        # Parse from_currency
        from_currency, offset = self._unpack_string(raw, offset)

        # Parse from_network
        from_network, offset = self._unpack_string(raw, offset)

        # Parse from_amount
        if offset + 8 > len(raw):
            raise ValueError("Invalid token: incomplete from_amount")
        from_amount = struct.unpack(">d", raw[offset:offset+8])[0]
        offset += 8

        # Parse payin_address
        payin_address, offset = self._unpack_string(raw, offset)

        # Parse timestamp
        if offset + 4 > len(raw):
            raise ValueError("Invalid token: incomplete timestamp")
        timestamp = struct.unpack(">I", raw[offset:offset+4])[0]
        offset += 4

        # Verify signature
        if len(raw) - offset != 16:
            raise ValueError(f"Invalid token: wrong signature size")

        data = raw[:offset]
        sig = raw[offset:]

        expected_full_sig = hmac.new(self.internal_key.encode(), data, hashlib.sha256).digest()
        expected_sig = expected_full_sig[:16]
        if not hmac.compare_digest(sig, expected_sig):
            raise ValueError("Signature mismatch")

        # Validate timestamp (7200 second / 2-hour window)
        # Extended for ETH transaction confirmation, Cloud Tasks delivery delays and retries
        current_time = int(time.time())
        if not (current_time - 7200 <= timestamp <= current_time + 5):
            raise ValueError(f"Token expired")

        print(f"🔓 [TOKEN_DEC] GCHostPay1→GCHostPay2: Token validated")

        return {
            "unique_id": unique_id,
            "cn_api_id": cn_api_id,
            "from_currency": from_currency,
            "from_network": from_network,
            "from_amount": from_amount,
            "payin_address": payin_address,
            "timestamp": timestamp
        }

    # ========================================================================
    # TOKEN 3: GCHostPay2 → GCHostPay1 (Status check response)
    # ========================================================================

    def encrypt_gchostpay2_to_gchostpay1_token(
        self,
        unique_id: str,
        cn_api_id: str,
        status: str,
        from_currency: str,
        from_network: str,
        from_amount: float,
        payin_address: str
    ) -> Optional[str]:
        """
        Encrypt response token for GCHostPay2 → GCHostPay1 (status check response).

        **CRITICAL FIX**: Includes ALL payment details so GCHostPay1 can create
        the GCHostPay3 payment execution request.

        Token Structure:
        - 16 bytes: unique_id (fixed)
        - 1 byte: cn_api_id length + variable bytes
        - 1 byte: status length + variable bytes
        - 1 byte: from_currency length + variable bytes
        - 1 byte: from_network length + variable bytes
        - 8 bytes: from_amount (double)
        - 1 byte: payin_address length + variable bytes
        - 4 bytes: timestamp
        - 16 bytes: HMAC signature

        Args:
            unique_id: Database linking ID
            cn_api_id: ChangeNow transaction ID
            status: ChangeNow status ("waiting", "confirming", etc.)
            from_currency: Source currency (e.g., "eth")
            from_network: Source network (e.g., "eth")
            from_amount: Amount to send
            payin_address: ChangeNow payin address

        Returns:
            Base64 URL-safe encoded token or None if failed
        """
        try:
            print(f"🔐 [TOKEN_ENC] GCHostPay2→GCHostPay1: Encrypting status response")

            unique_id_bytes = unique_id.encode('utf-8')[:16].ljust(16, b'\x00')

            packed_data = bytearray()
            packed_data.extend(unique_id_bytes)
            packed_data.extend(self._pack_string(cn_api_id))
            packed_data.extend(self._pack_string(status))
            packed_data.extend(self._pack_string(from_currency.lower()))
            packed_data.extend(self._pack_string(from_network.lower()))
            packed_data.extend(struct.pack(">d", from_amount))
            packed_data.extend(self._pack_string(payin_address))

            current_timestamp = int(time.time())
            packed_data.extend(struct.pack(">I", current_timestamp))

            # Sign with internal key
            full_signature = hmac.new(
                self.internal_key.encode(),
                bytes(packed_data),
                hashlib.sha256
            ).digest()
            truncated_signature = full_signature[:16]

            final_data = bytes(packed_data) + truncated_signature
            token = base64.urlsafe_b64encode(final_data).rstrip(b'=').decode('utf-8')

            print(f"✅ [TOKEN_ENC] Status response token encrypted ({len(token)} chars)")
            return token

        except Exception as e:
            print(f"❌ [TOKEN_ENC] Encryption error: {e}")
            return None

    def decrypt_gchostpay2_to_gchostpay1_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decrypt response token from GCHostPay2 → GCHostPay1.
        Token valid for 300 seconds (5 minutes).

        Returns:
            Dictionary with {unique_id, cn_api_id, status, from_currency, from_network, from_amount, payin_address, timestamp}
        """
        padding = '=' * (-len(token) % 4)
        try:
            raw = base64.urlsafe_b64decode(token + padding)
        except Exception:
            raise ValueError("Invalid token: cannot decode base64")

        if len(raw) < 52:
            raise ValueError(f"Invalid token: too small")

        offset = 0

        # Parse unique_id
        unique_id = raw[offset:offset+16].rstrip(b'\x00').decode('utf-8')
        offset += 16

        # Parse cn_api_id
        cn_api_id, offset = self._unpack_string(raw, offset)

        # Parse status
        status, offset = self._unpack_string(raw, offset)

        # Parse from_currency
        from_currency, offset = self._unpack_string(raw, offset)

        # Parse from_network
        from_network, offset = self._unpack_string(raw, offset)

        # Parse from_amount
        if offset + 8 > len(raw):
            raise ValueError("Invalid token: incomplete from_amount")
        from_amount = struct.unpack(">d", raw[offset:offset+8])[0]
        offset += 8

        # Parse payin_address
        payin_address, offset = self._unpack_string(raw, offset)

        # Parse timestamp
        if offset + 4 > len(raw):
            raise ValueError("Invalid token: incomplete timestamp")
        timestamp = struct.unpack(">I", raw[offset:offset+4])[0]
        offset += 4

        # Verify signature
        if len(raw) - offset != 16:
            raise ValueError(f"Invalid token: wrong signature size")

        data = raw[:offset]
        sig = raw[offset:]

        expected_full_sig = hmac.new(self.internal_key.encode(), data, hashlib.sha256).digest()
        expected_sig = expected_full_sig[:16]
        if not hmac.compare_digest(sig, expected_sig):
            raise ValueError("Signature mismatch")

        # Validate timestamp (7200 second / 2-hour window)
        # Extended for ETH transaction confirmation, Cloud Tasks delivery delays and retries
        current_time = int(time.time())
        if not (current_time - 7200 <= timestamp <= current_time + 5):
            raise ValueError(f"Token expired")

        print(f"🔓 [TOKEN_DEC] GCHostPay2→GCHostPay1: Token validated")

        return {
            "unique_id": unique_id,
            "cn_api_id": cn_api_id,
            "status": status,
            "from_currency": from_currency,
            "from_network": from_network,
            "from_amount": from_amount,
            "payin_address": payin_address,
            "timestamp": timestamp
        }

    # ========================================================================
    # TOKEN 4: GCHostPay1 → GCHostPay3 (Payment execution request)
    # ========================================================================

    def encrypt_gchostpay1_to_gchostpay3_token(
        self,
        unique_id: str,
        cn_api_id: str,
        from_currency: str,
        from_network: str,
        from_amount: float,
        payin_address: str,
        context: str = 'instant',
        attempt_count: int = 1,
        first_attempt_at: Optional[int] = None,
        last_error_code: Optional[str] = None
    ) -> Optional[str]:
        """
        Encrypt token for GCHostPay1 → GCHostPay3 (ETH payment execution request).

        Token Structure:
        - 16 bytes: unique_id (fixed)
        - 1 byte: cn_api_id length + variable bytes
        - 1 byte: from_currency length + variable bytes
        - 1 byte: from_network length + variable bytes
        - 8 bytes: from_amount (double)
        - 1 byte: payin_address length + variable bytes
        - 1 byte: context length + variable bytes ('instant' or 'threshold')
        - 4 bytes: attempt_count (uint32) [NEW: retry tracking]
        - 4 bytes: first_attempt_at timestamp (uint32) [NEW: retry tracking]
        - 1 byte: last_error_code length + variable bytes [NEW: retry tracking, empty if None]
        - 4 bytes: timestamp
        - 16 bytes: HMAC signature

        Args:
            context: Payment context - 'instant' (default) or 'threshold'
            attempt_count: Current attempt number (default: 1 for first attempt)
            first_attempt_at: Timestamp of first attempt (default: current time)
            last_error_code: Error code from previous attempt (default: None)

        Returns:
            Base64 URL-safe encoded token or None if failed
        """
        try:
            print(f"🔐 [TOKEN_ENC] GCHostPay1→GCHostPay3: Encrypting payment request")
            print(f"📋 [TOKEN_ENC] Context: {context}, Attempt: {attempt_count}")

            unique_id_bytes = unique_id.encode('utf-8')[:16].ljust(16, b'\x00')

            # Default first_attempt_at to current time if not provided
            if first_attempt_at is None:
                first_attempt_at = int(time.time())

            packed_data = bytearray()
            packed_data.extend(unique_id_bytes)
            packed_data.extend(self._pack_string(cn_api_id))
            packed_data.extend(self._pack_string(from_currency.lower()))
            packed_data.extend(self._pack_string(from_network.lower()))
            packed_data.extend(struct.pack(">d", from_amount))
            packed_data.extend(self._pack_string(payin_address))
            packed_data.extend(self._pack_string(context.lower()))

            # NEW: Add retry tracking fields
            packed_data.extend(struct.pack(">I", attempt_count))
            packed_data.extend(struct.pack(">I", first_attempt_at))
            packed_data.extend(self._pack_string(last_error_code if last_error_code else ''))

            current_timestamp = int(time.time())
            packed_data.extend(struct.pack(">I", current_timestamp))

            # Sign with internal key
            full_signature = hmac.new(
                self.internal_key.encode(),
                bytes(packed_data),
                hashlib.sha256
            ).digest()
            truncated_signature = full_signature[:16]

            final_data = bytes(packed_data) + truncated_signature
            token = base64.urlsafe_b64encode(final_data).rstrip(b'=').decode('utf-8')

            print(f"✅ [TOKEN_ENC] Payment request token encrypted ({len(token)} chars)")
            if last_error_code:
                print(f"🔄 [TOKEN_ENC] Retry token - Previous error: {last_error_code}")
            return token

        except Exception as e:
            print(f"❌ [TOKEN_ENC] Encryption error: {e}")
            return None

    def decrypt_gchostpay1_to_gchostpay3_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decrypt token from GCHostPay1 → GCHostPay3.
        Token valid for 7200 seconds (2 hours).

        **UPDATED**: Now includes retry tracking fields (attempt_count, first_attempt_at, last_error_code)
        with full backward compatibility for legacy tokens.

        Returns:
            Dictionary with payment details including context field or None
        """
        padding = '=' * (-len(token) % 4)
        try:
            raw = base64.urlsafe_b64decode(token + padding)
        except Exception:
            raise ValueError("Invalid token: cannot decode base64")

        if len(raw) < 52:
            raise ValueError(f"Invalid token: too small")

        offset = 0

        # Parse unique_id
        unique_id = raw[offset:offset+16].rstrip(b'\x00').decode('utf-8')
        offset += 16

        # Parse cn_api_id
        cn_api_id, offset = self._unpack_string(raw, offset)

        # Parse from_currency
        from_currency, offset = self._unpack_string(raw, offset)

        # Parse from_network
        from_network, offset = self._unpack_string(raw, offset)

        # Parse from_amount
        if offset + 8 > len(raw):
            raise ValueError("Invalid token: incomplete from_amount")
        from_amount = struct.unpack(">d", raw[offset:offset+8])[0]
        offset += 8

        # Parse payin_address
        payin_address, offset = self._unpack_string(raw, offset)

        # Parse context (defaults to 'instant' for backward compatibility)
        try:
            context, offset = self._unpack_string(raw, offset)
        except (ValueError, IndexError):
            # Backward compatibility: if context field doesn't exist, default to 'instant'
            context = 'instant'
            print(f"⚠️ [TOKEN_DEC] No context field found - defaulting to 'instant' (legacy token)")

        # NEW: Parse retry tracking fields (with backward compatibility)
        attempt_count = 1
        first_attempt_at = None
        last_error_code = None

        try:
            # Try to parse attempt_count (4 bytes)
            if offset + 4 <= len(raw) - 20:  # Need at least 20 more bytes (4 + 4 + 1 + 4 + 16)
                attempt_count = struct.unpack(">I", raw[offset:offset+4])[0]
                offset += 4

                # Try to parse first_attempt_at (4 bytes)
                if offset + 4 <= len(raw) - 16:
                    first_attempt_at = struct.unpack(">I", raw[offset:offset+4])[0]
                    offset += 4

                    # Try to parse last_error_code (variable length string)
                    try:
                        last_error_code_str, offset = self._unpack_string(raw, offset)
                        last_error_code = last_error_code_str if last_error_code_str else None
                    except (ValueError, IndexError):
                        # If parsing fails, this is a legacy token
                        pass
        except (ValueError, IndexError, struct.error):
            # If any retry field parsing fails, treat as legacy token (defaults already set)
            print(f"⚠️ [TOKEN_DEC] No retry fields found - treating as legacy token (attempt_count=1)")

        # If first_attempt_at is None, default to current time (legacy token)
        if first_attempt_at is None:
            first_attempt_at = int(time.time())

        # Parse timestamp
        if offset + 4 > len(raw):
            raise ValueError("Invalid token: incomplete timestamp")
        timestamp = struct.unpack(">I", raw[offset:offset+4])[0]
        offset += 4

        # Verify signature
        if len(raw) - offset != 16:
            raise ValueError(f"Invalid token: wrong signature size")

        data = raw[:offset]
        sig = raw[offset:]

        expected_full_sig = hmac.new(self.internal_key.encode(), data, hashlib.sha256).digest()
        expected_sig = expected_full_sig[:16]
        if not hmac.compare_digest(sig, expected_sig):
            raise ValueError("Signature mismatch")

        # Validate timestamp (7200 second / 2-hour window)
        # Extended for ETH transaction confirmation, Cloud Tasks delivery delays and retries
        current_time = int(time.time())
        if not (current_time - 7200 <= timestamp <= current_time + 5):
            raise ValueError(f"Token expired")

        print(f"🔓 [TOKEN_DEC] GCHostPay1→GCHostPay3: Token validated")
        print(f"📋 [TOKEN_DEC] Context: {context}, Attempt: {attempt_count}")
        if last_error_code:
            print(f"⚠️ [TOKEN_DEC] Previous error: {last_error_code}")

        return {
            "unique_id": unique_id,
            "cn_api_id": cn_api_id,
            "from_currency": from_currency,
            "from_network": from_network,
            "from_amount": from_amount,
            "payin_address": payin_address,
            "context": context,
            "timestamp": timestamp,
            # NEW: Retry tracking fields
            "attempt_count": attempt_count,
            "first_attempt_at": first_attempt_at,
            "last_error_code": last_error_code
        }

    # ========================================================================
    # TOKEN 5: GCHostPay3 → GCHostPay1 (Payment execution response)
    # ========================================================================

    def encrypt_gchostpay3_to_gchostpay1_token(
        self,
        unique_id: str,
        cn_api_id: str,
        tx_hash: str,
        tx_status: str,
        gas_used: int,
        block_number: int
    ) -> Optional[str]:
        """
        Encrypt response token for GCHostPay3 → GCHostPay1 (payment execution response).

        Token Structure:
        - 16 bytes: unique_id (fixed)
        - 1 byte: cn_api_id length + variable bytes
        - 1 byte: tx_hash length + variable bytes
        - 1 byte: tx_status length + variable bytes
        - 8 bytes: gas_used (uint64)
        - 8 bytes: block_number (uint64)
        - 4 bytes: timestamp
        - 16 bytes: HMAC signature

        Returns:
            Base64 URL-safe encoded token or None if failed
        """
        try:
            print(f"🔐 [TOKEN_ENC] GCHostPay3→GCHostPay1: Encrypting payment response")

            unique_id_bytes = unique_id.encode('utf-8')[:16].ljust(16, b'\x00')

            packed_data = bytearray()
            packed_data.extend(unique_id_bytes)
            packed_data.extend(self._pack_string(cn_api_id))
            packed_data.extend(self._pack_string(tx_hash))
            packed_data.extend(self._pack_string(tx_status))
            packed_data.extend(struct.pack(">Q", gas_used))
            packed_data.extend(struct.pack(">Q", block_number))

            current_timestamp = int(time.time())
            packed_data.extend(struct.pack(">I", current_timestamp))

            # Sign with internal key
            full_signature = hmac.new(
                self.internal_key.encode(),
                bytes(packed_data),
                hashlib.sha256
            ).digest()
            truncated_signature = full_signature[:16]

            final_data = bytes(packed_data) + truncated_signature
            token = base64.urlsafe_b64encode(final_data).rstrip(b'=').decode('utf-8')

            print(f"✅ [TOKEN_ENC] Payment response token encrypted ({len(token)} chars)")
            return token

        except Exception as e:
            print(f"❌ [TOKEN_ENC] Encryption error: {e}")
            return None

    def decrypt_gchostpay3_to_gchostpay1_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decrypt response token from GCHostPay3 → GCHostPay1.
        Token valid for 300 seconds (5 minutes).

        Returns:
            Dictionary with payment results or None
        """
        padding = '=' * (-len(token) % 4)
        try:
            raw = base64.urlsafe_b64decode(token + padding)
        except Exception:
            raise ValueError("Invalid token: cannot decode base64")

        if len(raw) < 52:
            raise ValueError(f"Invalid token: too small")

        offset = 0

        # Parse unique_id
        unique_id = raw[offset:offset+16].rstrip(b'\x00').decode('utf-8')
        offset += 16

        # Parse cn_api_id
        cn_api_id, offset = self._unpack_string(raw, offset)

        # Parse tx_hash
        tx_hash, offset = self._unpack_string(raw, offset)

        # Parse tx_status
        tx_status, offset = self._unpack_string(raw, offset)

        # Parse gas_used
        if offset + 8 > len(raw):
            raise ValueError("Invalid token: incomplete gas_used")
        gas_used = struct.unpack(">Q", raw[offset:offset+8])[0]
        offset += 8

        # Parse block_number
        if offset + 8 > len(raw):
            raise ValueError("Invalid token: incomplete block_number")
        block_number = struct.unpack(">Q", raw[offset:offset+8])[0]
        offset += 8

        # Parse timestamp
        if offset + 4 > len(raw):
            raise ValueError("Invalid token: incomplete timestamp")
        timestamp = struct.unpack(">I", raw[offset:offset+4])[0]
        offset += 4

        # Verify signature
        if len(raw) - offset != 16:
            raise ValueError(f"Invalid token: wrong signature size")

        data = raw[:offset]
        sig = raw[offset:]

        expected_full_sig = hmac.new(self.internal_key.encode(), data, hashlib.sha256).digest()
        expected_sig = expected_full_sig[:16]
        if not hmac.compare_digest(sig, expected_sig):
            raise ValueError("Signature mismatch")

        # Validate timestamp (7200 second / 2-hour window)
        # Extended for ETH transaction confirmation, Cloud Tasks delivery delays and retries
        current_time = int(time.time())
        if not (current_time - 7200 <= timestamp <= current_time + 5):
            raise ValueError(f"Token expired")

        print(f"🔓 [TOKEN_DEC] GCHostPay3→GCHostPay1: Token validated")

        return {
            "unique_id": unique_id,
            "cn_api_id": cn_api_id,
            "tx_hash": tx_hash,
            "tx_status": tx_status,
            "gas_used": gas_used,
            "block_number": block_number,
            "timestamp": timestamp
        }

    # ========================================================================
    # TOKEN 6: GCHostPay3 → GCHostPay3 (Self-retry after failure) [NEW]
    # ========================================================================

    def encrypt_gchostpay3_retry_token(
        self,
        token_data: Dict[str, Any],
        error_code: str
    ) -> Optional[str]:
        """
        NEW METHOD: Encrypt token for GCHostPay3 self-retry after payment failure.

        This method is called when a payment fails but is retryable (attempt_count < 3).
        It increments the attempt_count and adds the error_code from the failed attempt.

        Args:
            token_data: Decrypted token data from previous attempt (dict)
            error_code: Error code from the failed attempt (e.g., "RATE_LIMIT_EXCEEDED")

        Returns:
            Base64 URL-safe encoded retry token or None if failed

        Example:
            >>> failed_token_data = {
            ...     'unique_id': 'abc123',
            ...     'cn_api_id': 'xyz789',
            ...     'from_currency': 'eth',
            ...     'from_network': 'eth',
            ...     'from_amount': 0.001234,
            ...     'payin_address': '0x...',
            ...     'context': 'instant',
            ...     'attempt_count': 1,
            ...     'first_attempt_at': 1730419200,
            ...     'last_error_code': None
            ... }
            >>> retry_token = token_mgr.encrypt_gchostpay3_retry_token(
            ...     failed_token_data,
            ...     error_code='RATE_LIMIT_EXCEEDED'
            ... )
            >>> # retry_token will have attempt_count=2, last_error_code='RATE_LIMIT_EXCEEDED'
        """
        try:
            print(f"🔄 [TOKEN_RETRY] Building retry token for GCHostPay3 self-enqueue")
            print(f"🔄 [TOKEN_RETRY] Previous attempt: {token_data.get('attempt_count', 1)}")
            print(f"🔄 [TOKEN_RETRY] Error code: {error_code}")

            # Increment attempt count
            new_attempt_count = token_data.get('attempt_count', 1) + 1

            # Preserve first_attempt_at (should already exist)
            first_attempt_at = token_data.get('first_attempt_at', int(time.time()))

            # Build retry token using encrypt_gchostpay1_to_gchostpay3_token
            retry_token = self.encrypt_gchostpay1_to_gchostpay3_token(
                unique_id=token_data['unique_id'],
                cn_api_id=token_data['cn_api_id'],
                from_currency=token_data['from_currency'],
                from_network=token_data['from_network'],
                from_amount=token_data['from_amount'],
                payin_address=token_data['payin_address'],
                context=token_data.get('context', 'instant'),
                attempt_count=new_attempt_count,
                first_attempt_at=first_attempt_at,
                last_error_code=error_code
            )

            if retry_token:
                print(f"✅ [TOKEN_RETRY] Retry token created (attempt {new_attempt_count}/3)")
            else:
                print(f"❌ [TOKEN_RETRY] Failed to create retry token")

            return retry_token

        except Exception as e:
            print(f"❌ [TOKEN_RETRY] Retry token encryption error: {e}")
            return None
