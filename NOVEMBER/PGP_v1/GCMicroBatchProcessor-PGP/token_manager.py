#!/usr/bin/env python
"""
Token Manager for GCMicroBatchProcessor-10-26 (Micro-Batch Conversion Service).
Handles token encryption/decryption for communication with GCHostPay1.
"""
import base64
import hmac
import hashlib
import struct
import time
from typing import Optional, Dict, Any, Tuple


class TokenManager:
    """
    Manages token encryption for GCMicroBatchProcessor-10-26.
    """

    def __init__(self, signing_key: str):
        """
        Initialize the TokenManager.

        Args:
            signing_key: SUCCESS_URL_SIGNING_KEY for token encryption
        """
        self.signing_key = signing_key
        print(f"🔐 [TOKEN] TokenManager initialized")

    def _pack_string(self, s: str) -> bytes:
        """Pack a string with 1-byte length prefix."""
        s_bytes = s.encode('utf-8')
        if len(s_bytes) > 255:
            raise ValueError(f"String too long (max 255 bytes): {s}")
        return bytes([len(s_bytes)]) + s_bytes

    def _unpack_string(self, data: bytes, offset: int) -> Tuple[str, int]:
        """Unpack a string with 1-byte length prefix."""
        length = data[offset]
        offset += 1
        s_bytes = data[offset:offset + length]
        offset += length
        return s_bytes.decode('utf-8'), offset

    def encrypt_microbatch_to_gchostpay1_token(
        self,
        batch_conversion_id: str,
        cn_api_id: str,
        from_currency: str,
        from_network: str,
        from_amount: float,
        payin_address: str
    ) -> Optional[str]:
        """
        Encrypt token for GCHostPay1 batch execution request.

        Returns:
            Base64 URL-safe encoded token or None if failed
        """
        try:
            payload = bytearray()

            # Pack context
            payload.extend(self._pack_string('batch'))

            # Pack batch_conversion_id (UUID as string)
            payload.extend(self._pack_string(batch_conversion_id))

            # Pack cn_api_id
            payload.extend(self._pack_string(cn_api_id))

            # Pack from_currency
            payload.extend(self._pack_string(from_currency))

            # Pack from_network
            payload.extend(self._pack_string(from_network))

            # Pack from_amount (8 bytes, double)
            payload.extend(struct.pack(">d", from_amount))

            # Pack payin_address
            payload.extend(self._pack_string(payin_address))

            # Pack timestamp (8 bytes, uint64)
            timestamp = int(time.time())
            payload.extend(struct.pack(">Q", timestamp))

            # Generate HMAC signature
            signature = hmac.new(
                self.signing_key.encode(),
                bytes(payload),
                hashlib.sha256
            ).digest()[:16]

            # Combine payload + signature
            full_data = bytes(payload) + signature

            # Base64 encode
            token = base64.urlsafe_b64encode(full_data).decode('utf-8').rstrip('=')

            return token

        except Exception as e:
            print(f"❌ [TOKEN_ENC] Encryption error: {e}")
            return None

    def decrypt_gchostpay1_to_microbatch_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decrypt token from GCHostPay1 with batch execution completion details.

        Returns:
            Dictionary with decrypted data or None if failed
        """
        try:
            # Decode base64
            padding = 4 - (len(token) % 4) if len(token) % 4 != 0 else 0
            token_padded = token + ('=' * padding)
            data = base64.urlsafe_b64decode(token_padded)

            if len(data) < 16:
                raise ValueError("Token too short")

            payload = data[:-16]
            provided_signature = data[-16:]

            # Verify signature
            expected_signature = hmac.new(
                self.signing_key.encode(),
                payload,
                hashlib.sha256
            ).digest()[:16]

            if not hmac.compare_digest(provided_signature, expected_signature):
                raise ValueError("Invalid signature")

            offset = 0

            # Unpack batch_conversion_id (variable length string)
            batch_conversion_id, offset = self._unpack_string(payload, offset)

            # Unpack cn_api_id (variable length string)
            cn_api_id, offset = self._unpack_string(payload, offset)

            # Unpack tx_hash (variable length string)
            tx_hash, offset = self._unpack_string(payload, offset)

            # Unpack actual_usdt_received (8 bytes, double)
            actual_usdt_received = struct.unpack(">d", payload[offset:offset + 8])[0]
            offset += 8

            # Unpack timestamp (8 bytes, uint64)
            timestamp = struct.unpack(">Q", payload[offset:offset + 8])[0]
            offset += 8

            # Validate timestamp (30 minutes = 1800 seconds)
            # Extended window to accommodate:
            # - ChangeNow retry delays (up to 15 minutes for 3 retries)
            # - Cloud Tasks queue delays (2-5 minutes)
            # - Safety margin (10 minutes)
            current_time = int(time.time())
            token_age_seconds = current_time - timestamp
            if not (current_time - 1800 <= timestamp <= current_time + 5):
                print(f"❌ [TOKEN_DEC] Token expired: age={token_age_seconds}s ({token_age_seconds/60:.1f}m), max=1800s (30m)")
                raise ValueError("Token expired")

            print(f"✅ [TOKEN_DEC] Token age: {token_age_seconds}s ({token_age_seconds/60:.1f}m) - within 30-minute window")

            return {
                "batch_conversion_id": batch_conversion_id,
                "cn_api_id": cn_api_id,
                "tx_hash": tx_hash,
                "actual_usdt_received": actual_usdt_received,
                "timestamp": timestamp
            }

        except Exception as e:
            print(f"❌ [TOKEN_DEC] Decryption error: {e}")
            return None
