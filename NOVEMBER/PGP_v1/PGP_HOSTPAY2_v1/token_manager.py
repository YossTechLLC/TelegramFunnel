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
    def decrypt_pgp_hostpay1_to_pgp_hostpay2_token(self, token: str) -> Optional[Dict[str, Any]]:
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

    def encrypt_pgp_hostpay2_to_pgp_hostpay1_token(
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
