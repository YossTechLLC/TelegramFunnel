#!/usr/bin/env python
"""
Token Manager for GCSplit Services (GCSplit1, GCSplit2, GCSplit3)
Handles encryption and decryption of tokens for secure inter-service communication via Cloud Tasks.
"""
import hmac
import hashlib
import struct
import base64
import time
from typing import Dict, Any, Optional, Tuple


class TokenManager:
    """
    Manages token encryption and decryption for GCSplit services.
    Uses binary packing and HMAC-SHA256 signatures for security.
    """

    def __init__(self, signing_key: str):
        """
        Initialize TokenManager with signing key.

        Args:
            signing_key: SECRET key for HMAC signing (SUCCESS_URL_SIGNING_KEY)
        """
        if not signing_key:
            raise ValueError("Signing key cannot be empty")

        self.signing_key = signing_key
        print(f"🔐 [TOKEN_MANAGER] Initialized with signing key")

    def _pack_string(self, s: str) -> bytes:
        """
        Pack a string with 1-byte length prefix.

        Args:
            s: String to pack

        Returns:
            Packed bytes (1 byte length + UTF-8 encoded string)
        """
        s_bytes = s.encode('utf-8')
        if len(s_bytes) > 255:
            raise ValueError(f"String too long (max 255 bytes): {s}")
        return bytes([len(s_bytes)]) + s_bytes

    def _unpack_string(self, data: bytes, offset: int) -> Tuple[str, int]:
        """
        Unpack a string with 1-byte length prefix.

        Args:
            data: Byte array to unpack from
            offset: Starting offset

        Returns:
            Tuple of (unpacked_string, new_offset)
        """
        length = data[offset]
        offset += 1
        s_bytes = data[offset:offset + length]
        offset += length
        return s_bytes.decode('utf-8'), offset

    def encrypt_gcsplit1_to_gcsplit2_token(
        self,
        user_id: int,
        closed_channel_id: str,
        wallet_address: str,
        payout_currency: str,
        payout_network: str,
        adjusted_amount: float,  # ✅ RENAMED: Now accepts ETH or USDT
        swap_currency: str = 'usdt',  # ✅ NEW: 'eth' or 'usdt'
        payout_mode: str = 'instant',  # ✅ NEW: 'instant' or 'threshold'
        actual_eth_amount: float = 0.0  # ✅ ADDED: Pass through actual ETH
    ) -> Optional[str]:
        """
        Encrypt token for GCSplit1 → GCSplit2 (estimate request).

        Token Structure:
        - 8 bytes: user_id (uint64)
        - 16 bytes: closed_channel_id (fixed, padded)
        - 1 byte: wallet_address length + variable bytes
        - 1 byte: payout_currency length + variable bytes
        - 1 byte: payout_network length + variable bytes
        - 8 bytes: adjusted_amount (double) - ETH or USDT based on swap_currency
        - 1 byte: swap_currency length + variable bytes [✅ NEW]
        - 1 byte: payout_mode length + variable bytes [✅ NEW]
        - 8 bytes: actual_eth_amount (double) [✅ NEW]
        - 4 bytes: timestamp (uint32)
        - 16 bytes: HMAC signature (truncated)

        Returns:
            Base64 URL-safe encoded token or None if failed
        """
        try:
            print(f"🔐 [TOKEN_ENC] GCSplit1→GCSplit2: Encrypting token")
            print(f"💱 [TOKEN_ENC] Swap Currency: {swap_currency}, Payout Mode: {payout_mode}")

            # Fixed 16-byte closed_channel_id
            closed_channel_id_bytes = closed_channel_id.encode('utf-8')[:16].ljust(16, b'\x00')

            # Build packed data
            packed_data = bytearray()

            # user_id (8 bytes)
            packed_data.extend(struct.pack(">Q", user_id))

            # closed_channel_id (16 bytes fixed)
            packed_data.extend(closed_channel_id_bytes)

            # Variable length strings
            packed_data.extend(self._pack_string(wallet_address))
            packed_data.extend(self._pack_string(payout_currency))
            packed_data.extend(self._pack_string(payout_network))

            # adjusted_amount (8 bytes double)
            packed_data.extend(struct.pack(">d", adjusted_amount))

            # ✅ NEW: swap_currency, payout_mode, actual_eth_amount
            packed_data.extend(self._pack_string(swap_currency))
            packed_data.extend(self._pack_string(payout_mode))
            packed_data.extend(struct.pack(">d", actual_eth_amount))

            # timestamp (4 bytes)
            current_timestamp = int(time.time())
            packed_data.extend(struct.pack(">I", current_timestamp))

            # HMAC signature
            full_signature = hmac.new(
                self.signing_key.encode(),
                bytes(packed_data),
                hashlib.sha256
            ).digest()
            truncated_signature = full_signature[:16]

            # Final token
            final_data = bytes(packed_data) + truncated_signature
            token = base64.urlsafe_b64encode(final_data).rstrip(b'=').decode('utf-8')

            print(f"✅ [TOKEN_ENC] Token encrypted successfully ({len(token)} chars)")
            return token

        except Exception as e:
            print(f"❌ [TOKEN_ENC] Encryption error: {e}")
            return None

    def decrypt_gcsplit1_to_gcsplit2_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decrypt token from GCSplit1 → GCSplit2.

        Returns:
            Dictionary with decrypted fields or None if failed
        """
        try:
            print(f"🔓 [TOKEN_DEC] GCSplit1→GCSplit2: Decrypting token")

            # Decode base64
            padding = 4 - (len(token) % 4) if len(token) % 4 != 0 else 0
            token_padded = token + ('=' * padding)
            data = base64.urlsafe_b64decode(token_padded)

            # Split signature
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

            # Unpack payload
            offset = 0

            # user_id (8 bytes)
            user_id = struct.unpack(">Q", payload[offset:offset + 8])[0]
            offset += 8

            # closed_channel_id (16 bytes fixed)
            closed_channel_id_bytes = payload[offset:offset + 16]
            closed_channel_id = closed_channel_id_bytes.rstrip(b'\x00').decode('utf-8')
            offset += 16

            # Variable strings
            wallet_address, offset = self._unpack_string(payload, offset)
            payout_currency, offset = self._unpack_string(payload, offset)
            payout_network, offset = self._unpack_string(payload, offset)

            # adjusted_amount (8 bytes double)
            adjusted_amount = struct.unpack(">d", payload[offset:offset + 8])[0]
            offset += 8

            # ✅ NEW: swap_currency with backward compatibility
            swap_currency = 'usdt'  # Default for old tokens
            if offset + 1 <= len(payload):
                try:
                    swap_currency, offset = self._unpack_string(payload, offset)
                    print(f"💱 [TOKEN_DEC] Swap currency extracted: {swap_currency}")
                except Exception:
                    print(f"⚠️ [TOKEN_DEC] No swap_currency in token (backward compat - defaulting to 'usdt')")
                    swap_currency = 'usdt'
            else:
                print(f"⚠️ [TOKEN_DEC] Old token format - no swap_currency (backward compat)")

            # ✅ NEW: payout_mode with backward compatibility
            payout_mode = 'instant'  # Default for old tokens
            if offset + 1 <= len(payload):
                try:
                    payout_mode, offset = self._unpack_string(payload, offset)
                    print(f"🎯 [TOKEN_DEC] Payout mode extracted: {payout_mode}")
                except Exception:
                    print(f"⚠️ [TOKEN_DEC] No payout_mode in token (backward compat - defaulting to 'instant')")
                    payout_mode = 'instant'
            else:
                print(f"⚠️ [TOKEN_DEC] Old token format - no payout_mode (backward compat)")

            # ✅ ADDED: actual_eth_amount (8 bytes double) with backward compatibility
            actual_eth_amount = 0.0
            if offset + 8 <= len(payload):
                try:
                    actual_eth_amount = struct.unpack(">d", payload[offset:offset + 8])[0]
                    offset += 8
                    print(f"💰 [TOKEN_DEC] ACTUAL ETH extracted: {actual_eth_amount}")
                except Exception:
                    print(f"⚠️ [TOKEN_DEC] No actual_eth_amount in token (backward compat)")
                    actual_eth_amount = 0.0
            else:
                print(f"⚠️ [TOKEN_DEC] Old token format - no actual_eth_amount (backward compat)")

            # timestamp (4 bytes)
            timestamp = struct.unpack(">I", payload[offset:offset + 4])[0]
            offset += 4

            # Validate timestamp (24 hour window)
            now = int(time.time())
            if not (now - 86400 <= timestamp <= now + 300):
                raise ValueError(f"Token expired or invalid timestamp")

            print(f"✅ [TOKEN_DEC] Token decrypted successfully")

            return {
                "user_id": user_id,
                "closed_channel_id": closed_channel_id,
                "wallet_address": wallet_address,
                "payout_currency": payout_currency,
                "payout_network": payout_network,
                "adjusted_amount": adjusted_amount,  # ✅ RENAMED
                "swap_currency": swap_currency,  # ✅ NEW
                "payout_mode": payout_mode,  # ✅ NEW
                "actual_eth_amount": actual_eth_amount,  # ✅ ADDED
                "timestamp": timestamp
            }

        except Exception as e:
            print(f"❌ [TOKEN_DEC] Decryption error: {e}")
            return None

    def encrypt_gcsplit2_to_gcsplit1_token(
        self,
        user_id: int,
        closed_channel_id: str,
        wallet_address: str,
        payout_currency: str,
        payout_network: str,
        from_amount: float,  # ✅ RENAMED: ETH or USDT based on swap_currency
        to_amount_eth_post_fee: float,
        deposit_fee: float,
        withdrawal_fee: float,
        swap_currency: str,  # ✅ NEW: 'eth' or 'usdt'
        payout_mode: str,  # ✅ NEW: 'instant' or 'threshold'
        actual_eth_amount: float = 0.0  # ✅ ADDED: Pass through actual ETH
    ) -> Optional[str]:
        """
        Encrypt token for GCSplit2 → GCSplit1 (estimate response).

        Token Structure:
        - 8 bytes: user_id
        - 16 bytes: closed_channel_id (fixed)
        - Strings: wallet_address, payout_currency, payout_network
        - 8 bytes each: from_amount, to_amount, deposit_fee, withdrawal_fee
        - 1 byte: swap_currency length + variable bytes [✅ NEW]
        - 1 byte: payout_mode length + variable bytes [✅ NEW]
        - 8 bytes: actual_eth_amount [✅ ADDED]
        - 4 bytes: timestamp
        - 16 bytes: HMAC signature

        Returns:
            Base64 URL-safe encoded token or None if failed
        """
        try:
            print(f"🔐 [TOKEN_ENC] GCSplit2→GCSplit1: Encrypting estimate response")
            print(f"💱 [TOKEN_ENC] Swap Currency: {swap_currency}, Payout Mode: {payout_mode}")

            closed_channel_id_bytes = closed_channel_id.encode('utf-8')[:16].ljust(16, b'\x00')

            packed_data = bytearray()
            packed_data.extend(struct.pack(">Q", user_id))
            packed_data.extend(closed_channel_id_bytes)
            packed_data.extend(self._pack_string(wallet_address))
            packed_data.extend(self._pack_string(payout_currency))
            packed_data.extend(self._pack_string(payout_network))
            packed_data.extend(struct.pack(">d", from_amount))
            packed_data.extend(struct.pack(">d", to_amount_eth_post_fee))
            packed_data.extend(struct.pack(">d", deposit_fee))
            packed_data.extend(struct.pack(">d", withdrawal_fee))

            # ✅ NEW: swap_currency, payout_mode
            packed_data.extend(self._pack_string(swap_currency))
            packed_data.extend(self._pack_string(payout_mode))
            packed_data.extend(struct.pack(">d", actual_eth_amount))  # ✅ ADDED: Pass through

            current_timestamp = int(time.time())
            packed_data.extend(struct.pack(">I", current_timestamp))

            full_signature = hmac.new(
                self.signing_key.encode(),
                bytes(packed_data),
                hashlib.sha256
            ).digest()
            truncated_signature = full_signature[:16]

            final_data = bytes(packed_data) + truncated_signature
            token = base64.urlsafe_b64encode(final_data).rstrip(b'=').decode('utf-8')

            print(f"✅ [TOKEN_ENC] Response token encrypted successfully ({len(token)} chars)")
            return token

        except Exception as e:
            print(f"❌ [TOKEN_ENC] Encryption error: {e}")
            return None

    def decrypt_gcsplit2_to_gcsplit1_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Decrypt token from GCSplit2 → GCSplit1."""
        try:
            print(f"🔓 [TOKEN_DEC] GCSplit2→GCSplit1: Decrypting estimate response")

            padding = 4 - (len(token) % 4) if len(token) % 4 != 0 else 0
            token_padded = token + ('=' * padding)
            data = base64.urlsafe_b64decode(token_padded)

            if len(data) < 16:
                raise ValueError("Token too short")

            payload = data[:-16]
            provided_signature = data[-16:]

            expected_signature = hmac.new(
                self.signing_key.encode(),
                payload,
                hashlib.sha256
            ).digest()[:16]

            if not hmac.compare_digest(provided_signature, expected_signature):
                raise ValueError("Invalid signature")

            offset = 0
            user_id = struct.unpack(">Q", payload[offset:offset + 8])[0]
            offset += 8

            closed_channel_id_bytes = payload[offset:offset + 16]
            closed_channel_id = closed_channel_id_bytes.rstrip(b'\x00').decode('utf-8')
            offset += 16

            wallet_address, offset = self._unpack_string(payload, offset)
            payout_currency, offset = self._unpack_string(payload, offset)
            payout_network, offset = self._unpack_string(payload, offset)

            from_amount = struct.unpack(">d", payload[offset:offset + 8])[0]
            offset += 8
            to_amount_eth_post_fee = struct.unpack(">d", payload[offset:offset + 8])[0]
            offset += 8
            deposit_fee = struct.unpack(">d", payload[offset:offset + 8])[0]
            offset += 8
            withdrawal_fee = struct.unpack(">d", payload[offset:offset + 8])[0]
            offset += 8

            # ✅ NEW: swap_currency with backward compatibility
            swap_currency = 'usdt'  # Default for old tokens
            if offset + 1 <= len(payload):
                try:
                    swap_currency, offset = self._unpack_string(payload, offset)
                    print(f"💱 [TOKEN_DEC] Swap currency extracted: {swap_currency}")
                except Exception:
                    print(f"⚠️ [TOKEN_DEC] No swap_currency in token (backward compat - defaulting to 'usdt')")
                    swap_currency = 'usdt'
            else:
                print(f"⚠️ [TOKEN_DEC] Old token format - no swap_currency (backward compat)")

            # ✅ NEW: payout_mode with backward compatibility
            payout_mode = 'instant'  # Default for old tokens
            if offset + 1 <= len(payload):
                try:
                    payout_mode, offset = self._unpack_string(payload, offset)
                    print(f"🎯 [TOKEN_DEC] Payout mode extracted: {payout_mode}")
                except Exception:
                    print(f"⚠️ [TOKEN_DEC] No payout_mode in token (backward compat - defaulting to 'instant')")
                    payout_mode = 'instant'
            else:
                print(f"⚠️ [TOKEN_DEC] Old token format - no payout_mode (backward compat)")

            # ✅ ADDED: actual_eth_amount with backward compatibility
            actual_eth_amount = 0.0
            if offset + 8 <= len(payload):
                try:
                    actual_eth_amount = struct.unpack(">d", payload[offset:offset + 8])[0]
                    offset += 8
                    print(f"💰 [TOKEN_DEC] ACTUAL ETH extracted: {actual_eth_amount}")
                except Exception:
                    print(f"⚠️ [TOKEN_DEC] No actual_eth_amount in token (backward compat)")
                    actual_eth_amount = 0.0
            else:
                print(f"⚠️ [TOKEN_DEC] Old token format - no actual_eth_amount (backward compat)")

            timestamp = struct.unpack(">I", payload[offset:offset + 4])[0]
            offset += 4

            now = int(time.time())
            if not (now - 86400 <= timestamp <= now + 300):
                raise ValueError("Token expired")

            print(f"✅ [TOKEN_DEC] Estimate response decrypted successfully")

            return {
                "user_id": user_id,
                "closed_channel_id": closed_channel_id,
                "wallet_address": wallet_address,
                "payout_currency": payout_currency,
                "payout_network": payout_network,
                "from_amount": from_amount,  # ✅ RENAMED
                "swap_currency": swap_currency,  # ✅ NEW
                "payout_mode": payout_mode,  # ✅ NEW
                "to_amount_eth_post_fee": to_amount_eth_post_fee,
                "deposit_fee": deposit_fee,
                "withdrawal_fee": withdrawal_fee,
                "actual_eth_amount": actual_eth_amount,  # ✅ NEW
                "timestamp": timestamp
            }

        except Exception as e:
            print(f"❌ [TOKEN_DEC] Decryption error: {e}")
            return None

    def encrypt_gcsplit1_to_gcsplit3_token(
        self,
        unique_id: str,
        user_id: int,
        closed_channel_id: str,
        wallet_address: str,
        payout_currency: str,
        payout_network: str,
        eth_amount: float
    ) -> Optional[str]:
        """
        Encrypt token for GCSplit1 → GCSplit3 (ETH→Client swap request).

        Token Structure:
        - 16 bytes: unique_id (fixed)
        - 4 bytes: user_id
        - 16 bytes: closed_channel_id (fixed)
        - Strings: wallet_address, payout_currency, payout_network
        - 8 bytes: eth_amount
        - 4 bytes: timestamp
        - 16 bytes: HMAC signature

        Returns:
            Base64 URL-safe encoded token or None if failed
        """
        try:
            print(f"🔐 [TOKEN_ENC] GCSplit1→GCSplit3: Encrypting swap request")

            unique_id_bytes = unique_id.encode('utf-8')[:16].ljust(16, b'\x00')
            closed_channel_id_bytes = closed_channel_id.encode('utf-8')[:16].ljust(16, b'\x00')

            packed_data = bytearray()
            packed_data.extend(unique_id_bytes)
            packed_data.extend(struct.pack(">Q", user_id))
            packed_data.extend(closed_channel_id_bytes)
            packed_data.extend(self._pack_string(wallet_address))
            packed_data.extend(self._pack_string(payout_currency))
            packed_data.extend(self._pack_string(payout_network))
            packed_data.extend(struct.pack(">d", eth_amount))

            current_timestamp = int(time.time())
            packed_data.extend(struct.pack(">I", current_timestamp))

            full_signature = hmac.new(
                self.signing_key.encode(),
                bytes(packed_data),
                hashlib.sha256
            ).digest()
            truncated_signature = full_signature[:16]

            final_data = bytes(packed_data) + truncated_signature
            token = base64.urlsafe_b64encode(final_data).rstrip(b'=').decode('utf-8')

            print(f"✅ [TOKEN_ENC] Swap request token encrypted successfully ({len(token)} chars)")
            return token

        except Exception as e:
            print(f"❌ [TOKEN_ENC] Encryption error: {e}")
            return None

    def decrypt_gcsplit1_to_gcsplit3_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Decrypt token from GCSplit1 → GCSplit3."""
        try:
            print(f"🔓 [TOKEN_DEC] GCSplit1→GCSplit3: Decrypting swap request")

            padding = 4 - (len(token) % 4) if len(token) % 4 != 0 else 0
            token_padded = token + ('=' * padding)
            data = base64.urlsafe_b64decode(token_padded)

            if len(data) < 16:
                raise ValueError("Token too short")

            payload = data[:-16]
            provided_signature = data[-16:]

            expected_signature = hmac.new(
                self.signing_key.encode(),
                payload,
                hashlib.sha256
            ).digest()[:16]

            if not hmac.compare_digest(provided_signature, expected_signature):
                raise ValueError("Invalid signature")

            offset = 0

            unique_id_bytes = payload[offset:offset + 16]
            unique_id = unique_id_bytes.rstrip(b'\x00').decode('utf-8')
            offset += 16

            user_id = struct.unpack(">Q", payload[offset:offset + 8])[0]
            offset += 8

            closed_channel_id_bytes = payload[offset:offset + 16]
            closed_channel_id = closed_channel_id_bytes.rstrip(b'\x00').decode('utf-8')
            offset += 16

            wallet_address, offset = self._unpack_string(payload, offset)
            payout_currency, offset = self._unpack_string(payload, offset)
            payout_network, offset = self._unpack_string(payload, offset)

            eth_amount = struct.unpack(">d", payload[offset:offset + 8])[0]
            offset += 8

            timestamp = struct.unpack(">I", payload[offset:offset + 4])[0]
            offset += 4

            now = int(time.time())
            if not (now - 86400 <= timestamp <= now + 300):
                raise ValueError("Token expired")

            print(f"✅ [TOKEN_DEC] Swap request decrypted successfully")

            return {
                "unique_id": unique_id,
                "user_id": user_id,
                "closed_channel_id": closed_channel_id,
                "wallet_address": wallet_address,
                "payout_currency": payout_currency,
                "payout_network": payout_network,
                "eth_amount": eth_amount,
                "timestamp": timestamp
            }

        except Exception as e:
            print(f"❌ [TOKEN_DEC] Decryption error: {e}")
            return None

    def encrypt_gcsplit3_to_gcsplit1_token(
        self,
        unique_id: str,
        user_id: int,
        closed_channel_id: str,
        cn_api_id: str,
        from_currency: str,
        to_currency: str,
        from_network: str,
        to_network: str,
        from_amount: float,
        to_amount: float,
        payin_address: str,
        payout_address: str,
        refund_address: str,
        flow: str,
        type_: str
    ) -> Optional[str]:
        """
        Encrypt token for GCSplit3 → GCSplit1 (ETH→Client swap response).

        Token Structure:
        - 16 bytes: unique_id
        - 4 bytes: user_id
        - 16 bytes: closed_channel_id
        - Strings: cn_api_id, currencies, networks, addresses, flow, type
        - 8 bytes each: from_amount, to_amount
        - 4 bytes: timestamp
        - 16 bytes: HMAC signature

        Returns:
            Base64 URL-safe encoded token or None if failed
        """
        try:
            print(f"🔐 [TOKEN_ENC] GCSplit3→GCSplit1: Encrypting swap response")

            unique_id_bytes = unique_id.encode('utf-8')[:16].ljust(16, b'\x00')
            closed_channel_id_bytes = closed_channel_id.encode('utf-8')[:16].ljust(16, b'\x00')

            packed_data = bytearray()
            packed_data.extend(unique_id_bytes)
            packed_data.extend(struct.pack(">Q", user_id))
            packed_data.extend(closed_channel_id_bytes)
            packed_data.extend(self._pack_string(cn_api_id))
            packed_data.extend(self._pack_string(from_currency))
            packed_data.extend(self._pack_string(to_currency))
            packed_data.extend(self._pack_string(from_network))
            packed_data.extend(self._pack_string(to_network))
            packed_data.extend(struct.pack(">d", from_amount))
            packed_data.extend(struct.pack(">d", to_amount))
            packed_data.extend(self._pack_string(payin_address))
            packed_data.extend(self._pack_string(payout_address))
            packed_data.extend(self._pack_string(refund_address))
            packed_data.extend(self._pack_string(flow))
            packed_data.extend(self._pack_string(type_))

            current_timestamp = int(time.time())
            packed_data.extend(struct.pack(">I", current_timestamp))

            full_signature = hmac.new(
                self.signing_key.encode(),
                bytes(packed_data),
                hashlib.sha256
            ).digest()
            truncated_signature = full_signature[:16]

            final_data = bytes(packed_data) + truncated_signature
            token = base64.urlsafe_b64encode(final_data).rstrip(b'=').decode('utf-8')

            print(f"✅ [TOKEN_ENC] Swap response token encrypted successfully ({len(token)} chars)")
            return token

        except Exception as e:
            print(f"❌ [TOKEN_ENC] Encryption error: {e}")
            return None

    def decrypt_gcsplit3_to_gcsplit1_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Decrypt token from GCSplit3 → GCSplit1."""
        try:
            print(f"🔓 [TOKEN_DEC] GCSplit3→GCSplit1: Decrypting swap response")

            padding = 4 - (len(token) % 4) if len(token) % 4 != 0 else 0
            token_padded = token + ('=' * padding)
            data = base64.urlsafe_b64decode(token_padded)

            if len(data) < 16:
                raise ValueError("Token too short")

            payload = data[:-16]
            provided_signature = data[-16:]

            expected_signature = hmac.new(
                self.signing_key.encode(),
                payload,
                hashlib.sha256
            ).digest()[:16]

            if not hmac.compare_digest(provided_signature, expected_signature):
                raise ValueError("Invalid signature")

            offset = 0

            unique_id_bytes = payload[offset:offset + 16]
            unique_id = unique_id_bytes.rstrip(b'\x00').decode('utf-8')
            offset += 16

            user_id = struct.unpack(">Q", payload[offset:offset + 8])[0]
            offset += 8

            closed_channel_id_bytes = payload[offset:offset + 16]
            closed_channel_id = closed_channel_id_bytes.rstrip(b'\x00').decode('utf-8')
            offset += 16

            cn_api_id, offset = self._unpack_string(payload, offset)
            from_currency, offset = self._unpack_string(payload, offset)
            to_currency, offset = self._unpack_string(payload, offset)
            from_network, offset = self._unpack_string(payload, offset)
            to_network, offset = self._unpack_string(payload, offset)

            from_amount = struct.unpack(">d", payload[offset:offset + 8])[0]
            offset += 8
            to_amount = struct.unpack(">d", payload[offset:offset + 8])[0]
            offset += 8

            payin_address, offset = self._unpack_string(payload, offset)
            payout_address, offset = self._unpack_string(payload, offset)
            refund_address, offset = self._unpack_string(payload, offset)
            flow, offset = self._unpack_string(payload, offset)
            type_, offset = self._unpack_string(payload, offset)

            timestamp = struct.unpack(">I", payload[offset:offset + 4])[0]
            offset += 4

            now = int(time.time())
            if not (now - 86400 <= timestamp <= now + 300):
                raise ValueError("Token expired")

            print(f"✅ [TOKEN_DEC] Swap response decrypted successfully")

            return {
                "unique_id": unique_id,
                "user_id": user_id,
                "closed_channel_id": closed_channel_id,
                "cn_api_id": cn_api_id,
                "from_currency": from_currency,
                "to_currency": to_currency,
                "from_network": from_network,
                "to_network": to_network,
                "from_amount": from_amount,
                "to_amount": to_amount,
                "payin_address": payin_address,
                "payout_address": payout_address,
                "refund_address": refund_address,
                "flow": flow,
                "type": type_,
                "timestamp": timestamp
            }

        except Exception as e:
            print(f"❌ [TOKEN_DEC] Decryption error: {e}")
            return None
