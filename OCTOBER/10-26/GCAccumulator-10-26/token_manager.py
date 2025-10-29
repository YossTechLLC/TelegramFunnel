#!/usr/bin/env python
"""
Token Manager for GCAccumulator-10-26 (Payment Accumulation Service).
Handles token encryption for communication with GCSplit2.
"""
import base64
import hmac
import hashlib
import json
from typing import Optional


class TokenManager:
    """
    Manages token encryption for GCAccumulator-10-26.
    """

    def __init__(self, signing_key: str):
        """
        Initialize the TokenManager.

        Args:
            signing_key: SUCCESS_URL_SIGNING_KEY for token encryption
        """
        self.signing_key = signing_key
        print(f"🔐 [TOKEN] TokenManager initialized")

    def encrypt_token_for_gcsplit2(
        self,
        user_id: int,
        client_id: str,
        wallet_address: str,
        payout_currency: str,
        payout_network: str,
        adjusted_amount_usd: float
    ) -> Optional[str]:
        """
        Encrypt token for GCSplit2 USDT conversion request.

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
            print(f"🔐 [TOKEN] Encrypting token for GCSplit2")
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
