#!/usr/bin/env python
"""
Token Manager for PGP_SPLIT3_v1
Handles encryption and decryption of tokens for secure inter-service communication via Cloud Tasks.
"""
import base64
import hmac
import hashlib
import struct
import time
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

    def encrypt_pgp_split1_to_pgp_split3_token(
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
        Encrypt token for PGP_SPLIT1_v1 → PGP_SPLIT3_v1 (ETH→Client swap request).

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
            print(f"🔐 [TOKEN_ENC] PGP_SPLIT1_v1→PGP_SPLIT3_v1: Encrypting swap request")

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

    def decrypt_pgp_split1_to_pgp_split3_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Decrypt token from PGP_SPLIT1_v1 → PGP_SPLIT3_v1."""
        try:
            print(f"🔓 [TOKEN_DEC] PGP_SPLIT1_v1→PGP_SPLIT3_v1: Decrypting swap request")

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
            swap_currency = 'usdt'  # Default for old tokens (this won't be used in PGP_SPLIT3_v1)
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

    def encrypt_pgp_split3_to_pgp_split1_token(
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
        Encrypt token for PGP_SPLIT3_v1 → PGP_SPLIT1_v1 (ETH→Client swap response).

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
            print(f"🔐 [TOKEN_ENC] PGP_SPLIT3_v1→PGP_SPLIT1_v1: Encrypting swap response")
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

    def decrypt_pgp_split3_to_pgp_split1_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Decrypt token from PGP_SPLIT3_v1 → PGP_SPLIT1_v1."""
        try:
            print(f"🔓 [TOKEN_DEC] PGP_SPLIT3_v1→PGP_SPLIT1_v1: Decrypting swap response")

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
