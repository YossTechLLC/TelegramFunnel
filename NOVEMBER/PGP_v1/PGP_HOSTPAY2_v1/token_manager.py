#!/usr/bin/env python
"""
Token Manager for PGP_HOSTPAY2_v1.
Handles encryption and decryption of tokens for secure inter-service communication via Cloud Tasks.
"""
from typing import Dict, Any, Optional, Tuple
from PGP_COMMON.tokens import BaseTokenManager


class TokenManager(BaseTokenManager):
    """
    Manages token encryption and decryption for PGP_HOSTPAY2_v1.
    Inherits common methods from BaseTokenManager.
    """

    def __init__(self, signing_key: str):
        """
        Initialize TokenManager with signing key.

        Args:
            signing_key: SUCCESS_URL_SIGNING_KEY for HMAC signing
        """
        super().__init__(signing_key, service_name="PGP_HOSTPAY2_v1")

        str_val = data[offset:offset+str_len].decode('utf-8')
        offset += str_len

        return str_val, offset

    # ========================================================================
    # TOKEN 1: PGP_SPLIT1_v1 → PGP_HOSTPAY1_v1 (Incoming from external service)
    # ========================================================================

    def decrypt_gcsplit1_to_gchostpay1_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decrypt token from PGP_SPLIT1_v1 → PGP_HOSTPAY1_v1.
        Token is valid for 60 seconds from creation (1-minute window).

        Token Format (from PGP_SPLIT1_v1 build_hostpay_token):
        - 16 bytes: unique_id (UTF-8, fixed length, padded with nulls)
        - 1 byte: cn_api_id length + variable bytes for cn_api_id
        - 1 byte: from_currency length + variable bytes for from_currency
        - 1 byte: from_network length + variable bytes for from_network
        - 8 bytes: from_amount (double precision float)
        - 1 byte: payin_address length + variable bytes for payin_address
        - 4 bytes: timestamp (unix timestamp as uint32)
        - 16 bytes: HMAC-SHA256 signature (truncated)

        Args:
            token: Base64 URL-safe encoded token from PGP_SPLIT1_v1

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

        # Validate timestamp (5-minute window: current_time - 300 to current_time + 5)
        # Extended window to accommodate Cloud Tasks delivery delays and retry backoff (60s)
        current_time = int(time.time())
        if not (current_time - 300 <= timestamp <= current_time + 5):
            time_diff = current_time - timestamp
            raise ValueError(f"Token expired (created {abs(time_diff)} seconds ago, max 300 seconds)")

        print(f"🔓 [TOKEN_DEC] PGP_SPLIT1_v1→PGP_HOSTPAY1_v1: Token validated successfully")
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
    # TOKEN 2: PGP_HOSTPAY1_v1 → PGP_HOSTPAY2_v1 (Status check request)
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
        Encrypt token for PGP_HOSTPAY1_v1 → PGP_HOSTPAY2_v1 (Status check request).

        **CRITICAL FIX**: Includes ALL payment details so PGP_HOSTPAY2_v1 can pass them back
        in the response, enabling PGP_HOSTPAY1_v1 to create the PGP_HOSTPAY3_v1 payment request.

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
            print(f"🔐 [TOKEN_ENC] PGP_HOSTPAY1_v1→PGP_HOSTPAY2_v1: Encrypting status check request")

            packed_data = bytearray()
            packed_data.extend(self.pack_string(unique_id))
            packed_data.extend(self.pack_string(cn_api_id))
            packed_data.extend(self.pack_string(from_currency.lower()))
            packed_data.extend(self.pack_string(from_network.lower()))
            packed_data.extend(struct.pack(">d", from_amount))
            packed_data.extend(self.pack_string(payin_address))

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
        Decrypt token from PGP_HOSTPAY1_v1 → PGP_HOSTPAY2_v1.
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
        unique_id, offset = self.unpack_string(raw, offset)

        # Parse cn_api_id
        cn_api_id, offset = self.unpack_string(raw, offset)

        # Parse from_currency
        from_currency, offset = self.unpack_string(raw, offset)

        # Parse from_network
        from_network, offset = self.unpack_string(raw, offset)

        # Parse from_amount
        if offset + 8 > len(raw):
            raise ValueError("Invalid token: incomplete from_amount")
        from_amount = struct.unpack(">d", raw[offset:offset+8])[0]
        offset += 8

        # Parse payin_address
        payin_address, offset = self.unpack_string(raw, offset)

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

        # Validate timestamp (300 second / 5-minute window)
        # Extended for Cloud Tasks delivery delays and retries
        current_time = int(time.time())
        if not (current_time - 300 <= timestamp <= current_time + 5):
            raise ValueError(f"Token expired")

        print(f"🔓 [TOKEN_DEC] PGP_HOSTPAY1_v1→PGP_HOSTPAY2_v1: Token validated")

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
    # TOKEN 3: PGP_HOSTPAY2_v1 → PGP_HOSTPAY1_v1 (Status check response)
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
        Encrypt response token for PGP_HOSTPAY2_v1 → PGP_HOSTPAY1_v1 (status check response).

        **CRITICAL FIX**: Includes ALL payment details so PGP_HOSTPAY1_v1 can create
        the PGP_HOSTPAY3_v1 payment execution request.

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
            print(f"🔐 [TOKEN_ENC] PGP_HOSTPAY2_v1→PGP_HOSTPAY1_v1: Encrypting status response")

            packed_data = bytearray()
            packed_data.extend(self.pack_string(unique_id))
            packed_data.extend(self.pack_string(cn_api_id))
            packed_data.extend(self.pack_string(status))
            packed_data.extend(self.pack_string(from_currency.lower()))
            packed_data.extend(self.pack_string(from_network.lower()))
            packed_data.extend(struct.pack(">d", from_amount))
            packed_data.extend(self.pack_string(payin_address))

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
        Decrypt response token from PGP_HOSTPAY2_v1 → PGP_HOSTPAY1_v1.
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
        unique_id, offset = self.unpack_string(raw, offset)

        # Parse cn_api_id
        cn_api_id, offset = self.unpack_string(raw, offset)

        # Parse status
        status, offset = self.unpack_string(raw, offset)

        # Parse from_currency
        from_currency, offset = self.unpack_string(raw, offset)

        # Parse from_network
        from_network, offset = self.unpack_string(raw, offset)

        # Parse from_amount
        if offset + 8 > len(raw):
            raise ValueError("Invalid token: incomplete from_amount")
        from_amount = struct.unpack(">d", raw[offset:offset+8])[0]
        offset += 8

        # Parse payin_address
        payin_address, offset = self.unpack_string(raw, offset)

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

        # Validate timestamp (300 second / 5-minute window)
        # Extended for Cloud Tasks delivery delays and retries
        current_time = int(time.time())
        if not (current_time - 300 <= timestamp <= current_time + 5):
            raise ValueError(f"Token expired")

        print(f"🔓 [TOKEN_DEC] PGP_HOSTPAY2_v1→PGP_HOSTPAY1_v1: Token validated")

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
    # TOKEN 4: PGP_HOSTPAY1_v1 → PGP_HOSTPAY3_v1 (Payment execution request)
    # ========================================================================

    def encrypt_gchostpay1_to_gchostpay3_token(
        self,
        unique_id: str,
        cn_api_id: str,
        from_currency: str,
        from_network: str,
        from_amount: float,
        payin_address: str
    ) -> Optional[str]:
        """
        Encrypt token for PGP_HOSTPAY1_v1 → PGP_HOSTPAY3_v1 (ETH payment execution request).

        Token Structure:
        - 16 bytes: unique_id (fixed)
        - 1 byte: cn_api_id length + variable bytes
        - 1 byte: from_currency length + variable bytes
        - 1 byte: from_network length + variable bytes
        - 8 bytes: from_amount (double)
        - 1 byte: payin_address length + variable bytes
        - 4 bytes: timestamp
        - 16 bytes: HMAC signature

        Returns:
            Base64 URL-safe encoded token or None if failed
        """
        try:
            print(f"🔐 [TOKEN_ENC] PGP_HOSTPAY1_v1→PGP_HOSTPAY3_v1: Encrypting payment request")

            packed_data = bytearray()
            packed_data.extend(self.pack_string(unique_id))
            packed_data.extend(self.pack_string(cn_api_id))
            packed_data.extend(self.pack_string(from_currency.lower()))
            packed_data.extend(self.pack_string(from_network.lower()))
            packed_data.extend(struct.pack(">d", from_amount))
            packed_data.extend(self.pack_string(payin_address))

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
        Decrypt token from PGP_HOSTPAY1_v1 → PGP_HOSTPAY3_v1.
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
        unique_id, offset = self.unpack_string(raw, offset)

        # Parse cn_api_id
        cn_api_id, offset = self.unpack_string(raw, offset)

        # Parse from_currency
        from_currency, offset = self.unpack_string(raw, offset)

        # Parse from_network
        from_network, offset = self.unpack_string(raw, offset)

        # Parse from_amount
        if offset + 8 > len(raw):
            raise ValueError("Invalid token: incomplete from_amount")
        from_amount = struct.unpack(">d", raw[offset:offset+8])[0]
        offset += 8

        # Parse payin_address
        payin_address, offset = self.unpack_string(raw, offset)

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

        # Validate timestamp (300 second / 5-minute window)
        # Extended for Cloud Tasks delivery delays and retries
        current_time = int(time.time())
        if not (current_time - 300 <= timestamp <= current_time + 5):
            raise ValueError(f"Token expired")

        print(f"🔓 [TOKEN_DEC] PGP_HOSTPAY1_v1→PGP_HOSTPAY3_v1: Token validated")

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
    # TOKEN 5: PGP_HOSTPAY3_v1 → PGP_HOSTPAY1_v1 (Payment execution response)
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
        Encrypt response token for PGP_HOSTPAY3_v1 → PGP_HOSTPAY1_v1 (payment execution response).

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
            print(f"🔐 [TOKEN_ENC] PGP_HOSTPAY3_v1→PGP_HOSTPAY1_v1: Encrypting payment response")

            packed_data = bytearray()
            packed_data.extend(self.pack_string(unique_id))
            packed_data.extend(self.pack_string(cn_api_id))
            packed_data.extend(self.pack_string(tx_hash))
            packed_data.extend(self.pack_string(tx_status))
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
        Decrypt response token from PGP_HOSTPAY3_v1 → PGP_HOSTPAY1_v1.
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
        unique_id, offset = self.unpack_string(raw, offset)

        # Parse cn_api_id
        cn_api_id, offset = self.unpack_string(raw, offset)

        # Parse tx_hash
        tx_hash, offset = self.unpack_string(raw, offset)

        # Parse tx_status
        tx_status, offset = self.unpack_string(raw, offset)

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

        # Validate timestamp (300 second / 5-minute window)
        # Extended for Cloud Tasks delivery delays and retries
        current_time = int(time.time())
        if not (current_time - 300 <= timestamp <= current_time + 5):
            raise ValueError(f"Token expired")

        print(f"🔓 [TOKEN_DEC] PGP_HOSTPAY3_v1→PGP_HOSTPAY1_v1: Token validated")

        return {
            "unique_id": unique_id,
            "cn_api_id": cn_api_id,
            "tx_hash": tx_hash,
            "tx_status": tx_status,
            "gas_used": gas_used,
            "block_number": block_number,
            "timestamp": timestamp
        }
