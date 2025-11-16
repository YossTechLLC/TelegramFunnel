#!/usr/bin/env python
"""
Token Manager for PGP_ACCUMULATOR_v1 (Payment Accumulation Service).
Handles token encryption/decryption for communication with PGP Split and HostPay services.
"""
import base64
import hmac
import hashlib
import struct
import time
from typing import Optional, Dict, Any, Tuple
from PGP_COMMON.tokens import BaseTokenManager


class TokenManager(BaseTokenManager):
    """
    Manages token encryption for PGP_ACCUMULATOR_v1.
    Inherits common methods from BaseTokenManager.
    """

    def __init__(self, signing_key: str):
        """
        Initialize the TokenManager.

        Args:
            signing_key: SUCCESS_URL_SIGNING_KEY for token encryption
        """
        super().__init__(signing_key=signing_key, service_name="PGP_ACCUMULATOR_v1")


    def encrypt_token_for_pgp_split2(
        self,
        user_id: int,
        client_id: str,
        wallet_address: str,
        payout_currency: str,
        payout_network: str,
        adjusted_amount_usd: float
    ) -> Optional[str]:
        """
        Encrypt token for PGP_SPLIT2_v1 USDT conversion request.

        Args:
            user_id: Telegram user ID
            client_id: Client's open_channel_id
            wallet_address: Client's payout wallet address
            payout_currency: Target currency (e.g., XMR)
            payout_network: Payout network
            adjusted_amount_usd: USD amount after TP fee deduction

        Returns:
            Encrypted token string or None if failed
        """
        try:
            print(f"🔐 [TOKEN] Encrypting token for PGP_SPLIT2_v1")
            print(f"👤 [TOKEN] User ID: {user_id}, Client ID: {client_id}")
            print(f"💰 [TOKEN] Amount: ${adjusted_amount_usd}")

            # Create payload
            payload = {
                'user_id': user_id,
                'client_id': client_id,
                'wallet_address': wallet_address,
                'payout_currency': payout_currency,
                'payout_network': payout_network,
                'amount_usd': adjusted_amount_usd
            }

            # Convert to JSON bytes
            payload_bytes = json.dumps(payload).encode('utf-8')

            # Generate HMAC signature
            signature = hmac.new(
                self.signing_key.encode(),
                payload_bytes,
                hashlib.sha256
            ).digest()

            # Combine payload + signature
            token_bytes = payload_bytes + signature[:16]  # Use truncated signature

            # Base64 encode
            token = base64.urlsafe_b64encode(token_bytes).decode('utf-8').rstrip('=')

            print(f"✅ [TOKEN] Token encrypted successfully")

            return token

        except Exception as e:
            print(f"❌ [TOKEN] Error encrypting token: {e}")
            return None

    # ========================================================================
    # Helper Methods for Binary Packing/Unpacking
    # ========================================================================

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

    # ========================================================================
    # PGP_ACCUMULATOR → PGP_SPLIT3_v1 Token Methods (for ETH→USDT swap creation)
    # ========================================================================

    def encrypt_accumulator_to_pgp_split3_token(
        self,
        accumulation_id: int,
        client_id: str,
        eth_amount: float,
        usdt_wallet_address: str
    ) -> Optional[str]:
        """
        Encrypt token for PGP_SPLIT3_v1 ETH→USDT swap creation request.

        Token Structure:
        - 8 bytes: accumulation_id (uint64)
        - 1 byte: client_id length + variable bytes
        - 8 bytes: eth_amount (double)
        - 1 byte: usdt_wallet_address length + variable bytes
        - 8 bytes: timestamp (uint64)
        - 16 bytes: HMAC signature (truncated)

        Returns:
            Base64 URL-safe encoded token or None if failed
        """
        try:
            print(f"🔐 [TOKEN_ENC] PGP_ACCUMULATOR→PGP_SPLIT3_v1: Encrypting ETH→USDT swap request")

            payload = bytearray()

            # Pack accumulation_id (8 bytes, uint64)
            payload.extend(struct.pack(">Q", accumulation_id))

            # Pack client_id (variable length string)
            payload.extend(self.pack_string(client_id))

            # Pack eth_amount (8 bytes, double)
            payload.extend(struct.pack(">d", eth_amount))

            # Pack usdt_wallet_address (variable length string)
            payload.extend(self.pack_string(usdt_wallet_address))

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

            print(f"✅ [TOKEN_ENC] Token encrypted successfully")
            print(f"🆔 [TOKEN_ENC] Accumulation ID: {accumulation_id}")
            print(f"💰 [TOKEN_ENC] ETH Amount: ${eth_amount}")

            return token

        except Exception as e:
            print(f"❌ [TOKEN_ENC] Encryption error: {e}")
            return None

    def decrypt_pgp_split3_to_accumulator_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decrypt token from PGP_SPLIT3_v1 with ETH→USDT swap details.

        Expected fields:
        - accumulation_id (int)
        - client_id (str)
        - cn_api_id (str)
        - from_amount (float)
        - to_amount (float)
        - payin_address (str)
        - payout_address (str)
        - timestamp (int)

        Returns:
            Dictionary with decrypted data or None if failed
        """
        try:
            print(f"🔓 [TOKEN_DEC] PGP_SPLIT3_v1→PGP_ACCUMULATOR: Decrypting swap response")

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

            # Unpack accumulation_id (8 bytes, uint64)
            accumulation_id = struct.unpack(">Q", payload[offset:offset + 8])[0]
            offset += 8

            # Unpack client_id (variable length string)
            client_id, offset = self.unpack_string(payload, offset)

            # Unpack cn_api_id (variable length string)
            cn_api_id, offset = self.unpack_string(payload, offset)

            # Unpack from_amount (8 bytes, double)
            from_amount = struct.unpack(">d", payload[offset:offset + 8])[0]
            offset += 8

            # Unpack to_amount (8 bytes, double)
            to_amount = struct.unpack(">d", payload[offset:offset + 8])[0]
            offset += 8

            # Unpack payin_address (variable length string)
            payin_address, offset = self.unpack_string(payload, offset)

            # Unpack payout_address (variable length string)
            payout_address, offset = self.unpack_string(payload, offset)

            # Unpack timestamp (8 bytes, uint64)
            timestamp = struct.unpack(">Q", payload[offset:offset + 8])[0]
            offset += 8

            # Validate timestamp (5 minutes = 300 seconds)
            current_time = int(time.time())
            if not (current_time - 300 <= timestamp <= current_time + 5):
                raise ValueError("Token expired")

            print(f"✅ [TOKEN_DEC] Accumulation ID: {accumulation_id}")
            print(f"✅ [TOKEN_DEC] CN API ID: {cn_api_id}")
            print(f"✅ [TOKEN_DEC] From: ${from_amount} ETH")
            print(f"✅ [TOKEN_DEC] To: ${to_amount} USDT")

            return {
                "accumulation_id": accumulation_id,
                "client_id": client_id,
                "cn_api_id": cn_api_id,
                "from_amount": from_amount,
                "to_amount": to_amount,
                "payin_address": payin_address,
                "payout_address": payout_address,
                "timestamp": timestamp
            }

        except Exception as e:
            print(f"❌ [TOKEN_DEC] Decryption error: {e}")
            return None

    # ========================================================================
    # PGP_ACCUMULATOR → PGP_HOSTPAY1_v1 Token Methods (for swap execution)
    # ========================================================================

    def encrypt_accumulator_to_pgp_hostpay1_token(
        self,
        accumulation_id: int,
        cn_api_id: str,
        from_currency: str,
        from_network: str,
        from_amount: float,
        payin_address: str,
        context: str = 'threshold'
    ) -> Optional[str]:
        """
        Encrypt token for PGP_HOSTPAY1_v1 swap execution request.

        Token Structure:
        - 8 bytes: accumulation_id (uint64)
        - 1 byte: cn_api_id length + variable bytes
        - 1 byte: from_currency length + variable bytes
        - 1 byte: from_network length + variable bytes
        - 8 bytes: from_amount (double)
        - 1 byte: payin_address length + variable bytes
        - 1 byte: context length + variable bytes (NEW: 'threshold' for accumulator payouts)
        - 8 bytes: timestamp (uint64)
        - 16 bytes: HMAC signature (truncated)

        Args:
            context: Payment context - always 'threshold' for accumulator payouts

        Returns:
            Base64 URL-safe encoded token or None if failed
        """
        try:
            print(f"🔐 [TOKEN_ENC] PGP_ACCUMULATOR→PGP_HOSTPAY1_v1: Encrypting execution request")
            print(f"📋 [TOKEN_ENC] Context: {context}")

            payload = bytearray()

            # Pack accumulation_id (8 bytes, uint64)
            payload.extend(struct.pack(">Q", accumulation_id))

            # Pack cn_api_id (variable length string)
            payload.extend(self.pack_string(cn_api_id))

            # Pack from_currency (variable length string)
            payload.extend(self.pack_string(from_currency))

            # Pack from_network (variable length string)
            payload.extend(self.pack_string(from_network))

            # Pack from_amount (8 bytes, double)
            payload.extend(struct.pack(">d", from_amount))

            # Pack payin_address (variable length string)
            payload.extend(self.pack_string(payin_address))

            # Pack context (variable length string) - NEW
            payload.extend(self.pack_string(context.lower()))

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

            print(f"✅ [TOKEN_ENC] Token encrypted successfully")
            print(f"🆔 [TOKEN_ENC] Accumulation ID: {accumulation_id}")
            print(f"🆔 [TOKEN_ENC] CN API ID: {cn_api_id}")

            return token

        except Exception as e:
            print(f"❌ [TOKEN_ENC] Encryption error: {e}")
            return None

    def decrypt_pgp_hostpay1_to_accumulator_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decrypt token from PGP_HOSTPAY1_v1 with swap execution completion details.

        Expected fields:
        - accumulation_id (int)
        - cn_api_id (str)
        - tx_hash (str)
        - to_amount (float)
        - timestamp (int)

        Returns:
            Dictionary with decrypted data or None if failed
        """
        try:
            print(f"🔓 [TOKEN_DEC] PGP_HOSTPAY1_v1→PGP_ACCUMULATOR: Decrypting execution response")

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

            # Unpack accumulation_id (8 bytes, uint64)
            accumulation_id = struct.unpack(">Q", payload[offset:offset + 8])[0]
            offset += 8

            # Unpack cn_api_id (variable length string)
            cn_api_id, offset = self.unpack_string(payload, offset)

            # Unpack tx_hash (variable length string)
            tx_hash, offset = self.unpack_string(payload, offset)

            # Unpack to_amount (8 bytes, double)
            to_amount = struct.unpack(">d", payload[offset:offset + 8])[0]
            offset += 8

            # Unpack timestamp (8 bytes, uint64)
            timestamp = struct.unpack(">Q", payload[offset:offset + 8])[0]
            offset += 8

            # Validate timestamp (5 minutes = 300 seconds)
            current_time = int(time.time())
            if not (current_time - 300 <= timestamp <= current_time + 5):
                raise ValueError("Token expired")

            print(f"✅ [TOKEN_DEC] Accumulation ID: {accumulation_id}")
            print(f"✅ [TOKEN_DEC] CN API ID: {cn_api_id}")
            print(f"✅ [TOKEN_DEC] TX Hash: {tx_hash}")
            print(f"✅ [TOKEN_DEC] Final USDT: ${to_amount}")

            return {
                "accumulation_id": accumulation_id,
                "cn_api_id": cn_api_id,
                "tx_hash": tx_hash,
                "to_amount": to_amount,
                "timestamp": timestamp
            }

        except Exception as e:
            print(f"❌ [TOKEN_DEC] Decryption error: {e}")
            return None
