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

    def decrypt_accumulator_to_gchostpay1_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decrypt token from GCAccumulator → GCHostPay1.
        Token is valid for 300 seconds from creation (5-minute window).

        Token Format (from GCAccumulator encrypt_accumulator_to_gchostpay1_token):
        - 8 bytes: accumulation_id (uint64)
        - 1 byte: cn_api_id length + variable bytes for cn_api_id
        - 1 byte: from_currency length + variable bytes for from_currency
        - 1 byte: from_network length + variable bytes for from_network
        - 8 bytes: from_amount (double precision float)
        - 1 byte: payin_address length + variable bytes for payin_address
        - 1 byte: context length + variable bytes for context ('threshold')
        - 8 bytes: timestamp (uint64 unix timestamp)
        - 16 bytes: HMAC-SHA256 signature (truncated)

        Args:
            token: Base64 URL-safe encoded token from GCAccumulator

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

        # Minimum size check (8 + 1 + 1 + 1 + 8 + 1 + 1 + 8 + 16 = 45 minimum)
        if len(raw) < 45:
            raise ValueError(f"Invalid token: too small (got {len(raw)}, minimum 45)")

        offset = 0

        # Parse accumulation_id (8 bytes, uint64)
        if offset + 8 > len(raw):
            raise ValueError("Invalid token: missing accumulation_id")
        accumulation_id = struct.unpack(">Q", raw[offset:offset+8])[0]
        offset += 8

        # Parse variable-length cn_api_id
        cn_api_id, offset = self._unpack_string(raw, offset)

        # Parse variable-length from_currency
        from_currency, offset = self._unpack_string(raw, offset)

        # Parse variable-length from_network
        from_network, offset = self._unpack_string(raw, offset)

        # Parse 8-byte double for from_amount
        if offset + 8 > len(raw):
            raise ValueError("Invalid token: incomplete from_amount")
        from_amount = struct.unpack(">d", raw[offset:offset+8])[0]
        offset += 8

        # Parse variable-length payin_address
        payin_address, offset = self._unpack_string(raw, offset)

        # Parse variable-length context
        context, offset = self._unpack_string(raw, offset)

        # Parse 8-byte timestamp (uint64)
        if offset + 8 > len(raw):
            raise ValueError("Invalid token: incomplete timestamp")
        timestamp = struct.unpack(">Q", raw[offset:offset+8])[0]
        offset += 8

        # The remaining bytes should be the 16-byte truncated signature
        if len(raw) - offset != 16:
            raise ValueError(f"Invalid token: wrong signature size (got {len(raw) - offset}, expected 16)")

        data = raw[:offset]  # All data except signature
        sig = raw[offset:]   # The signature

        # Verify truncated signature using SUCCESS_URL_SIGNING_KEY (internal key)
        expected_full_sig = hmac.new(self.internal_key.encode(), data, hashlib.sha256).digest()
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

        print(f"🔓 [TOKEN_DEC] GCAccumulator→GCHostPay1: Token validated successfully")
        print(f"⏰ [TOKEN_DEC] Token age: {current_time - timestamp} seconds")
        print(f"📋 [TOKEN_DEC] Context: {context}")
        print(f"🆔 [TOKEN_DEC] Accumulation ID: {accumulation_id}")

        return {
            "accumulation_id": accumulation_id,
            "cn_api_id": cn_api_id,
            "from_currency": from_currency,
            "from_network": from_network,
            "from_amount": from_amount,
            "payin_address": payin_address,
            "context": context,
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
        context: str = 'instant'
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
        - 1 byte: context length + variable bytes (NEW: 'instant' or 'threshold')
        - 4 bytes: timestamp
        - 16 bytes: HMAC signature

        Args:
            context: Payment context - 'instant' for direct payouts, 'threshold' for accumulator payouts

        Returns:
            Base64 URL-safe encoded token or None if failed
        """
        try:
            print(f"🔐 [TOKEN_ENC] GCHostPay1→GCHostPay3: Encrypting payment request")
            print(f"📋 [TOKEN_ENC] Context: {context}")

            unique_id_bytes = unique_id.encode('utf-8')[:16].ljust(16, b'\x00')

            packed_data = bytearray()
            packed_data.extend(unique_id_bytes)
            packed_data.extend(self._pack_string(cn_api_id))
            packed_data.extend(self._pack_string(from_currency.lower()))
            packed_data.extend(self._pack_string(from_network.lower()))
            packed_data.extend(struct.pack(">d", from_amount))
            packed_data.extend(self._pack_string(payin_address))
            packed_data.extend(self._pack_string(context.lower()))  # NEW: context field

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
            return token

        except Exception as e:
            print(f"❌ [TOKEN_ENC] Encryption error: {e}")
            return None

    def decrypt_gchostpay1_to_gchostpay3_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decrypt token from GCHostPay1 → GCHostPay3.
        Token valid for 300 seconds (5 minutes).

        Returns:
            Dictionary with payment details or None
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
    # TOKEN 7: GCMicroBatchProcessor → GCHostPay1 (Batch execution request)
    # ========================================================================

    def decrypt_microbatch_to_gchostpay1_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decrypt token from GCMicroBatchProcessor → GCHostPay1.
        Token is valid for 300 seconds from creation (5-minute window).

        Token Format (from GCMicroBatchProcessor encrypt_microbatch_to_gchostpay1_token):
        - 1 byte: context length + variable bytes ('batch')
        - 1 byte: batch_conversion_id length + variable bytes (UUID string)
        - 1 byte: cn_api_id length + variable bytes
        - 1 byte: from_currency length + variable bytes
        - 1 byte: from_network length + variable bytes
        - 8 bytes: from_amount (double precision float)
        - 1 byte: payin_address length + variable bytes
        - 8 bytes: timestamp (uint64 unix timestamp)
        - 16 bytes: HMAC-SHA256 signature (truncated)

        Args:
            token: Base64 URL-safe encoded token from GCMicroBatchProcessor

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
        if len(raw) < 45:
            raise ValueError(f"Invalid token: too small (got {len(raw)}, minimum 45)")

        offset = 0

        # Parse context (variable length string, should be 'batch')
        context, offset = self._unpack_string(raw, offset)
        if context != 'batch':
            raise ValueError(f"Invalid context: expected 'batch', got '{context}'")

        # Parse batch_conversion_id (variable length string, UUID)
        batch_conversion_id, offset = self._unpack_string(raw, offset)

        # Parse variable-length cn_api_id
        cn_api_id, offset = self._unpack_string(raw, offset)

        # Parse variable-length from_currency
        from_currency, offset = self._unpack_string(raw, offset)

        # Parse variable-length from_network
        from_network, offset = self._unpack_string(raw, offset)

        # Parse 8-byte double for from_amount
        if offset + 8 > len(raw):
            raise ValueError("Invalid token: incomplete from_amount")
        from_amount = struct.unpack(">d", raw[offset:offset+8])[0]
        offset += 8

        # Parse variable-length payin_address
        payin_address, offset = self._unpack_string(raw, offset)

        # Parse 8-byte timestamp (uint64)
        if offset + 8 > len(raw):
            raise ValueError("Invalid token: incomplete timestamp")
        timestamp = struct.unpack(">Q", raw[offset:offset+8])[0]
        offset += 8

        # The remaining bytes should be the 16-byte truncated signature
        if len(raw) - offset != 16:
            raise ValueError(f"Invalid token: wrong signature size (got {len(raw) - offset}, expected 16)")

        data = raw[:offset]  # All data except signature
        sig = raw[offset:]   # The signature

        # Verify truncated signature using SUCCESS_URL_SIGNING_KEY (internal key)
        expected_full_sig = hmac.new(self.internal_key.encode(), data, hashlib.sha256).digest()
        expected_sig = expected_full_sig[:16]
        if not hmac.compare_digest(sig, expected_sig):
            raise ValueError("Signature mismatch - token may be tampered or invalid signing key")

        # Validate timestamp (5-minute window: current_time - 300 to current_time + 5)
        current_time = int(time.time())
        if not (current_time - 300 <= timestamp <= current_time + 5):
            time_diff = current_time - timestamp
            raise ValueError(f"Token expired (created {abs(time_diff)} seconds ago, max 300 seconds)")

        print(f"🔓 [TOKEN_DEC] GCMicroBatchProcessor→GCHostPay1: Token validated successfully")
        print(f"⏰ [TOKEN_DEC] Token age: {current_time - timestamp} seconds")
        print(f"📋 [TOKEN_DEC] Context: {context}")
        print(f"🆔 [TOKEN_DEC] Batch Conversion ID: {batch_conversion_id}")

        return {
            "context": context,
            "batch_conversion_id": batch_conversion_id,
            "cn_api_id": cn_api_id,
            "from_currency": from_currency,
            "from_network": from_network,
            "from_amount": from_amount,
            "payin_address": payin_address,
            "timestamp": timestamp
        }

    # ========================================================================
    # TOKEN 8: GCHostPay1 → GCMicroBatchProcessor (Batch execution response)
    # ========================================================================

    def encrypt_gchostpay1_to_microbatch_response_token(
        self,
        batch_conversion_id: str,
        cn_api_id: str,
        tx_hash: str,
        actual_usdt_received: float
    ) -> Optional[str]:
        """
        Encrypt token for GCHostPay1 → GCMicroBatchProcessor (Batch execution response).

        Token Structure:
        - 1 byte: batch_conversion_id length + variable bytes (UUID string)
        - 1 byte: cn_api_id length + variable bytes
        - 1 byte: tx_hash length + variable bytes
        - 8 bytes: actual_usdt_received (double)
        - 8 bytes: timestamp (uint64)
        - 16 bytes: HMAC signature

        Args:
            batch_conversion_id: Batch conversion UUID
            cn_api_id: ChangeNow transaction ID
            tx_hash: Ethereum transaction hash
            actual_usdt_received: Actual USDT amount received from ChangeNow

        Returns:
            Base64 URL-safe encoded token or None if failed
        """
        try:
            print(f"🔐 [TOKEN_ENC] GCHostPay1→GCMicroBatchProcessor: Encrypting batch response")

            payload = bytearray()

            # Pack batch_conversion_id
            payload.extend(self._pack_string(batch_conversion_id))

            # Pack cn_api_id
            payload.extend(self._pack_string(cn_api_id))

            # Pack tx_hash
            payload.extend(self._pack_string(tx_hash))

            # Pack actual_usdt_received (8 bytes, double)
            payload.extend(struct.pack(">d", actual_usdt_received))

            # Pack timestamp (8 bytes, uint64)
            timestamp = int(time.time())
            payload.extend(struct.pack(">Q", timestamp))

            # Generate HMAC signature using internal key
            signature = hmac.new(
                self.internal_key.encode(),
                bytes(payload),
                hashlib.sha256
            ).digest()[:16]

            # Combine payload + signature
            full_data = bytes(payload) + signature

            # Base64 encode
            token = base64.urlsafe_b64encode(full_data).decode('utf-8').rstrip('=')

            print(f"✅ [TOKEN_ENC] Batch response token created successfully")
            return token

        except Exception as e:
            print(f"❌ [TOKEN_ENC] Encryption error: {e}")
            return None
