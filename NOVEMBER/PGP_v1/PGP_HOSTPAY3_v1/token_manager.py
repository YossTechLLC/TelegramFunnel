#!/usr/bin/env python
"""
Token Manager for PGP_HOSTPAY3_v1.
Handles encryption and decryption of tokens for secure inter-service communication via Cloud Tasks.
"""
from typing import Dict, Any, Optional
from PGP_COMMON.tokens import BaseTokenManager


class TokenManager(BaseTokenManager):
    """
    Manages token encryption and decryption for PGP_HOSTPAY3_v1.
    Inherits common methods from BaseTokenManager.

    Only includes methods actually used by PGP_HOSTPAY3_v1:
    - decrypt_pgp_hostpay1_to_pgp_hostpay3_token() - Receive payment execution requests
    - encrypt_pgp_hostpay3_to_pgp_hostpay1_token() - Send payment execution responses
    - encrypt_pgp_hostpay3_retry_token() - Create retry tokens after failures
    """

    def __init__(self, signing_key: str):
        """
        Initialize TokenManager with signing key.

        Args:
            signing_key: SUCCESS_URL_SIGNING_KEY for HMAC signing
        """
        super().__init__(signing_key, service_name="PGP_HOSTPAY3_v1")

    # ========================================================================
    # TOKEN 4: PGP_HOSTPAY1_v1 → PGP_HOSTPAY3_v1 (Payment execution request)
    # ========================================================================

    def decrypt_pgp_hostpay1_to_pgp_hostpay3_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decrypt token from PGP_HOSTPAY1_v1 → PGP_HOSTPAY3_v1.
        Token valid for 7200 seconds (2 hours).

        **UPDATED**: Now includes retry tracking fields (attempt_count, first_attempt_at, last_error_code)
        with full backward compatibility for legacy tokens.

        Returns:
            Dictionary with payment details including context field or None
        """
        import base64
        import hmac
        import hashlib
        import struct
        import time

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

        # Parse context (defaults to 'instant' for backward compatibility)
        try:
            context, offset = self.unpack_string(raw, offset)
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
                        last_error_code_str, offset = self.unpack_string(raw, offset)
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

        print(f"🔓 [TOKEN_DEC] PGP_HOSTPAY1_v1→PGP_HOSTPAY3_v1: Token validated")
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
    # TOKEN 5: PGP_HOSTPAY3_v1 → PGP_HOSTPAY1_v1 (Payment execution response)
    # ========================================================================

    def encrypt_pgp_hostpay3_to_pgp_hostpay1_token(
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
        - 1 byte: unique_id length + variable bytes (length-prefixed string)
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
        import base64
        import hmac
        import hashlib
        import struct
        import time

        try:
            print(f"🔐 [TOKEN_ENC] PGP_HOSTPAY3_v1→PGP_HOSTPAY1_v1: Encrypting payment response")

            packed_data = bytearray()
            packed_data.extend(self.pack_string(unique_id))  # ✅ FIXED: Variable-length instead of 16-byte truncation
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

    # ========================================================================
    # TOKEN 6: PGP_HOSTPAY3_v1 → PGP_HOSTPAY3_v1 (Self-retry after failure) [NEW]
    # ========================================================================

    def encrypt_pgp_hostpay3_retry_token(
        self,
        token_data: Dict[str, Any],
        error_code: str
    ) -> Optional[str]:
        """
        NEW METHOD: Encrypt token for PGP_HOSTPAY3_v1 self-retry after payment failure.

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
            >>> retry_token = token_mgr.encrypt_pgp_hostpay3_retry_token(
            ...     failed_token_data,
            ...     error_code='RATE_LIMIT_EXCEEDED'
            ... )
            >>> # retry_token will have attempt_count=2, last_error_code='RATE_LIMIT_EXCEEDED'
        """
        import struct
        import time
        import base64
        import hmac
        import hashlib

        try:
            print(f"🔄 [TOKEN_RETRY] Building retry token for PGP_HOSTPAY3_v1 self-enqueue")
            print(f"🔄 [TOKEN_RETRY] Previous attempt: {token_data.get('attempt_count', 1)}")
            print(f"🔄 [TOKEN_RETRY] Error code: {error_code}")

            # Increment attempt count
            new_attempt_count = token_data.get('attempt_count', 1) + 1

            # Preserve first_attempt_at (should already exist)
            first_attempt_at = token_data.get('first_attempt_at', int(time.time()))

            # Build retry token structure (same as HOSTPAY1→HOSTPAY3 token)
            packed_data = bytearray()
            packed_data.extend(self.pack_string(token_data['unique_id']))
            packed_data.extend(self.pack_string(token_data['cn_api_id']))
            packed_data.extend(self.pack_string(token_data['from_currency'].lower()))
            packed_data.extend(self.pack_string(token_data['from_network'].lower()))
            packed_data.extend(struct.pack(">d", token_data['from_amount']))
            packed_data.extend(self.pack_string(token_data['payin_address']))
            packed_data.extend(self.pack_string(token_data.get('context', 'instant').lower()))

            # NEW: Add retry tracking fields
            packed_data.extend(struct.pack(">I", new_attempt_count))
            packed_data.extend(struct.pack(">I", first_attempt_at))
            packed_data.extend(self.pack_string(error_code if error_code else ''))

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
            retry_token = base64.urlsafe_b64encode(final_data).rstrip(b'=').decode('utf-8')

            print(f"✅ [TOKEN_RETRY] Retry token created (attempt {new_attempt_count}/3)")
            return retry_token

        except Exception as e:
            print(f"❌ [TOKEN_RETRY] Retry token encryption error: {e}")
            return None
