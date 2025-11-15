#!/usr/bin/env python
"""
Token Manager for PGP_SPLIT3_v1
Handles encryption and decryption of tokens for secure inter-service communication via Cloud Tasks.
"""
from typing import Dict, Any, Optional, Tuple
from PGP_COMMON.tokens import BaseTokenManager


class TokenManager(BaseTokenManager):
    """
    Manages token encryption and decryption for PGP_SPLIT3_v1.
    Inherits common methods from BaseTokenManager.
    """

    def __init__(self, signing_key: str):
        """
        Initialize TokenManager with signing key.

        Args:
            signing_key: SECRET key for HMAC signing (SUCCESS_URL_SIGNING_KEY)
        """
        super().__init__(signing_key, service_name="PGP_SPLIT3_v1")
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
        adjusted_amount_usdt: float
    ) -> Optional[str]:
        """
        Encrypt token for GCSplit1 → GCSplit2 (USDT estimate request).

        Token Structure:
        - 8 bytes: user_id (uint64)
        - 16 bytes: closed_channel_id (fixed, padded)
        - 1 byte: wallet_address length + variable bytes
        - 1 byte: payout_currency length + variable bytes
        - 1 byte: payout_network length + variable bytes
        - 8 bytes: adjusted_amount_usdt (double)
        - 4 bytes: timestamp (uint32)
        - 16 bytes: HMAC signature (truncated)

        Returns:
            Base64 URL-safe encoded token or None if failed
        """
        try:
            print(f"🔐 [TOKEN_ENC] GCSplit1→GCSplit2: Encrypting token")

            # Fixed 16-byte closed_channel_id
            closed_channel_id_bytes = closed_channel_id.encode('utf-8')[:16].ljust(16, b'\x00')

            # Build packed data
            packed_data = bytearray()

            # user_id (8 bytes)
            packed_data.extend(struct.pack(">Q", user_id))

            # closed_channel_id (16 bytes fixed)
            packed_data.extend(closed_channel_id_bytes)

            # Variable length strings
            packed_data.extend(self.pack_string(wallet_address))
            packed_data.extend(self.pack_string(payout_currency))
            packed_data.extend(self.pack_string(payout_network))

            # adjusted_amount_usdt (8 bytes double)
            packed_data.extend(struct.pack(">d", adjusted_amount_usdt))

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
            wallet_address, offset = self.unpack_string(payload, offset)
            payout_currency, offset = self.unpack_string(payload, offset)
            payout_network, offset = self.unpack_string(payload, offset)

            # adjusted_amount_usdt (8 bytes double)
            adjusted_amount_usdt = struct.unpack(">d", payload[offset:offset + 8])[0]
            offset += 8

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
                "adjusted_amount_usdt": adjusted_amount_usdt,
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
        from_amount_usdt: float,
        to_amount_eth_post_fee: float,
        deposit_fee: float,
        withdrawal_fee: float
    ) -> Optional[str]:
        """
        Encrypt token for GCSplit2 → GCSplit1 (USDT estimate response).

        Token Structure:
        - 4 bytes: user_id
        - 16 bytes: closed_channel_id (fixed)
        - Strings: wallet_address, payout_currency, payout_network
        - 8 bytes each: from_amount, to_amount, deposit_fee, withdrawal_fee
        - 4 bytes: timestamp
        - 16 bytes: HMAC signature

        Returns:
            Base64 URL-safe encoded token or None if failed
        """
        try:
            print(f"🔐 [TOKEN_ENC] GCSplit2→GCSplit1: Encrypting estimate response")

            closed_channel_id_bytes = closed_channel_id.encode('utf-8')[:16].ljust(16, b'\x00')

            packed_data = bytearray()
            packed_data.extend(struct.pack(">Q", user_id))
            packed_data.extend(closed_channel_id_bytes)
            packed_data.extend(self.pack_string(wallet_address))
            packed_data.extend(self.pack_string(payout_currency))
            packed_data.extend(self.pack_string(payout_network))
            packed_data.extend(struct.pack(">d", from_amount_usdt))
            packed_data.extend(struct.pack(">d", to_amount_eth_post_fee))
            packed_data.extend(struct.pack(">d", deposit_fee))
            packed_data.extend(struct.pack(">d", withdrawal_fee))

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

            wallet_address, offset = self.unpack_string(payload, offset)
            payout_currency, offset = self.unpack_string(payload, offset)
            payout_network, offset = self.unpack_string(payload, offset)

            from_amount_usdt = struct.unpack(">d", payload[offset:offset + 8])[0]
            offset += 8
            to_amount_eth_post_fee = struct.unpack(">d", payload[offset:offset + 8])[0]
            offset += 8
            deposit_fee = struct.unpack(">d", payload[offset:offset + 8])[0]
            offset += 8
            withdrawal_fee = struct.unpack(">d", payload[offset:offset + 8])[0]
            offset += 8

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
                "from_amount_usdt": from_amount_usdt,
                "to_amount_eth_post_fee": to_amount_eth_post_fee,
                "deposit_fee": deposit_fee,
                "withdrawal_fee": withdrawal_fee,
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
            packed_data.extend(self.pack_string(wallet_address))
            packed_data.extend(self.pack_string(payout_currency))
            packed_data.extend(self.pack_string(payout_network))
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

            wallet_address, offset = self.unpack_string(payload, offset)
            payout_currency, offset = self.unpack_string(payload, offset)
            payout_network, offset = self.unpack_string(payload, offset)

            eth_amount = struct.unpack(">d", payload[offset:offset + 8])[0]
            offset += 8

            # ✅ NEW: swap_currency with backward compatibility
            swap_currency = 'usdt'  # Default for old tokens (this won't be used in GCSplit3)
            if offset + 1 <= len(payload) - 4:  # Check if there's room before timestamp
                try:
                    swap_currency, offset = self.unpack_string(payload, offset)
                    print(f"💱 [TOKEN_DEC] Swap currency extracted: {swap_currency}")
                except Exception:
                    print(f"⚠️ [TOKEN_DEC] No swap_currency in token (backward compat - defaulting to 'usdt')")
                    swap_currency = 'usdt'
            else:
                print(f"⚠️ [TOKEN_DEC] Old token format - no swap_currency (backward compat)")

            # ✅ NEW: payout_mode with backward compatibility
            payout_mode = 'instant'  # Default for old tokens
            if offset + 1 <= len(payload) - 4:  # Check if there's room before timestamp
                try:
                    payout_mode, offset = self.unpack_string(payload, offset)
                    print(f"🎯 [TOKEN_DEC] Payout mode extracted: {payout_mode}")
                except Exception:
                    print(f"⚠️ [TOKEN_DEC] No payout_mode in token (backward compat - defaulting to 'instant')")
                    payout_mode = 'instant'
            else:
                print(f"⚠️ [TOKEN_DEC] Old token format - no payout_mode (backward compat)")

            # ✅ Extract actual_eth_amount if available (backward compatibility)
            actual_eth_amount = 0.0
            if offset + 8 <= len(payload) - 4:  # Check if there's room for double + timestamp
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

            print(f"✅ [TOKEN_DEC] Swap request decrypted successfully")
            print(f"💰 [TOKEN_DEC] Estimated ETH: {eth_amount}")
            print(f"💰 [TOKEN_DEC] ACTUAL ETH: {actual_eth_amount}")
            print(f"💱 [TOKEN_DEC] Swap Currency: {swap_currency}, Payout Mode: {payout_mode}")

            return {
                "unique_id": unique_id,
                "user_id": user_id,
                "closed_channel_id": closed_channel_id,
                "wallet_address": wallet_address,
                "payout_currency": payout_currency,
                "payout_network": payout_network,
                "eth_amount": eth_amount,
                "swap_currency": swap_currency,  # ✅ NEW
                "payout_mode": payout_mode,  # ✅ NEW
                "actual_eth_amount": actual_eth_amount,
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
        type_: str,
        actual_eth_amount: float = 0.0  # ✅ ADD THIS
    ) -> Optional[str]:
        """
        Encrypt token for GCSplit3 → GCSplit1 (ETH→Client swap response).

        Token Structure:
        - 16 bytes: unique_id
        - 4 bytes: user_id
        - 16 bytes: closed_channel_id
        - Strings: cn_api_id, currencies, networks, addresses, flow, type
        - 8 bytes each: from_amount, to_amount
        - 8 bytes: actual_eth_amount (ACTUAL from NowPayments)
        - 4 bytes: timestamp
        - 16 bytes: HMAC signature

        Returns:
            Base64 URL-safe encoded token or None if failed
        """
        try:
            print(f"🔐 [TOKEN_ENC] GCSplit3→GCSplit1: Encrypting swap response")
            print(f"💰 [TOKEN_ENC] ACTUAL ETH: {actual_eth_amount}")  # ✅ ADD LOG

            unique_id_bytes = unique_id.encode('utf-8')[:16].ljust(16, b'\x00')
            closed_channel_id_bytes = closed_channel_id.encode('utf-8')[:16].ljust(16, b'\x00')

            packed_data = bytearray()
            packed_data.extend(unique_id_bytes)
            packed_data.extend(struct.pack(">Q", user_id))
            packed_data.extend(closed_channel_id_bytes)
            packed_data.extend(self.pack_string(cn_api_id))
            packed_data.extend(self.pack_string(from_currency))
            packed_data.extend(self.pack_string(to_currency))
            packed_data.extend(self.pack_string(from_network))
            packed_data.extend(self.pack_string(to_network))
            packed_data.extend(struct.pack(">d", from_amount))
            packed_data.extend(struct.pack(">d", to_amount))
            packed_data.extend(self.pack_string(payin_address))
            packed_data.extend(self.pack_string(payout_address))
            packed_data.extend(self.pack_string(refund_address))
            packed_data.extend(self.pack_string(flow))
            packed_data.extend(self.pack_string(type_))
            packed_data.extend(struct.pack(">d", actual_eth_amount))  # ✅ ADD ACTUAL

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

            cn_api_id, offset = self.unpack_string(payload, offset)
            from_currency, offset = self.unpack_string(payload, offset)
            to_currency, offset = self.unpack_string(payload, offset)
            from_network, offset = self.unpack_string(payload, offset)
            to_network, offset = self.unpack_string(payload, offset)

            from_amount = struct.unpack(">d", payload[offset:offset + 8])[0]
            offset += 8
            to_amount = struct.unpack(">d", payload[offset:offset + 8])[0]
            offset += 8

            payin_address, offset = self.unpack_string(payload, offset)
            payout_address, offset = self.unpack_string(payload, offset)
            refund_address, offset = self.unpack_string(payload, offset)
            flow, offset = self.unpack_string(payload, offset)
            type_, offset = self.unpack_string(payload, offset)

            # ✅ ADDED: actual_eth_amount with backward compatibility
            actual_eth_amount = 0.0
            if offset + 8 <= len(payload) - 4:  # Check if there's room for double + timestamp
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
                "actual_eth_amount": actual_eth_amount,  # ✅ NEW
                "timestamp": timestamp
            }

        except Exception as e:
            print(f"❌ [TOKEN_DEC] Decryption error: {e}")
            return None

    # ========================================================================
    # GCAccumulator ↔ GCSplit3 Token Methods (for ETH→USDT swaps)
    # ========================================================================

    def decrypt_accumulator_to_gcsplit3_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decrypt token from GCAccumulator for ETH→USDT swap creation.

        Expected fields:
        - accumulation_id (int)
        - client_id (str)
        - eth_amount (float)
        - usdt_wallet_address (str)
        - timestamp (int)
        """
        try:
            print(f"🔓 [TOKEN_DEC] GCAccumulator→GCSplit3: Decrypting ETH→USDT swap request")

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

            # Unpack accumulation_id (8 bytes, int64)
            accumulation_id = struct.unpack(">Q", payload[offset:offset + 8])[0]
            offset += 8

            # Unpack client_id (variable length string)
            client_id, offset = self.unpack_string(payload, offset)

            # Unpack eth_amount (8 bytes, double)
            eth_amount = struct.unpack(">d", payload[offset:offset + 8])[0]
            offset += 8

            # Unpack usdt_wallet_address (variable length string)
            usdt_wallet_address, offset = self.unpack_string(payload, offset)

            # Unpack timestamp (8 bytes, int64)
            timestamp = struct.unpack(">Q", payload[offset:offset + 8])[0]
            offset += 8

            # Validate timestamp (5 minutes = 300 seconds)
            current_time = int(time.time())
            if not (current_time - 300 <= timestamp <= current_time + 5):
                raise ValueError("Token expired")

            print(f"✅ [TOKEN_DEC] Accumulation ID: {accumulation_id}")
            print(f"✅ [TOKEN_DEC] Client ID: {client_id}")
            print(f"✅ [TOKEN_DEC] ETH Amount: ${eth_amount}")

            return {
                "accumulation_id": accumulation_id,
                "client_id": client_id,
                "eth_amount": eth_amount,
                "usdt_wallet_address": usdt_wallet_address,
                "timestamp": timestamp
            }

        except Exception as e:
            print(f"❌ [TOKEN_DEC] Decryption error: {e}")
            return None

    def encrypt_gcsplit3_to_accumulator_token(
        self,
        accumulation_id: int,
        client_id: str,
        cn_api_id: str,
        from_amount: float,
        to_amount: float,
        payin_address: str,
        payout_address: str
    ) -> Optional[str]:
        """
        Encrypt token for GCAccumulator with ETH→USDT swap details.

        Returns encrypted token or None if encryption fails.
        """
        try:
            print(f"🔐 [TOKEN_ENC] GCSplit3→GCAccumulator: Encrypting swap response")

            payload = bytearray()

            # Pack accumulation_id (8 bytes, int64)
            payload.extend(struct.pack(">Q", accumulation_id))

            # Pack client_id (variable length string)
            payload.extend(self.pack_string(client_id))

            # Pack cn_api_id (variable length string)
            payload.extend(self.pack_string(cn_api_id))

            # Pack from_amount (8 bytes, double)
            payload.extend(struct.pack(">d", from_amount))

            # Pack to_amount (8 bytes, double)
            payload.extend(struct.pack(">d", to_amount))

            # Pack payin_address (variable length string)
            payload.extend(self.pack_string(payin_address))

            # Pack payout_address (variable length string)
            payload.extend(self.pack_string(payout_address))

            # Pack timestamp (8 bytes, int64)
            timestamp = int(time.time())
            payload.extend(struct.pack(">Q", timestamp))

            # Generate signature
            signature = hmac.new(
                self.signing_key.encode(),
                bytes(payload),
                hashlib.sha256
            ).digest()[:16]

            # Combine payload + signature
            full_data = bytes(payload) + signature

            # Encode to base64
            token = base64.urlsafe_b64encode(full_data).decode('utf-8').rstrip('=')

            print(f"✅ [TOKEN_ENC] Token encrypted successfully")

            return token

        except Exception as e:
            print(f"❌ [TOKEN_ENC] Encryption error: {e}")
            return None
